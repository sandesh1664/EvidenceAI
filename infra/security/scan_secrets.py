#!/usr/bin/env python3
"""Unsuppressed Gitleaks plus exact, reviewed non-credential adjudications.

Raw reports never enter the checkout or stdout. No network validation is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = '8.30.1'
RULES = {'generic': 'generic-api-key', 'sourcegraph': 'sourcegraph-access-token'}
ARCHIVES = ('.gz', '.zip', '.tgz', '.tar')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)


def finding_key(row):
    return tuple(row[k] for k in ('scope', 'path', 'revision', 'blob_digest',
                                 'value_digest', 'rule', 'line', 'end_line',
                                 'column', 'end_column'))


def policy_keys(path, repo):
    data = json.loads(path.read_text())
    if data['version'] != 1 or data['scanner'] != VERSION:
        raise ValueError('Unsupported adjudication policy')
    keys = set()
    for row in data['findings']:
        if row['basis'] not in {'public_module_checksum', 'recomputed_blob_hash',
                                'public_source_revision', 'narrative_context'}:
            raise ValueError('Unreviewed proof class')
        row = dict(row)
        row['rule'] = RULES[row['rule']]
        if row['scope'] == 'history':
            revision = row['revision']
            if not re.fullmatch('[a-f0-9]{12}', revision):
                raise ValueError('Exact commit prefix required')
            # Ambiguity/missing historical objects fail closed.
            row['revision'] = git(repo, 'rev-parse', '--verify', revision+'^{commit}').decode().strip()
        elif row['scope'] not in {'current', 'archive'} or row['revision']:
            raise ValueError('Unexpected adjudication scope')
        for field in ('blob_digest', 'value_digest'):
            if not re.fullmatch('[a-f0-9]{64}', row[field]):
                raise ValueError('Invalid digest')
        if not row['path'] or row['path'].startswith('/') or '..' in row['path'].split('/'):
            raise ValueError('Invalid relative path')
        key = finding_key(row)
        if key in keys:
            raise ValueError('Duplicate adjudication')
        keys.add(key)
    return keys


def normalize(finding, scope, repo, snapshot, archive_map):
    path = finding['File']
    revision = finding.get('Commit', '') if scope == 'history' else ''
    if scope == 'history':
        blob = git(repo, 'show', revision+':'+path.partition('!')[0])
    else:
        outer, delimiter, member = path.partition('!')
        outer_path = Path(outer)
        blob = outer_path.read_bytes()
        if scope == 'archive':
            path = archive_map[str(outer_path)] + (delimiter+member if delimiter else '')
        else:
            path = str(outer_path.relative_to(snapshot)) + (delimiter+member if delimiter else '')
    return {'scope': scope, 'path': path, 'revision': revision,
            'blob_digest': digest(blob), 'value_digest': digest(finding['Secret'].encode()),
            'rule': finding['RuleID'], 'line': finding['StartLine'],
            'end_line': finding['EndLine'], 'column': finding['StartColumn'],
            'end_column': finding['EndColumn']}


def run_scanner(binary, mode, source, report, extra=()):
    if stat.S_IMODE(report.parent.stat().st_mode) != 0o700:
        raise ValueError('Raw report parent must be private')
    env = dict(os.environ)
    for key in ('GITLEAKS_CONFIG', 'GITLEAKS_CONFIG_TOML'):
        env.pop(key, None)
    command = [binary, mode, '--no-banner', '--no-color',
               '--config', str(ROOT/'infra/security/gitleaks.toml'),
               '--gitleaks-ignore-path', str(report.parent/'no-ignore-file'),
               '--ignore-gitleaks-allow', '--max-archive-depth=3',
               '--report-format=json', '--report-path='+str(report), *extra, str(source)]
    # Precreate at0600 before the scanner writes, independent of caller umask.
    descriptor = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    with report.with_suffix('.log').open('x') as log:
        os.chmod(log.name, 0o600)
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    if report.is_file():
        # Gitleaks chooses0644 on output; the0700 parent protects the write.
        os.chmod(report, 0o600)
    if result.returncode not in (0, 1) or not report.is_file():
        raise RuntimeError('Scanner execution failed')
    findings = json.loads(report.read_text())
    if not isinstance(findings, list) or (result.returncode == 0) != (len(findings) == 0):
        raise RuntimeError('Inconsistent scanner result')
    return findings, result.returncode


def scan(repo, private, binary='gitleaks'):
    """Scan reachable history, index/working source and historical archive bytes."""
    version = subprocess.check_output([binary, 'version'], stderr=subprocess.PIPE).decode().strip()
    if version != VERSION:
        raise ValueError('Pinned scanner version required')
    snapshot = private/'current'
    snapshot.mkdir(mode=0o700)
    paths = git(repo, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').split(b'\0')
    for encoded in set(paths)-{b''}:
        path = os.fsdecode(encoded)
        source = repo/path
        if source.is_symlink():
            # Never follow a checkout symlink into ignored/private host data.
            raise ValueError('Symlink in scan input requires review')
        if not source.exists():
            continue
        if not source.is_file():
            raise ValueError('Non-file scan input requires review')
        target = snapshot/path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    archives = private/'archives'
    archives.mkdir(mode=0o700)
    archive_map = {}
    objects = git(repo, 'rev-list', '--objects', '--all').decode().splitlines()
    for item in objects:
        oid, separator, path = item.partition(' ')
        if separator and path.endswith(ARCHIVES):
            if git(repo, 'cat-file', '-t', oid).strip() != b'blob':
                continue
            target = archives/(oid+'-'+Path(path).name)
            target.write_bytes(git(repo, 'cat-file', 'blob', oid))
            archive_map[str(target)] = path
    records = []
    statuses = []
    for scope, mode, source, extra in (
            ('history', 'git', repo, ['--log-opts=--all']),
            ('current', 'dir', snapshot, []), ('archive', 'dir', archives, [])):
        report = private/(scope+'.json')
        findings, code = run_scanner(binary, mode, source, report, extra)
        records.extend(normalize(row, scope, repo, snapshot, archive_map) for row in findings)
        statuses.append({'scope': scope, 'exit_code': code, 'findings': len(findings)})
    # Private normalized index contains digests/coordinates only; raw JSON is separate.
    (private/'index.json').write_text(json.dumps(records, indent=2)+'\n')
    return records, statuses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--policy', type=Path, default=ROOT/'infra/security/adjudications.json')
    parser.add_argument('--private-directory', type=Path)
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        repo = args.repo.resolve()
        if args.private_directory:
            private = args.private_directory.resolve()
            if private == repo or repo in private.parents:
                raise ValueError('Raw evidence must stay outside checkout')
            private.mkdir(mode=0o700, parents=False, exist_ok=False)
        else:
            private = Path(tempfile.mkdtemp(prefix='evidenceai-secret-scan-'))
        if stat.S_IMODE(private.stat().st_mode) != 0o700:
            raise ValueError('Restricted evidence directory required')
        records, statuses = scan(repo, private)
        accepted = set() if args.audit_only else policy_keys(args.policy, repo)
        unknown = sum(finding_key(row) not in accepted for row in records)
        summary = {'status': 'FAIL' if unknown else 'PASS', 'unreviewed_findings': unknown,
                   'adjudicated_findings': len(records)-unknown, 'unsuppressed_scans': statuses}
        (private/'result.json').write_text(json.dumps(summary, indent=2)+'\n')
        print(json.dumps(summary))
        return 1 if unknown else 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            RuntimeError, subprocess.SubprocessError):
        # Never echo untrusted scanner errors/config/secret-bearing diagnostics.
        print('Secret verification failed; inspect restricted local evidence.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
