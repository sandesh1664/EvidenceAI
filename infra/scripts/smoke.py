#!/usr/bin/env python3
"""Local-only staging drill. Own bind mounts/tmpfs; never existing DBs or Docker volumes."""
import hashlib
import http.cookiejar
import io
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[2]


def run(command,**kwargs):
    result=subprocess.run(command,check=True,**kwargs)
    return result.stdout


def main():
    identity=uuid.uuid4().hex[:10]
    project='evidenceai-staging-smoke'+identity
    report={'scope':'local isolated staging, private CA; not public TLS or production acceptance','project':project}
    with tempfile.TemporaryDirectory(prefix='evidenceai-m11-') as raw:
        directory=Path(raw).resolve()
        private=directory/'secrets';private.mkdir(mode=0o700)
        for name in ('db_password','postgres_password','operations_token','grafana_password'):
            (private/name).write_text(secrets.token_hex(32));(private/name).chmod(0o444)
        (private/'provider_key').write_text('');(private/'provider_key').chmod(0o444)
        key=run(['docker','run','--rm','--network','none','--entrypoint','age-keygen','evidenceai-backup:m11'],stdout=subprocess.PIPE,stderr=subprocess.PIPE).decode()
        (private/'age_identity').write_text(key);(private/'age_identity').chmod(0o444)
        recipient=next(line.split(': ',1)[1] for line in key.splitlines() if line.startswith('# public key:'))
        values={'DEPLOY_PROJECT':project,'SITE_HOST':'localhost','PUBLIC_ORIGIN':'https://localhost:18443',
            'ACME_EMAIL':'local@example.invalid','API_IMAGE':'evidenceai-api:m11','WEB_IMAGE':'evidenceai-web:m11',
            'BACKUP_IMAGE':'evidenceai-backup:m11','PROXY_IMAGE':'evidenceai-proxy:m11','SECRETS_DIR':str(private),'AGE_RECIPIENT':recipient,
            'EMBEDDING_PROVIDER':'fake','LLM_PROVIDER':'mock'}
        envfile=directory/'stage.env';envfile.write_text('\n'.join(k+'='+v for k,v in values.items())+'\n')
        names=('documents','metrics','proxy','backups','prometheus','grafana')
        for name in names: (directory/name).mkdir()
        # Only synthetic temporary directories are touched by this bounded ownership helper.
        helper="import os; base='/fixture'; [os.chown(base+'/'+n,10001,10001) or os.chmod(base+'/'+n,0o700) for n in ['documents','metrics','proxy','backups']]; os.chown(base+'/prometheus',65534,65534); os.chown(base+'/grafana',472,0)"
        run(['docker','run','--rm','--network','none','--user','0','--entrypoint','python','-v',str(directory)+':/fixture','evidenceai-api:m11','-c',helper])
        def mount(name,target,ro=''): return json.dumps(str(directory/name)+':'+target+ro)
        override=directory/'smoke.yml'
        override.write_text(f'''services:
  db:
    volumes: !override ["{ROOT}/infra/deploy/init-db.sh:/docker-entrypoint-initdb.d/10-evidenceai.sh:ro"]
    tmpfs: !override ["/var/lib/postgresql/data:rw,nosuid,size=512m,uid=999,gid=999", "/var/run/postgresql:rw,nosuid,size=16m,uid=999,gid=999", "/tmp:rw,nosuid,size=32m,uid=999,gid=999"]
  api:
    volumes: !override [{mount('documents','/data/documents')}]
    environment: {{TRUSTED_PROXY_IP: 172.30.31.10}}
  worker:
    volumes: !override [{mount('documents','/data/documents')}, {mount('metrics','/metrics')}]
  migrate:
    volumes: !override [{mount('documents','/data/documents')}]
  proxy:
    volumes: !override ["{ROOT}/infra/deploy/Caddyfile:/etc/caddy/Caddyfile:ro", "{ROOT}/infra/deploy/tls.staging.caddy:/etc/caddy/tls.caddy:ro", {mount('proxy','/data')}]
    networks:
      application: {{ipv4_address: 172.30.31.10}}
  backup:
    volumes: !override [{mount('documents','/documents',':ro')}, {mount('backups','/backups')}]
  restore-verify:
    volumes: !override [{mount('backups','/backups',':ro')}]
  prometheus:
    volumes: !override ["{ROOT}/infra/deploy/prometheus.yml:/etc/prometheus/prometheus.yml:ro", "{ROOT}/infra/monitoring/alerts.yml:/etc/prometheus/alerts.yml:ro", {mount('prometheus','/prometheus')}]
  grafana:
    volumes: !override [{mount('grafana','/var/lib/grafana')}, "{ROOT}/infra/monitoring/grafana/provisioning:/etc/grafana/provisioning:ro", "{ROOT}/infra/monitoring/grafana/evidenceai.json:/var/lib/grafana/dashboards/evidenceai.json:ro"]
  worker-exporter:
    volumes: !override [{mount('metrics','/metrics',':ro')}]
networks:
  application:
    ipam:
      config: !override [{{subnet: 172.30.31.0/24}}]
volumes: !reset {{}}
''')
        command=['docker','compose','--project-name',project,'--env-file',str(envfile),'-f',str(ROOT/'infra/compose.production.yml'),'-f',str(ROOT/'infra/compose.staging.yml'),'-f',str(override)]
        env=os.environ.copy();env.update(values)
        def compose(*args,capture=False):
            return run(command+list(args),env=env,stdout=subprocess.PIPE if capture else None,text=True)
        try:
            compose('config','--quiet')
            run([sys.executable,str(ROOT/'infra/scripts/deploy.py'),'--env-file',str(envfile),'validate'])
            production={**values,'DEPLOY_PROJECT':'evidenceai-production-validate'+identity,'SITE_HOST':'evidenceai.example.com','PUBLIC_ORIGIN':'https://evidenceai.example.com','ACME_EMAIL':'operator@example.com'}
            for key in ('API_IMAGE','WEB_IMAGE','BACKUP_IMAGE','PROXY_IMAGE'): production[key]='registry.example.com/release@sha256:'+'a'*64
            production_env=directory/'production.env';production_env.write_text('\n'.join(k+'='+v for k,v in production.items()))
            run([sys.executable,str(ROOT/'infra/scripts/deploy.py'),'--environment','production','--env-file',str(production_env),'validate'])
            report['compose_validation']='staging and production; production was not started'
            compose('up','-d','--wait','db')
            compose('run','--rm','migrate')
            compose('up','-d','--wait','api','worker','web','proxy')
            compose('--profile','monitoring','up','-d','--wait','prometheus','worker-exporter','grafana')
            ca=directory/'root.crt';compose('cp','proxy:/data/caddy/pki/authorities/local/root.crt',str(ca))
            context=ssl.create_default_context(cafile=str(ca))
            cookies=http.cookiejar.CookieJar()
            opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(cookies))
            origin='https://localhost:18443'
            def request(path,body=None,method=None,headers=None):
                actual={'Origin':origin,'X-CSRF-Protection':'1','X-Request-ID':str(uuid.uuid4())}
                if headers is not None: actual=headers
                if isinstance(body,dict): actual['Content-Type']='application/json';body=json.dumps(body).encode()
                req=urllib.request.Request(origin+path,data=body,headers=actual,method=method)
                try:
                    with opener.open(req,timeout=30) as response: return response.status,response.read(),response.headers
                except urllib.error.HTTPError as response: return response.code,response.read(),response.headers
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self,*args,**kwargs): return None
            try:
                urllib.request.build_opener(NoRedirect()).open('http://localhost:18080/login',timeout=5)
            except urllib.error.HTTPError as redirect:
                assert redirect.code==308 and redirect.headers['Location']==origin+'/login'
            else: raise AssertionError('HTTP was not redirected')
            assert request('/login')[0]==200
            assert request('/api/v1/ready')[0]==200
            assert 'max-age=' in request('/login')[2]['Strict-Transport-Security']
            assert 'no-store' in request('/api/v1/ready')[2]['Cache-Control']
            assert request('/api/v1/ops/metrics')[0]==404
            assert request('/api/v1/auth/register',{'email':f'{identity}@example.com','password':'Synthetic staging password 2026!','display_name':'Staging fixture'})[0]==201
            status,body,headers=request('/api/v1/auth/login',{'email':f'{identity}@example.com','password':'Synthetic staging password 2026!'})
            assert status==200 and '__Host-evidenceai_session=' in headers['Set-Cookie'] and 'Secure' in headers['Set-Cookie'] and 'HttpOnly' in headers['Set-Cookie']
            assert request('/api/v1/auth/logout',body=b'',method='POST',headers={'Origin':origin})[0]==403
            assert request('/api/v1/auth/logout',body=b'',method='POST',headers={'Origin':'https://evil.invalid','X-CSRF-Protection':'1'})[0]==403
            _,body,_=request('/api/v1/workspaces/',{'name':'Synthetic staging recovery'})
            workspace=json.loads(body)['id']
            boundary='M11'+identity
            document=b'Solar panels convert sunlight into renewable electricity.'
            multipart=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode()+document+f'\r\n--{boundary}--\r\n'.encode())
            status,body,_=request(f'/api/v1/workspaces/{workspace}/documents/',multipart,headers={'Origin':origin,'X-CSRF-Protection':'1','Content-Type':'multipart/form-data; boundary='+boundary})
            assert status==202
            saved=json.loads(body);document_id=saved['id']
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                _,body,_=request(f'/api/v1/workspaces/{workspace}/documents/{document_id}')
                if json.loads(body)['processing_status']=='completed': break
                time.sleep(.5)
            else: raise AssertionError('Worker did not process the fixture')
            status,body,_=request(f'/api/v1/workspaces/{workspace}/documents/{document_id}/download')
            assert status==200 and body==document
            search_deadline=time.monotonic()+30
            while time.monotonic()<search_deadline:
                status,body,_=request(f'/api/v1/workspaces/{workspace}/search',{'query':'solar panels convert'})
                if status==200 and json.loads(body): break
                time.sleep(.5)
            else: raise AssertionError('Embedding/search fixture did not become ready')
            status,body,headers=request(f'/api/v1/workspaces/{workspace}/ask',{'question':'Solar panels convert','document_ids':[document_id]})
            answer=json.loads(body)
            assert status==200 and answer['status']=='answered' and answer['request_id']==headers['X-Request-ID']
            report['embedding_rag']='fake/mock indexed retrieval and cited answer passed'
            report['https_cookie_csrf_routing_storage_worker']='passed'
            for service in ('api','worker','web'):
                uid=compose('exec','-T',service,'id','-u',capture=True).strip()
                assert uid=='10001';report[service+'_uid']=uid
            role_check="from app.container_entrypoint import configure; configure(); from app.db.session import get_engine; from sqlalchemy import text; c=get_engine().connect(); row=c.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user')).one(); assert not any(row); c.close()"
            compose('exec','-T','api','python','-c',role_check)
            report['database_role']='non-superuser; no create database or roles'
            readonly_check="from pathlib import Path; p=Path('/app/forbidden-write');\ntry: p.write_text('test'); raise AssertionError()\nexcept OSError as e: assert e.errno==30"
            compose('exec','-T','api','python','-c',readonly_check)
            report['read_only_root']='enforced'
            # Request forgery directly to API must not make an untrusted HTTP peer HTTPS.
            check="import urllib.request,urllib.error; r=urllib.request.Request('http://api:8000/api/v1/auth/logout',data=b'',headers={'Origin':'https://localhost:18443','X-CSRF-Protection':'1','X-Forwarded-Proto':'https'});\ntry: urllib.request.urlopen(r); raise AssertionError()\nexcept urllib.error.HTTPError as e: assert e.code==403"
            compose('exec','-T','worker','python','-c',check)
            # Real internal scrape, without exposing operator endpoints through the proxy.
            check="import urllib.request,pathlib; token=pathlib.Path('/run/secrets/operations_token').read_text().strip(); req=urllib.request.Request('http://api:8000/api/v1/ops/metrics',headers={'Authorization':'Bearer '+token}); data=urllib.request.urlopen(req).read(); assert b'evidenceai_database_up 1' in data"
            compose('exec','-T','api','python','-c',check)
            scrape_check="import urllib.request,json,time; end=time.monotonic()+45;\nwhile time.monotonic()<end:\n data=json.load(urllib.request.urlopen('http://prometheus:9090/api/v1/targets',timeout=5))['data']['activeTargets'];\n if len(data)==2 and all(t['health']=='up' for t in data): break\n time.sleep(1)\nelse: raise AssertionError('Internal scrape targets not healthy')"
            compose('exec','-T','api','python','-c',scrape_check)
            report['prometheus_targets']='API and worker exporter up'
            compose('stop','proxy','api','worker')
            output=compose('run','--rm','--no-deps','-e','QUIESCED=1','backup',capture=True)
            backup=json.loads(output.strip().splitlines()[-1]);report['backup']=backup
            compose('--profile','recovery','up','-d','--wait','restore-db')
            output=compose('--profile','recovery','run','--rm','--no-deps','-e','BACKUP_FILE='+backup['file'],'restore-verify',capture=True)
            report['restore']=json.loads(output.strip().splitlines()[-1])
            try:
                compose('--profile','recovery','run','--rm','--no-deps','-e','BACKUP_FILE='+backup['file'],'restore-verify',capture=True)
            except subprocess.CalledProcessError: report['nonempty_restore_target_rejected']=True
            else: raise AssertionError('Restore overwrote a nonempty target')
            compose('--profile','recovery','stop','restore-db');compose('--profile','recovery','rm','-f','restore-db')
            compose('--profile','recovery','up','-d','--wait','restore-db')
            damaged=backup['file'].rsplit('-',1)[0]+'-'+uuid.uuid4().hex+'.tar.age'
            corrupt="from pathlib import Path; import sys; data=bytearray((Path('/backups')/sys.argv[1]).read_bytes()); data[-1]^=1; p=Path('/backups')/sys.argv[2]; p.write_bytes(data); p.chmod(0o600)"
            compose('run','--rm','--no-deps','--entrypoint','python','backup','-c',corrupt,backup['file'],damaged)
            try:
                compose('--profile','recovery','run','--rm','--no-deps','-e','BACKUP_FILE='+damaged,'restore-verify',capture=True)
            except subprocess.CalledProcessError: report['tampered_ciphertext_rejected']=True
            else: raise AssertionError('Tampered ciphertext was accepted')
            report['graceful_shutdown']='compose stop completed for proxy/API/worker'
            Path('/tmp/evidenceai-m11-smoke-result.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
        except Exception:
            compose('logs','--no-color','--tail','40','api','worker','proxy','prometheus','grafana')
            raise
        finally:
            # Never --volumes/-v: this fixture uses bind mounts and tmpfs exclusively.
            try: compose('--profile','monitoring','--profile','recovery','down','--remove-orphans')
            finally:
                owner=f"import os; root='/fixture'; uid={os.getuid()}; gid={os.getgid()}; [(os.chown(p,uid,gid),os.chmod(p,0o700)) for p in [root]+[os.path.join(d,n) for d,ds,fs in os.walk(root) for n in ds+fs]]"
                run(['docker','run','--rm','--network','none','--user','0','--entrypoint','python','-v',str(directory)+':/fixture','evidenceai-api:m11','-c',owner])


if __name__=='__main__': main()
