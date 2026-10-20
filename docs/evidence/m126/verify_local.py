"""12.6 append-only command receipts; disposable fixtures only for DB tests."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'docs/evidence/m126'
LOG = ROOT/'infra/runtime/m126'
GROUP = sys.argv[1]
PYTHON = str(ROOT/'apps/api/.venv/bin/python')
sets = {
 'backend': [
  ('backend', '.', [PYTHON, '-m', 'pytest', 'apps/api/tests', '-q', '--junitxml='+str(OUT/'backend.xml')]),
  ('migration-current', 'apps/api', [PYTHON, '-m', 'alembic', 'current']),
  ('migration-check', 'apps/api', [PYTHON, '-m', 'alembic', 'check']),
  ('pip-check', 'apps/api', [PYTHON, '-m', 'pip', 'check']),
 ],
 'frontend': [
  ('unit', 'apps/web', ['npm', 'test']),
  ('lint', 'apps/web', ['npm', 'run', 'lint']),
  ('types', 'apps/web', ['npx', '--no-install', 'tsc', '--noEmit']),
  ('build', 'apps/web', ['npm', 'run', 'build']),
  ('npm-runtime', 'apps/web', ['npm', 'audit', '--omit=dev', '--json']),
  ('npm-all', 'apps/web', ['npm', 'audit', '--json']),
 ],
 'browser': [('browser', 'apps/web', ['npm', 'run', 'test:e2e'])],
 'runner': [('runner', '.', [PYTHON, '-m', 'unittest', 'discover', '-s', 'infra/testing', '-p', 'test_run_isolated.py', '-v'])],
 'monitoring': [('monitoring', '.', [sys.executable, 'infra/scripts/smoke.py'])],
}
sets['browser-final'] = [('browser-final', 'apps/web', ['npm', 'run', 'test:e2e'])]
env = os.environ.copy()
env['PLAYWRIGHT_BROWSERS_PATH'] = '/tmp/evidenceai-m126-browsers' if GROUP == 'browser-final' else '/tmp/evidenceai-m12-browsers'
env['EVIDENCEAI_EVIDENCE_TAG'] = 'm126'
env['EVIDENCEAI_ACCEPTANCE'] = '0'
env['EVIDENCEAI_GRAFANA_IMAGE'] = 'grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185'
env['EVIDENCEAI_GRAFANA_TRANSITION_IMAGE'] = 'evidenceai-grafana:kin-m125'
# Default smoke covers monitoring/recovery; do not repeat completed load certification.
rows = []
receipt = OUT/(GROUP+'-commands.json')
if receipt.exists(): raise SystemExit('Refusing to overwrite existing receipt')
for name, cwd, cmd in sets[GROUP]:
 start = time.monotonic()
 utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (LOG/(name+'.log')).open('x') as log:
  result = subprocess.run(cmd, cwd=ROOT/cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
 rows.append({'name':name, 'cwd':cwd, 'command':cmd, 'started_utc':utc, 'exit_code':result.returncode, 'seconds':round(time.monotonic()-start,3)})
 receipt.write_text(json.dumps(rows,indent=2)+'\n')
 print(name, result.returncode, flush=True)
raise SystemExit(0 if all(r['exit_code']==0 for r in rows) else 1)
