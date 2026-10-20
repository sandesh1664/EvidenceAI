import subprocess,json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
cmd=[str(root/'apps/api/.venv/bin/python'),'-m','pytest','-q','tests/test_database_isolation.py']
with (root/'docs/evidence/m125/isolation-tests-final.log').open('w') as log:r=subprocess.run(cmd,cwd=root/'apps/api',stdout=log,stderr=log)
(root/'docs/evidence/m125/isolation-test-final-command.json').write_text(json.dumps({'command':cmd,'cwd':'apps/api','exit_code':r.returncode},indent=2)+'\n')
raise SystemExit(r.returncode)
