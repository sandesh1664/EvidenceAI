import subprocess,json,time,os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=root/'docs/evidence/m124';logs=root/'infra/runtime/m124';group=sys.argv[1]
sets={
'backend':[('pytest','apps/api',['.venv/bin/python','-m','pytest','-q','--junitxml='+str(out/'backend.xml')]),('alembic-current','apps/api',['.venv/bin/python','-m','alembic','current']),('alembic-check','apps/api',['.venv/bin/python','-m','alembic','check']),('pip-check','apps/api',['.venv/bin/python','-m','pip','check'])],
'frontend':[('unit','apps/web',['npm','test']),('lint','apps/web',['npm','run','lint']),('types','apps/web',['npx','tsc','--noEmit']),('build','apps/web',['npm','run','build']),('browser','apps/web',['npm','run','test:e2e'])],
'audits':[('python-audit','apps/api',['/tmp/evidenceai-m11-audit-venv/bin/python','-m','pip_audit','-r','requirements.txt','--format','json']),('npm-runtime','apps/web',['npm','audit','--omit=dev','--json']),('npm-all','apps/web',['npm','audit','--json']),('actionlint','.', ['docker','run','--rm','--network','none','-v',str(root/'.github/workflows')+':/work:ro','-w','/work','rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667','-color','ci.yml','deploy.yml'])]}
rows=[];env=os.environ.copy();env['PLAYWRIGHT_BROWSERS_PATH']='/tmp/evidenceai-m12-browsers';env['EVIDENCEAI_TIMING_REPORT']=str(out/'registration-timing.json')
for name,cwd,cmd in sets[group]:
 start=time.monotonic()
 with (logs/(name+'.log')).open('w') as log:r=subprocess.run(cmd,cwd=root/cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
 rows.append({'name':name,'cwd':cwd,'command':cmd,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,3)})
 (out/(group+'-commands.json')).write_text(json.dumps(rows,indent=2)+'\n');print(name,r.returncode,flush=True)
