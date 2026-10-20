"""Publication and deployment invariants; no DB, credentials or hosted operations."""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]


class WorkflowSafetyTests(unittest.TestCase):
    def test_only_fixed_summary_can_be_uploaded(self):
        ci=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertEqual(ci.count('uses: actions/upload-artifact@'),1)
        self.assertIn('path: safe-ci-summary/status.json',ci)
        self.assertNotIn('path: release/',ci)
        self.assertNotIn('path: reports/',ci)
        self.assertNotIn('path: apps/api/evaluation',ci)
        self.assertIn('needs: [secrets, application, containers, dependency-report]',ci)
        self.assertEqual(ci.count('if: always()'),1)
        for name in ('application','containers','dependency-report'):
            self.assertIn('  '+name+':\n    needs: secrets',ci)

    def test_third_party_actions_pinned_and_checkout_credentials_not_persisted(self):
        for name in ('ci.yml','deploy.yml'):
            text=(ROOT/'.github/workflows'/name).read_text()
            for target in re.findall(r'uses:\s*(\S+)',text):
                self.assertRegex(target,r'^[\w.-]+/[\w.-]+@[a-f0-9]{40}$')
            self.assertNotIn('persist-credentials: true',text)
        ci=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('fetch-depth: 0',ci)
        self.assertNotIn('cache: pip',ci)
        self.assertNotIn('cache: npm',ci)

    def test_deployment_is_manual_and_credentials_follow_guards(self):
        text=(ROOT/'.github/workflows/deploy.yml').read_text()
        triggers=text.split('permissions:',1)[0]
        self.assertIn('workflow_dispatch:',triggers)
        self.assertNotIn('push:',triggers)
        self.assertNotIn('workflow_run:',triggers)
        guard=text.index('Require passing main-branch verification')
        credentials=text.index('SSH_PRIVATE_KEY:')
        self.assertGreater(credentials,guard)
        self.assertIn('prevent_self_review',text)
        self.assertIn('python3 infra/scripts/verify_release.py /etc/evidenceai/accepted/$RELEASE_SHA.json',text)
        self.assertIn('StrictHostKeyChecking=yes',text)
        self.assertIn('if: always()',text)  # SSH-key cleanup stays unconditional.
        self.assertNotIn('upload-artifact',text)

    def test_release_evidence_gate_still_rejects_missing_failed_or_unknown(self):
        spec=importlib.util.spec_from_file_location('release_gate',ROOT/'infra/scripts/verify_release.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        complete={name:'PASS' for name in module.REQUIRED}
        for value in ('FAIL','NOT VERIFIED'):
            self.assertEqual(module.decision({**complete,'container_security':value})['release'],'BLOCKED')
        self.assertEqual(module.decision({})['release'],'BLOCKED')
        with self.assertRaises(ValueError):module.decision({'container_security':'WAIVED'})


if __name__=='__main__':unittest.main()
