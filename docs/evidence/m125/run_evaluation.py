import subprocess,json
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=root/'infra/runtime/m125/evaluation';out.mkdir(exist_ok=True)
cmd=[str(root/'apps/api/.venv/bin/python'),'-m','app.evaluate','--repeat','3','--output-dir',str(out)]
r=subprocess.run(cmd,cwd=root/'apps/api',capture_output=True,text=True)
(root/'infra/runtime/m125/evaluation.log').write_text(r.stdout+r.stderr)
record={'command':cmd,'cwd':'apps/api','exit_code':r.returncode}
if r.returncode==0:record['observed']=json.loads(r.stdout)
(root/'docs/evidence/m125/evaluation-command.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(r.returncode)
