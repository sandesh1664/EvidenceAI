"""Synthetic values are generated locally, never issued credentials or tracked literals."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'infra/security'))
from scan_secrets import finding_key, normalize, policy_keys, run_scanner
from ci_summary import JOBS, summarize


class ExactPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = policy_keys(ROOT/'infra/security/adjudications.json', ROOT)

    def test_scope_location_bytes_and_value_all_bound(self):
        fields = ('scope', 'path', 'revision', 'blob_digest', 'value_digest',
                  'rule', 'line', 'end_line', 'column', 'end_column')
        key = next(iter(self.keys))
        for index, field in enumerate(fields):
            with self.subTest(field=field):
                changed = list(key)
                changed[index] = changed[index]+1 if isinstance(changed[index], int) else changed[index]+'changed'
                self.assertNotIn(tuple(changed), self.keys)

    def test_same_line_occurrences_have_distinct_columns(self):
        rows = json.loads((ROOT/'infra/security/adjudications.json').read_text())['findings']
        rows = [r for r in rows if r['scope']=='history' and r['path']=='docs/evidence/m124/kin-workspace-build.log' and r['rule']=='sourcegraph']
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['column'] for r in rows}), 2)

    def test_policy_rejects_duplicate_or_unproved_entries(self):
        policy = json.loads((ROOT/'infra/security/adjudications.json').read_text())
        for alteration in ('duplicate', 'basis', 'scanner'):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as directory:
                copy = json.loads(json.dumps(policy))
                if alteration=='duplicate': copy['findings'].append(copy['findings'][0])
                elif alteration=='basis': copy['findings'][0]['basis']='unreviewed'
                else: copy['scanner']='unknown'
                path=Path(directory)/'policy.json';path.write_text(json.dumps(copy))
                with self.assertRaises(ValueError):policy_keys(path,ROOT)


class RealScannerTests(unittest.TestCase):
    def test_genuine_patterns_inline_comments_and_archives_fail(self):
        self.assertIsNotNone(shutil.which('gitleaks'))
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);source=base/'source';source.mkdir();reports=base/'reports';reports.mkdir(mode=0o700)
            # These have real detector shapes but are locally generated, non-issued fixtures.
            pat='gh'+'p_'+secrets.token_hex(18)
            source_token='sg'+'p_'+secrets.token_hex(20)
            generic=secrets.token_urlsafe(36)
            (source/'fixture.py').write_text('api_key = '+repr(generic)+' # gitleaks:allow\n')
            (source/'token.txt').write_text(pat+'\n')
            with zipfile.ZipFile(source/'fixture.zip','w') as archive:archive.writestr('nested.txt',source_token+'\n')
            (source/'.gitleaks.toml').write_text('[allowlist]\nregexes = [".*"]\n')
            findings, code=run_scanner('gitleaks','dir',source,reports/'scan.json')
            self.assertEqual(code,1)
            found={r['Secret'] for r in findings}
            for value in (pat,source_token,generic):self.assertTrue(value in found)
            installed=policy_keys(ROOT/'infra/security/adjudications.json',ROOT)
            rows=[normalize(f,'current',ROOT,source,{}) for f in findings]
            self.assertTrue(all(finding_key(row) not in installed for row in rows))
            self.assertEqual((reports/'scan.json').stat().st_mode & 0o077,0)

    def test_new_value_in_reviewed_file_fails_end_to_end(self):
        # Copy existing history only: no commits or history rewriting, including in fixtures.
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);repo=base/'repo';private=base/'private'
            with (base/'clone.log').open('w') as log:
                subprocess.run(['git','clone','--no-local',str(ROOT),str(repo)],check=True,stdout=log,stderr=log)
            value='gh'+'p_'+secrets.token_hex(18)
            target=repo/'docs/evidence/m125/build-provenance.txt'
            with target.open('a') as file:file.write('\n'+value+'\n')
            result=subprocess.run([sys.executable,str(ROOT/'infra/security/scan_secrets.py'),
                '--repo',str(repo),'--policy',str(ROOT/'infra/security/adjudications.json'),
                '--private-directory',str(private)],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertNotIn(value,result.stdout+result.stderr)
            summary=json.loads((private/'result.json').read_text())
            self.assertGreater(summary['unreviewed_findings'],0)
            self.assertTrue((private/'history.json').exists())


class SafeSummaryTests(unittest.TestCase):
    def test_failures_preserved_without_outputs_or_diagnostics(self):
        sentinel=secrets.token_urlsafe(32)
        data={name:{'result':'failure','outputs':{'private':sentinel}} for name in JOBS}
        summary=summarize(data)
        self.assertNotIn(sentinel,json.dumps(summary))
        self.assertEqual(set(summary['jobs'].values()),{'failure'})
        self.assertFalse(summary['raw_artifacts_uploaded'])

    def test_untrusted_status_or_job_name_rejected(self):
        data={name:{'result':'success'} for name in JOBS}
        data['secrets']['result']='unexpected text'
        with self.assertRaises(ValueError):summarize(data)
        with self.assertRaises(ValueError):summarize({'unreviewed':{'result':'success'}})


if __name__=='__main__':unittest.main()
