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
M12=os.environ.get('EVIDENCEAI_ACCEPTANCE')=='1'
TAG=os.environ.get('EVIDENCEAI_IMAGE_TAG','m121')
def image(name): return 'evidenceai-'+name+':'+TAG


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
        (private/'smtp_password').write_text('');(private/'smtp_password').chmod(0o444)
        key=run(['docker','run','--rm','--network','none','--entrypoint','age-keygen',image('backup')],stdout=subprocess.PIPE,stderr=subprocess.PIPE).decode()
        (private/'age_identity').write_text(key);(private/'age_identity').chmod(0o444)
        recipient=next(line.split(': ',1)[1] for line in key.splitlines() if line.startswith('# public key:'))
        values={'DEPLOY_PROJECT':project,'SITE_HOST':'localhost','PUBLIC_ORIGIN':'https://localhost:18443',
            'ACME_EMAIL':'local@example.invalid','PROMETHEUS_IMAGE':image('prometheus'),'EXPORTER_IMAGE':image('exporter'),'DATABASE_IMAGE':image('database'),'API_IMAGE':image('api'),'WEB_IMAGE':image('web'),
            'BACKUP_IMAGE':image('backup'),'PROXY_IMAGE':image('proxy'),'SECRETS_DIR':str(private),'AGE_RECIPIENT':recipient,
            'EMBEDDING_PROVIDER':'fake','LLM_PROVIDER':'mock'}
        envfile=directory/'stage.env';envfile.write_text('\n'.join(k+'='+v for k,v in values.items())+'\n')
        names=('documents','metrics','proxy','backups','prometheus','grafana','restored','mail')
        for name in names: (directory/name).mkdir()
        # Only synthetic temporary directories are touched by this bounded ownership helper.
        helper="import os; base='/fixture'; [os.chown(base+'/'+n,10001,10001) or os.chmod(base+'/'+n,0o700) for n in ['documents','metrics','proxy','backups','restored','mail']]; os.chown(base+'/prometheus',65534,65534); os.chown(base+'/grafana',472,0)"
        run(['docker','run','--rm','--network','none','--user','0','--entrypoint','python','-v',str(directory)+':/fixture',image('api'),'-c',helper])
        run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(directory/'mail/key.pem'),'-out',str(directory/'mail/cert.pem'),'-subj','/CN=mail','-addext','subjectAltName=DNS:mail','-days','1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for filename in ('key.pem','cert.pem'): (directory/'mail'/filename).chmod(0o444)
        def mount(name,target,ro=''): return json.dumps(str(directory/name)+':'+target+ro)
        override=directory/'smoke.yml'
        override.write_text(f'''services:
  db:
    volumes: !override ["{ROOT}/infra/deploy/init-db.sh:/docker-entrypoint-initdb.d/10-evidenceai.sh:ro"]
    tmpfs: !override ["/var/lib/postgresql/data:rw,nosuid,size=512m,uid=999,gid=999", "/var/run/postgresql:rw,nosuid,size=16m,uid=999,gid=999", "/tmp:rw,nosuid,size=32m,uid=999,gid=999"]
  api:
    volumes: !override [{mount('documents','/data/documents')}, {mount('mail/cert.pem','/smtp-ca.pem',':ro')}]
    environment: {{TRUSTED_PROXY_IP: 172.30.31.10, REGISTRATION_EMAIL_ENABLED: 'true', SMTP_HOST: mail, SMTP_PORT: '1465', SMTP_SENDER: noreply@example.invalid, SMTP_CA_FILE: /smtp-ca.pem}}
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
    volumes: !override [{mount('grafana','/var/lib/grafana')}, "{ROOT}/infra/deploy/grafana/provisioning:/etc/grafana/provisioning:ro", "{ROOT}/infra/monitoring/grafana/evidenceai.json:/etc/grafana/dashboards/evidenceai.json:ro"]
  mail:
    image: python:3.14.6-alpine@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92
    user: '10001:10001'
    command: [python, /smtp_sink.py]
    read_only: true
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    mem_limit: 128m
    networks: [application]
    volumes: [{mount('mail','/mail')}, "{ROOT}/infra/testing/smtp_sink.py:/smtp_sink.py:ro"]
  worker-exporter:
    volumes: !override [{mount('metrics','/metrics',':ro')}]
networks:
  application:
    ipam:
      config: !override [{{subnet: 172.30.31.0/24}}]
volumes: !reset {{}}
''')
        if M12:
            override.write_text(override.read_text().replace("  restore-verify:\n    volumes: !override ["+mount('backups','/backups',':ro')+"]",
                "  restore-verify:\n    environment: {RESTORE_DOCUMENTS_TO: /restored-documents}\n    volumes: !override ["+mount('backups','/backups',':ro')+", "+mount('restored','/restored-documents')+"]"))
        command=['docker','compose','--project-name',project,'--env-file',str(envfile),'-f',str(ROOT/'infra/compose.production.yml'),'-f',str(ROOT/'infra/compose.staging.yml'),'-f',str(override)]
        env=os.environ.copy();env.update(values)
        def compose(*args,capture=False):
            return run(command+list(args),env=env,stdout=subprocess.PIPE if capture else None,text=True)
        try:
            compose('config','--quiet')
            run([sys.executable,str(ROOT/'infra/scripts/deploy.py'),'--env-file',str(envfile),'validate'])
            production={**values,'DEPLOY_PROJECT':'evidenceai-production-validate'+identity,'SITE_HOST':'evidenceai.example.com','PUBLIC_ORIGIN':'https://evidenceai.example.com','ACME_EMAIL':'operator@example.com'}
            for key in ('API_IMAGE','WEB_IMAGE','BACKUP_IMAGE','PROXY_IMAGE','DATABASE_IMAGE','PROMETHEUS_IMAGE','EXPORTER_IMAGE'): production[key]='registry.example.com/release@sha256:'+'a'*64
            production_env=directory/'production.env';production_env.write_text('\n'.join(k+'='+v for k,v in production.items()))
            run([sys.executable,str(ROOT/'infra/scripts/deploy.py'),'--environment','production','--env-file',str(production_env),'validate'])
            report['compose_validation']='staging and production; production was not started'
            compose('up','-d','--wait','db')
            compose('run','--rm','migrate')
            compose('up','-d','--wait','mail','api','worker','web','proxy')
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
            registration={'email':f'{identity}@example.com','password':'Synthetic staging password 2026!','display_name':'Staging fixture'}
            first=request('/api/v1/auth/register',registration)
            assert first[0]==202
            assert request('/api/v1/auth/login',{'email':registration['email'],'password':registration['password']})[0]==401
            filename=hashlib.sha256(registration['email'].encode()).hexdigest()+'.json'
            proof=compose('exec','-T','mail','python','-c',"from pathlib import Path; import sys; print((Path('/mail')/sys.argv[1]).read_text())",filename,capture=True)
            token=json.loads(proof)['token']
            assert request('/api/v1/auth/verify-registration',{'token':token})[0]==202
            duplicate=request('/api/v1/auth/register',registration)
            assert duplicate[0]==first[0] and duplicate[1]==first[1]
            report['registration']='Uniform 202, pre-verification login refused, real TLS SMTP fixture delivery and browser-bound verification passed'

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
            if M12:
                import acceptance
                acceptance.OUT=ROOT/'infra/runtime'/TAG
                from acceptance import load
                report['load']=load(directory,project,compose,{'origin':origin,'project':project,'ca':str(ca),
                    'email':f'{identity}@example.com','password':'Synthetic staging password 2026!',
                    'workspace':workspace,'document':document_id})
            if M12:
                compose('stop','worker')
                queued_multipart=multipart.replace(document,document+b' Unique recovery fixture.')
                status,queued,_=request(f'/api/v1/workspaces/{workspace}/documents/',queued_multipart,headers={'Origin':origin,'X-CSRF-Protection':'1','Content-Type':'multipart/form-data; boundary='+boundary})
                assert status==202
                queued_id=json.loads(queued)['id']
                last_write=time.time()
            recovery_started=time.monotonic()
            compose('stop','proxy','api','worker')
            output=compose('run','--rm','--no-deps','-e','QUIESCED=1','backup',capture=True)
            backup=json.loads(output.strip().splitlines()[-1]);report['backup']=backup
            if M12: backup_window=round(time.time()-last_write,3)
            compose('--profile','recovery','up','-d','--wait','restore-db')
            output=compose('--profile','recovery','run','--rm','--no-deps','-e','BACKUP_FILE='+backup['file'],'restore-verify',capture=True)
            report['restore']=json.loads(output.strip().splitlines()[-1])
            if M12:
                # Only this fixture's disposable restore-db is promoted for application verification.
                password=(private/'db_password').read_text().strip()
                sql=("ALTER DATABASE restorecheck RENAME TO evidenceai; CREATE ROLE evidenceai LOGIN PASSWORD '"+password+"';")
                run(command+['exec','-T','restore-db','psql','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],env=env,input=sql,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                sql='GRANT CONNECT ON DATABASE evidenceai TO evidenceai; GRANT USAGE ON SCHEMA public TO evidenceai; GRANT ALL ON ALL TABLES IN SCHEMA public TO evidenceai; GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO evidenceai;'
                run(command+['exec','-T','restore-db','psql','-U','postgres','-d','evidenceai','-v','ON_ERROR_STOP=1'],env=env,input=sql,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                recovery_override=directory/'recovery-app.yml'
                recovery_override.write_text(f'''services:
  api:
    environment: {{DATABASE_HOST: restore-db}}
    networks: !override [application, monitoring, recovery, egress]
    volumes: !override [{mount('restored','/data/documents')}, {mount('mail/cert.pem','/smtp-ca.pem',':ro')}]
  worker:
    environment: {{DATABASE_HOST: restore-db}}
    networks: !override [monitoring, recovery, egress]
    volumes: !override [{mount('restored','/data/documents')}, {mount('metrics','/metrics')}]
''')
                command.extend(['-f',str(recovery_override)])
                compose('up','-d','--wait','api','worker','proxy')
                assert request('/api/v1/auth/me')[0]==200  # Restored existing session, not a new identity.
                assert request('/api/v1/auth/login',{'email':f'{identity}@example.com','password':'Synthetic staging password 2026!'})[0]==200
                status,restored,_=request(f'/api/v1/workspaces/{workspace}/documents/{document_id}/download')
                assert status==200 and restored==document
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    status,body,_=request(f'/api/v1/workspaces/{workspace}/documents/{queued_id}')
                    if status==200 and json.loads(body)['processing_status']=='completed': break
                    time.sleep(.5)
                else: raise AssertionError('Restored pending queue did not recover')
                status,body,_=request(f'/api/v1/workspaces/{workspace}/documents/{queued_id}/download')
                assert status==200 and body==document+b' Unique recovery fixture.'
                report['recovery_application']={'authenticated_session':'PASS','fresh_login':'PASS','original_download':'PASS',
                    'pending_queue_recovery':'PASS','queued_document_download':'PASS',
                    'measured_recovery_seconds':round(time.monotonic()-recovery_started,3),
                    'last_write_to_backup_complete_seconds':backup_window,
                    'data_loss':'0 acknowledged synthetic writes; writers quiesced; local fixture only'}
                previous=os.environ.get('EVIDENCEAI_ROLLBACK_IMAGE')
                if previous:
                    if previous!='evidenceai-api:m11': raise ValueError('Only the local baseline candidate is permitted in this drill')
                    current=recovery_override.read_text()
                    rollback_started=time.monotonic()
                    recovery_override.write_text(current.replace('  api:\n','  api:\n    image: '+previous+'\n').replace('  worker:\n','  worker:\n    image: '+previous+'\n'))
                    compose('run','--rm','--no-deps','api','check')
                    compose('stop','proxy','api','worker')
                    compose('up','-d','--wait','api','worker','proxy')
                    assert request('/api/v1/auth/me')[0]==200
                    assert request(f'/api/v1/workspaces/{workspace}/documents/{document_id}/download')[1]==document
                    report['rollback']={'status':'PASS','scope':'Local backend/worker candidate compatibility only; M11 is not an accepted production release',
                        'previous_image':previous,'seconds_to_baseline_ready':round(time.monotonic()-rollback_started,3),
                        'session_and_download':'PASS','schema_downgrade':False}
                    recovery_override.write_text(current)
                    compose('stop','proxy','api','worker')
                    compose('up','-d','--wait','api','worker','proxy')
                    assert request('/api/v1/auth/me')[0]==200
                    report['rollback']['return_to_current_candidate']='PASS'
                else:
                    report['rollback']={'status':'NOT VERIFIED','reason':'No previous candidate image supplied; no accepted production release exists'}
                compose('stop','proxy','api','worker')
                command[-2:]=[]
                run(command+['exec','-T','restore-db','psql','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],env=env,
                    input='ALTER DATABASE evidenceai RENAME TO restorecheck;',text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
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
            if M12:
                stopped={}
                for service in ('api','worker','proxy'):
                    identifier=compose('ps','-aq',service,capture=True).strip()
                    state=json.loads(run(['docker','inspect','--format','{{json .State}}',identifier],stdout=subprocess.PIPE,text=True))
                    assert not state['OOMKilled'] and state['ExitCode']!=137
                    stopped[service]={'exit_code':state['ExitCode'],'oom_killed':state['OOMKilled']}
                report['shutdown_states']=stopped
            report['graceful_shutdown']='compose stop completed for proxy/API/worker'
            Path('/tmp/evidenceai-'+TAG+'-smoke-result.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
            if M12:
                assert report['load']['status']=='PASS', 'Performance acceptance failed; evidence retained'
                assert report['recovery_application']['measured_recovery_seconds']<=report['load']['thresholds']['recovery_seconds_max'], 'Recovery duration exceeded proposed threshold'
        except Exception:
            compose('logs','--no-color','--tail','40','api','worker','proxy','prometheus','grafana')
            raise
        finally:
            # Never --volumes/-v: this fixture uses bind mounts and tmpfs exclusively.
            try: compose('--profile','monitoring','--profile','recovery','down','--remove-orphans')
            finally:
                owner=f"import os; root='/fixture'; uid={os.getuid()}; gid={os.getgid()}; [(os.chown(p,uid,gid),os.chmod(p,0o700)) for p in [root]+[os.path.join(d,n) for d,ds,fs in os.walk(root) for n in ds+fs if not os.path.join(d,n).startswith(root+'/secrets') and os.path.join(d,n) not in (root+'/mail/key.pem',root+'/mail/cert.pem')]]"
                run(['docker','run','--rm','--network','none','--user','0','--entrypoint','python','-v',str(directory)+':/fixture',image('api'),'-c',owner])


if __name__=='__main__': main()
