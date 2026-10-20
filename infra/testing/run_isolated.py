#!/usr/bin/env python3
"""Run a command against a uniquely owned tmpfs PostgreSQL/pgvector container.

Example: apps/api/.venv/bin/python infra/testing/run_isolated.py -- apps/api/.venv/bin/python -m pytest apps/api/tests
No development database is contacted. Only the generated container is removed.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
IMAGE='evidenceai-database:m121'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-directory',type=Path,default=ROOT/'infra/runtime/isolated-tests')
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args();command=args.command
    if command[:1]==['--']:command=command[1:]
    if not command:parser.error('Command required')
    output=args.evidence_directory.resolve();output.mkdir(parents=True,exist_ok=True)
    suffix=uuid.uuid4().hex;name='evidenceai-test-'+suffix;database='evidenceai_test_'+suffix
    image_id=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',IMAGE],text=True).strip()
    password=secrets.token_urlsafe(32);env=os.environ.copy()
    created=False;record={'container':name,'database':database,'storage':'owned tmpfs; no host development mounts','command':command,'image':IMAGE,'immutable_local_image':image_id}
    with tempfile.TemporaryDirectory(prefix='evidenceai-test-db-') as temporary:
        envfile=Path(temporary)/'database.env'
        envfile.write_text(f'POSTGRES_USER=test_runner\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB={database}\n');envfile.chmod(0o600)
        try:
            subprocess.run(['docker','run','-d','--name',name,'--label','com.evidenceai.disposable-test='+suffix,
                '--tmpfs','/var/lib/postgresql/data:rw,noexec,nosuid,size=512m,uid=999,gid=999,mode=0700','-p','127.0.0.1::5432',
                '--env-file',str(envfile),image_id],check=True,stdout=subprocess.DEVNULL)
            created=True
            port=json.loads(subprocess.check_output(['docker','inspect',name]))[0]['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort']
            url=f'postgresql+psycopg://test_runner:{password}@127.0.0.1:{port}/{database}'
            from sqlalchemy import create_engine,text
            engine=create_engine(url,hide_parameters=True,connect_args={'connect_timeout':2})
            deadline=time.monotonic()+45
            while True:
                try:
                    with engine.begin() as connection:
                        assert connection.scalar(text('select current_database()'))==database
                        connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                    break
                except Exception:
                    if time.monotonic()>deadline:raise RuntimeError('Disposable database readiness timed out') from None
                    time.sleep(.25)
            engine.dispose()
            env['EVIDENCEAI_TEST_DATABASE_URL']=url;env['DATABASE_URL']=url;env['APP_ENV']='test'
            with (output/'migration.log').open('w') as log:
                subprocess.run([str(ROOT/'apps/api/.venv/bin/python'),'-m','alembic','upgrade','head'],cwd=ROOT/'apps/api',env=env,stdout=log,stderr=log,check=True)
            result=subprocess.run(command,cwd=ROOT,env=env)
            record['exit_code']=result.returncode
            # All pytest/browser scratch schemas must already have cleaned themselves.
            engine=create_engine(url,hide_parameters=True)
            with engine.connect() as connection:
                record['remaining_test_schemas']=connection.scalar(text("select count(*) from pg_namespace where nspname ~ '^(test_suite_|test_workspace_|e2e_web_|eval_rag_|eval_retrieval_)'"))
                record['public_users']=connection.scalar(text('select count(*) from public.users'))
                record['public_registration_intents']=connection.scalar(text('select count(*) from public.registration_intents'))
                record['public_limiter_rows']=connection.scalar(text('select count(*) from public.auth_rate_limits'))
            engine.dispose()
            record['isolation_clean']=all(record[key]==0 for key in ['remaining_test_schemas','public_users','public_registration_intents','public_limiter_rows'])
            return result.returncode if record['isolation_clean'] else 1
        except BaseException as error:
            record['failure_type']=type(error).__name__
            raise
        finally:
            if created:
                actual=subprocess.check_output(['docker','inspect','--format','{{index .Config.Labels "com.evidenceai.disposable-test"}}',name],text=True).strip()
                if actual!=suffix:raise RuntimeError('Refusing cleanup: ownership mismatch')
                subprocess.run(['docker','rm','-f',name],check=True,stdout=subprocess.DEVNULL)
                record['owned_container_removed']=True
            (output/'isolation.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':raise SystemExit(main())
