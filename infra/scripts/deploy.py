#!/usr/bin/env python3
"""Explicit, fail-closed single-host deployment operations. Never deletes volumes."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]


def configuration(path, environment, *, recovery=False):
    values={}
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        key,separator,value=line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key) or key in values:
            raise ValueError('Malformed or duplicate deployment setting')
        values[key]=value.strip()
    required=('DEPLOY_PROJECT','SITE_HOST','PUBLIC_ORIGIN','ACME_EMAIL','API_IMAGE','WEB_IMAGE','BACKUP_IMAGE','PROXY_IMAGE','DATABASE_IMAGE','PROMETHEUS_IMAGE','EXPORTER_IMAGE','SECRETS_DIR','AGE_RECIPIENT')
    if any(not values.get(key) or 'REPLACE' in values[key] for key in required): raise ValueError('Required deployment settings missing')
    if not re.fullmatch('evidenceai-'+environment+r'(-[a-z0-9]+)?',values['DEPLOY_PROJECT']):
        raise ValueError('Project must be a dedicated evidenceai-staging/production name')
    url=urlsplit(values['PUBLIC_ORIGIN'])
    if (url.scheme!='https' or url.hostname!=values['SITE_HOST'] or url.username or url.password or url.path or url.query or url.fragment
            or not re.fullmatch(r'[a-z0-9.-]+',values['SITE_HOST'])): raise ValueError('Explicit matching HTTPS origin/hostname required')
    if environment=='production':
        if url.port not in (None,443) or values['SITE_HOST'].endswith(('.localhost','.invalid')) or values['SITE_HOST']=='localhost':
            raise ValueError('Production requires a public DNS hostname and HTTPS port 443')
        if values['ACME_EMAIL'].endswith('.invalid'): raise ValueError('Production ACME contact required')
        if any(not re.fullmatch(r'.+@sha256:[a-f0-9]{64}',values[key]) for key in ('API_IMAGE','WEB_IMAGE','BACKUP_IMAGE','PROXY_IMAGE','DATABASE_IMAGE','PROMETHEUS_IMAGE','EXPORTER_IMAGE')):
            raise ValueError('Production requires immutable registry image digests')
    if not re.fullmatch(r'age1[a-z0-9]{58}',values['AGE_RECIPIENT']): raise ValueError('Valid age public recipient required')
    retention=int(values.get('BACKUP_RETENTION_DAYS','14'))
    if not 1<=retention<=3650: raise ValueError('Invalid backup retention')
    directory=Path(values['SECRETS_DIR'])
    if directory.resolve()==ROOT or ROOT in directory.resolve().parents: raise ValueError('Secrets must be outside the source checkout')
    if not directory.is_absolute() or not directory.is_dir() or directory.is_symlink(): raise ValueError('Private absolute secrets directory required')
    if directory.stat().st_mode & 0o077: raise ValueError('Secrets directory must be mode 0700')
    for name in ('db_password','postgres_password','operations_token','grafana_password','provider_key','smtp_password') + (('age_identity',) if recovery else ()):
        file=directory/name
        if file.is_symlink() or not file.is_file(): raise ValueError('Required secret file missing')
        value=file.read_text().strip()
        if name not in {'provider_key','smtp_password','age_identity'} and len(value)<32: raise ValueError('Weak or missing secret')
        if name=='age_identity' and 'AGE-SECRET-KEY-' not in value: raise ValueError('Recovery identity is required')
    if values.get('AUTH_ALLOW_INSECURE_HTTP','false').lower()!='false': raise ValueError('Insecure authentication is forbidden')
    return values


@contextmanager
def lock(environment):
    import fcntl
    path=ROOT/'infra'/'runtime'/f'{environment}.lock'
    path.parent.mkdir(mode=0o700,exist_ok=True)
    with path.open('a') as stream:
        try: fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Another deployment/backup operation holds the lock') from None
        yield


class Deployment:
    def __init__(self,args):
        self.args=args
        self.values=configuration(args.env_file,args.environment,recovery=args.action=='restore-verify')
        self.env=os.environ.copy();self.env.update(self.values)
        self.command=['docker','compose','--project-name',self.values['DEPLOY_PROJECT'],'--env-file',str(args.env_file.resolve()),'-f',str(ROOT/'infra/compose.production.yml')]
        if args.environment=='staging': self.command+=['-f',str(ROOT/'infra/compose.staging.yml')]

    def compose(self,*arguments,capture=False):
        result=subprocess.run(self.command+list(arguments),env=self.env,check=True,
            stdout=subprocess.PIPE if capture else None,text=True)
        return result.stdout

    def validate(self):
        self.compose('config','--quiet')
        print('Deployment configuration valid; secrets were not rendered')

    def start(self):
        self.compose('up','-d','--wait','db')
        self.migrate()
        self.compose('up','-d','--wait','api','worker','web','proxy')
        self.ready()

    def migrate(self):
        running=self.compose('ps','--services','--status','running',capture=True).splitlines()
        if any(name in running for name in ('api','worker')):
            raise ValueError('Stop API and worker before the one-time migration; use controlled rollout')
        self.compose('run','--rm','migrate')

    def ready(self): self.compose('exec','-T','api','python','-m','app.container_entrypoint','check')

    def backup(self, *, restart=True):
        running=self.compose('ps','--services','--status','running',capture=True).splitlines()
        writers=[service for service in ('proxy','api','worker') if service in running]
        self.compose('stop',*writers) if writers else None
        try:
            self.compose('run','--rm','--no-deps','-e','QUIESCED=1','backup')
        finally:
            if writers and restart: self.compose('up','-d','--wait',*writers)

    def restore(self):
        # Existing disposable target must be removed explicitly; never overwrite it.
        self.compose('--profile','recovery','up','-d','--wait','restore-db')
        try:
            self.compose('--profile','recovery','run','--rm','--no-deps','-e','BACKUP_FILE='+self.args.backup_file,'restore-verify')
        finally:
            self.compose('--profile','recovery','stop','restore-db')
            self.compose('--profile','recovery','rm','-f','restore-db')

    def rollout(self):
        if not self.args.previous_env: raise ValueError('Rollout requires --previous-env for a reviewable rollback reference')
        previous=configuration(self.args.previous_env,self.args.environment)
        if any(previous[key]!=self.values[key] for key in ('DEPLOY_PROJECT','SECRETS_DIR','PUBLIC_ORIGIN')):
            raise ValueError('Rollout must preserve project, secrets and origin')
        if previous['DATABASE_IMAGE']!=self.values['DATABASE_IMAGE']:
            raise ValueError('Database image changes require a separately reviewed fresh-volume logical migration; app rollout cannot switch database runtimes')
        self.compose('pull','api','web','backup','proxy')
        self.backup(restart=False)
        # Quiesce writers for the one-time migration, then recreate only app services.
        self.compose('stop','proxy','api','worker')
        try:
            self.migrate()
            self.compose('up','-d','--wait','api','worker','web','proxy')
            self.ready()
        except subprocess.CalledProcessError:
            print('Rollout stopped safely. Inspect migration compatibility before explicit application rollback.',file=sys.stderr)
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment',choices=['staging','production'],default='staging')
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--ack-production',action='store_true')
    parser.add_argument('--previous-env',type=Path)
    parser.add_argument('--backup-file',default='')
    parser.add_argument('--export-path',type=Path)
    parser.add_argument('action',choices=['validate','start','migrate','ready','backup','restore-verify','rollout','rollback','diagnostics','monitoring','list-backups','export-backup','stop'])
    args=parser.parse_args()
    try:
        if args.environment=='production' and args.action not in {'validate','diagnostics','ready'} and not args.ack_production:
            raise ValueError('Production changes require explicit --ack-production and release approval')
        deployment=Deployment(args)
        with lock(args.environment):
            deployment.validate()
            if args.action=='validate': return
            if args.action=='start': deployment.start()
            elif args.action=='migrate': deployment.migrate()
            elif args.action=='stop': deployment.compose('stop','proxy','api','worker','web')
            elif args.action=='ready': deployment.ready()
            elif args.action=='backup': deployment.backup()
            elif args.action=='restore-verify': deployment.restore()
            elif args.action=='rollout': deployment.rollout()
            elif args.action=='rollback':
                # This env file must select the last accepted app image digests. No DB downgrade.
                deployment.compose('run','--rm','--no-deps','api','check')
                deployment.compose('stop','proxy','api','worker')
                deployment.compose('up','-d','--wait','--no-deps','api','worker','web','proxy');deployment.ready()
            elif args.action=='list-backups': deployment.compose('run','--rm','--no-deps','backup','list')
            elif args.action=='export-backup':
                if not args.export_path or not args.export_path.is_absolute(): raise ValueError('Explicit absolute encrypted export path required')
                descriptor=os.open(args.export_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                try:
                    with os.fdopen(descriptor,'wb') as stream:
                        subprocess.run(deployment.command+['run','--rm','--no-deps','-e','BACKUP_FILE='+args.backup_file,'backup','export'],env=deployment.env,stdout=stream,check=True)
                except BaseException:
                    args.export_path.unlink(missing_ok=True)
                    raise
            elif args.action=='monitoring': deployment.compose('--profile','monitoring','up','-d','--wait','prometheus','worker-exporter','grafana')
            elif args.action=='diagnostics':
                deployment.compose('ps');deployment.compose('exec','-T','worker','python','-m','app.container_entrypoint','status')
    except (ValueError,OSError,subprocess.CalledProcessError):
        print('Deployment operation failed: validate configuration, private permissions and service status. No volume deletion was requested.',file=sys.stderr)
        raise SystemExit(1) from None


if __name__=='__main__': main()
