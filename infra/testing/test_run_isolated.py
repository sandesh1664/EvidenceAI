"""Import-path regressions; these checks do not provision or contact a database."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from run_isolated import ROOT, command_environment


class CommandEnvironmentTests(unittest.TestCase):
    def test_project_paths_take_precedence_and_input_is_unchanged(self):
        inherited = {'PYTHONPATH': 'custom', 'DATABASE_URL': 'inherited-value'}
        env = command_environment(inherited)
        self.assertEqual(env['PYTHONPATH'].split(os.pathsep), [
            str(ROOT/'apps/api'), str(ROOT/'infra/testing'), str(Path('custom').resolve()),
        ])
        self.assertEqual(inherited['PYTHONPATH'], 'custom')

    def test_relative_and_empty_entries_use_invoking_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = str(Path(directory).resolve())
            with patch('os.getcwd', return_value=directory):
                env = command_environment({'PYTHONPATH': 'custom' + os.pathsep})
            self.assertEqual(env['PYTHONPATH'].split(os.pathsep)[2:], [
                str(Path(directory)/'custom'), directory,
            ])

    def test_imports_and_fail_closed_guard_from_different_child_directories(self):
        env = command_environment({key: value for key, value in os.environ.items()
                                   if key not in {'PYTHONPATH', 'EVIDENCEAI_TEST_DATABASE_URL'}})
        env['DATABASE_URL'] = 'postgresql://development-must-not-be-used/development'
        code = '''
import app
from database_guard import activate
try:
    activate()
except RuntimeError as error:
    assert 'Explicit loopback disposable' in str(error)
else:
    raise AssertionError('Guard accepted an inherited development URL')
'''
        with tempfile.TemporaryDirectory() as directory:
            for cwd in (ROOT, ROOT/'apps/api', Path(directory)):
                with self.subTest(cwd=cwd):
                    subprocess.run([sys.executable, '-c', code], cwd=cwd, env=env, check=True)


if __name__ == '__main__':
    unittest.main()
