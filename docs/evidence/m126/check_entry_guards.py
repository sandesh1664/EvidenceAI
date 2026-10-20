"""Exercise actual test entry points with forbidden DB targets; no connections permitted."""
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
PYTHON=str(ROOT/'apps/api/.venv/bin/python')
rows=[]
commands={
 'pytest':[PYTHON,'-m','pytest','--collect-only','-q','apps/api/tests/test_database_isolation.py'],
 'browser':[PYTHON,'apps/web/e2e/server.py'],
 'retrieval':[PYTHON,'-c','from app.evaluate_retrieval import evaluate; evaluate()'],
 'rag':[PYTHON,'-c','from app.evaluate_rag import evaluate; evaluate()'],
 'combined':[PYTHON,'-m','app.evaluate'],
}
for label,url in [('missing',None),('development','postgresql+psycopg://localhost:5433/evidenceai'),('production','postgresql+psycopg://production.invalid:5432/evidenceai')]:
 for name,command in commands.items():
  env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join([str(ROOT/'apps/api'),str(ROOT/'infra/testing')])
  env['DATABASE_URL']=url or 'postgresql+psycopg://localhost:5433/evidenceai'
  env.pop('EVIDENCEAI_TEST_DATABASE_URL',None)
  if url:env['EVIDENCEAI_TEST_DATABASE_URL']=url
  result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
  # Do not publish raw traceback/config; only guard result and aggregate.
  refused=result.returncode!=0 and 'Explicit loopback disposable EVIDENCEAI_TEST_DATABASE_URL required' in result.stderr
  rows.append({'entry':name,'target':label,'command':command,'exit_code':result.returncode,'guard_refusal':refused})
p=ROOT/'docs/evidence/m126/entry-guards.json'
with p.open('x') as f:json.dump({'status':'PASS' if all(r['guard_refusal'] for r in rows) else 'FAIL','cases':rows},f,indent=2);f.write('\n')
print('Guard refusals:',sum(r['guard_refusal'] for r in rows),'/',len(rows))
raise SystemExit(0 if all(r['guard_refusal'] for r in rows) else 1)
