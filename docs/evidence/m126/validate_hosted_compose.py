"""Validate prepared hosted overlay with synthetic configuration, without startup."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('deploy',ROOT/'infra/scripts/deploy.py')
deploy=importlib.util.module_from_spec(spec);spec.loader.exec_module(deploy)
with tempfile.TemporaryDirectory(prefix='evidenceai-m126-compose-') as temp:
 directory=Path(temp);secret=directory/'secrets';secret.mkdir(mode=0o700)
 for name in ('db_password','postgres_password','operations_token','grafana_password'):
  (secret/name).write_text('synthetic-validation-only-'+'a'*32)
 for name in ('provider_key','smtp_password'):(secret/name).write_text('')
 values={'DEPLOY_PROJECT':'evidenceai-staging-m126validate','SITE_HOST':'staging.example.invalid','PUBLIC_ORIGIN':'https://staging.example.invalid','ACME_EMAIL':'operator@example.invalid','SECRETS_DIR':str(secret),'AGE_RECIPIENT':'age1'+'a'*58}
 values.update({key:'registry.example.invalid/'+key.lower()+'@sha256:'+'a'*64 for key in ('API_IMAGE','WEB_IMAGE','DATABASE_IMAGE','BACKUP_IMAGE','PROXY_IMAGE','PROMETHEUS_IMAGE','EXPORTER_IMAGE')})
 path=directory/'staging.env';path.write_text('\n'.join(k+'='+v for k,v in values.items())+'\n')
 deploy.configuration(path,'staging')
 cmd=['docker','compose','--project-name',values['DEPLOY_PROJECT'],'--env-file',str(path),'-f',str(ROOT/'infra/compose.production.yml'),'-f',str(ROOT/'infra/compose.hosted-staging.yml'),'--profile','monitoring','--profile','operations','config','--format','json']
 r=subprocess.run(cmd,capture_output=True,text=True,env={**os.environ,**values});r.check_returncode();data=json.loads(r.stdout)
 services=data['services'];proxy=services['proxy'];grafana=services['grafana']
 checks={'staging_environment':all(services[n]['environment']['APP_ENV']=='staging' for n in ('api','worker','migrate')),'public_ports':{p['published'] for p in proxy['ports']}=={'80','443'},'public_tls':any(v['source'].endswith('/tls.production.caddy') and v['target']=='/etc/caddy/tls.caddy' for v in proxy['volumes']),'private_monitoring':not grafana.get('ports') and data['networks']['monitoring']['internal'],'proxy_trust_preserved':services['api']['environment']['TRUSTED_PROXY_IP']=='172.30.11.10','separate_project':data['name']==values['DEPLOY_PROJECT'],'selected_grafana_unchanged':grafana['image'].endswith('dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f')}
 out={'status':'PASS' if all(checks.values()) else 'FAIL','scope':'Compose configuration only; no containers started, no DNS or TLS issuance','exit_code':r.returncode,'checks':checks,'initial_harness_failure':'Initial ad-hoc validation omitted --profile monitoring/operations, so accessing omitted grafana raised KeyError; no application or startup failure. Corrected harness enables profiles.'}
 target=ROOT/'docs/evidence/m126/hosted-compose-validation.json'
 with target.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
 print(json.dumps(out,indent=2));assert all(checks.values())
