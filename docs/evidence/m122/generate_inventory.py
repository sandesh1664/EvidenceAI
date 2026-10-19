"""Regenerate 12.2 evidence from local full Trivy reports and image archives."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def image(directory, name, reference):
    path = directory / (name + '.json')
    data = json.loads(path.read_text())
    live = json.loads(subprocess.check_output(['docker', 'image', 'inspect', reference]))[0]
    archive = directory / 'archives' / (name + '.tar')
    with tarfile.open(archive) as tar:
        manifest = json.load(tar.extractfile('manifest.json'))
        config = tar.extractfile(manifest[0]['Config']).read()
        config_id = 'sha256:' + hashlib.sha256(config).hexdigest()
        assert config_id == data['Metadata']['ImageID'], name
        assert data['Metadata']['DiffIDs'] == live['RootFS']['Layers'], name
        assert json.loads(config)['rootfs']['diff_ids'] == live['RootFS']['Layers'], name
        # Docker Desktop's Id can be an OCI index, rather than the config ID.
        if live['Id'] != config_id:
            blob = tar.extractfile('blobs/sha256/' + live['Id'].split(':')[1]).read()
            assert 'sha256:' + hashlib.sha256(blob).hexdigest() == live['Id'], name
    rows = []
    for result in data.get('Results', []):
        for v in result.get('Vulnerabilities', []):
            if v['Severity'] not in ('HIGH', 'CRITICAL'):
                continue
            rows.append({'image': name, 'target': result['Target'],
                'advisory': v['VulnerabilityID'], 'package': v['PkgName'],
                'installed': v['InstalledVersion'], 'fixed': v.get('FixedVersion'),
                'severity': v['Severity'], 'title': v.get('Title'),
                'url': v.get('PrimaryURL'), 'layer': v.get('Layer'),
                'status': v.get('Status'),
                'reachability': 'Runtime binary present; no approved exception. Core serves APIs; Prometheus is provisioned and exercised. Other datasource use is configuration-dependent, not a waiver.'})
    secrets = [s for r in data.get('Results', []) for s in r.get('Secrets', [])]
    meta = {'reference': reference, 'scan_created_at': data['CreatedAt'],
        'scan_sha256': sha(path), 'archive_sha256': sha(archive),
        'artifact_id': data['ArtifactID'], 'docker_id': live['Id'],
        'config_id': config_id, 'diff_ids': live['RootFS']['Layers'],
        'os': data['Metadata'].get('OS'), 'architecture': live['Architecture'],
        'scan_matches_archive_and_live_layers': True,
        'high': sum(r['severity'] == 'HIGH' for r in rows),
        'critical': sum(r['severity'] == 'CRITICAL' for r in rows),
        'secrets': len(secrets)}
    return meta, rows


def main():
    baseline = json.loads((ROOT/'docs/security-remediation-inventory.json').read_text())['after']
    images, findings = {}, []
    for group in ('candidates', 'support'):
        directory = ROOT/'infra/runtime/m122'/group
        gate = json.loads((directory/'gate.json').read_text())
        for name, policy in gate.items():
            meta, rows = image(directory, name, policy['reference'])
            assert all(meta[k] == policy[k] for k in ('high', 'critical', 'secrets'))
            images[name] = meta
            findings += rows
    report = {'baseline_git': '0f58dcf0b0a5777acd48da738bd1aa460a9bc0ab',
        'working_tree_uncommitted': True,
        'scanner_reference': 'aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222',
        'vulnerability_database': json.loads((ROOT/'infra/runtime/m122/support/trivy-cache/trivy/db/metadata.json').read_text()),
        'before': {'source': 'docs/security-remediation-inventory.json#/after',
            'high': sum(r['high'] for r in baseline['images'].values()),
            'critical': sum(r['critical'] for r in baseline['images'].values()),
            'finding_occurrences': len(baseline['findings']),
            'distinct_advisories': len({r['advisory'] for r in baseline['findings']})},
        'after': {'images': images, 'high': sum(r['high'] for r in images.values()),
            'critical': sum(r['critical'] for r in images.values()),
            'finding_occurrences': len(findings),
            'distinct_advisories': len({r['advisory'] for r in findings}), 'findings': findings},
        'approved_exceptions': [], 'release': 'BLOCKED', 'experiments': {}}
    for group, reference in [('grafana-candidate', 'evidenceai-grafana:m122'),
                             ('grafana-core', 'evidenceai-grafana:experimental-m122')]:
        meta, rows = image(ROOT/'infra/runtime/m122'/group, 'grafana', reference)
        report['experiments'][group] = {'image': meta, 'findings': rows,
                                      'selected_for_production': False}
    (ROOT/'docs/security-remediation-12-2-inventory.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Archive/config/layer identities verified for eight selected images and two experiments.')
    print('Selected runtime findings:', report['after']['high'], 'high,', report['after']['critical'], 'critical')


if __name__ == '__main__':
    main()
