import subprocess,os,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[3];env=os.environ.copy();env['PLAYWRIGHT_BROWSERS_PATH']='/tmp/evidenceai-m12-browsers'
cmd=['npm','run','test:e2e'];start=time.monotonic()
with (root/'infra/runtime/m125/browser-final.log').open('w') as log:r=subprocess.run(cmd,cwd=root/'apps/web',env=env,stdout=log,stderr=log)
(root/'docs/evidence/m125/browser-final-command.json').write_text(json.dumps({'command':cmd,'cwd':'apps/web','exit_code':r.returncode,'seconds':round(time.monotonic()-start,3)},indent=2)+'\n')
raise SystemExit(r.returncode)
