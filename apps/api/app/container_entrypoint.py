"""Container-only secret injection and startup validation; no migration on API start."""
import os
from pathlib import Path
import sys
from sqlalchemy.engine import URL


def read_secret(path, *, required=True):
    try:
        value=Path(path).read_text().strip()
        if not value or len(value)>8192 or '\x00' in value: raise ValueError()
        return value
    except (OSError,ValueError):
        if required: raise ValueError('Required secret file unavailable') from None
        return None


class StartupError(Exception):
    pass


def configure():
    stage='secret_files'
    try:
        if os.environ.get('DATABASE_PASSWORD_FILE'):
            password=read_secret(os.environ['DATABASE_PASSWORD_FILE'])
            if len(password)<32: raise ValueError('Database password must contain at least 32 characters')
            os.environ['DATABASE_URL']=URL.create('postgresql+psycopg',username='evidenceai',password=password,
                host=os.environ.get('DATABASE_HOST','db'),port=5432,database='evidenceai').render_as_string(hide_password=False)
        for name in ('OPERATIONS_TOKEN','OPENAI_API_KEY','SMTP_PASSWORD'):
            if os.environ.get(name+'_FILE'):
                value=read_secret(os.environ[name+'_FILE'],required=name=='OPERATIONS_TOKEN')
                if value: os.environ[name]=value
        stage='settings'
        from app.core.config import get_settings
        get_settings.cache_clear()
        settings=get_settings()
        stage='security_policy'
        if settings.app_env not in {'staging','production'} or settings.auth_allow_insecure_http:
            raise ValueError('Container runtime requires staging/production HTTPS authentication')
        if not settings.operations_token: raise ValueError('Operator token required for deployment')
        if not settings.database_url.get_secret_value().startswith('postgresql+psycopg://evidenceai:'):
            raise ValueError('Container runtime requires the dedicated application database role')
        import ipaddress
        proxy=ipaddress.ip_address(os.environ.get('TRUSTED_PROXY_IP','172.30.11.10'))
        if not proxy.is_private or proxy.is_unspecified or proxy.is_loopback:
            raise ValueError('One explicit private proxy address required')
        stage='storage_permissions'
        from app.services.document_storage import LocalDocumentStorage
        LocalDocumentStorage(settings.document_storage_root)
        return settings

    except Exception as error:
        from pydantic import ValidationError
        if isinstance(error,ValidationError):
            # Location/type only: never echo inputs, validator context or secret values.
            fields=','.join('.'.join(map(str,item['loc']))+':'+item['type'] for item in error.errors())
            stage+=' ('+fields+')'
        raise StartupError(stage) from None


def main():
    try:
        configure()
        mode=sys.argv[1] if len(sys.argv)>1 else 'api'
        commands={
            'api':[sys.executable,'-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000',
                '--workers','1','--proxy-headers','--forwarded-allow-ips',os.environ.get('TRUSTED_PROXY_IP','172.30.11.10'),
                '--timeout-keep-alive','5','--timeout-graceful-shutdown','150','--no-access-log'],
            'worker':[sys.executable,'-m','app.document_worker','--metrics-file','/metrics/worker.prom'],
            'migrate':[sys.executable,'-m','alembic','upgrade','head'],
            'status':[sys.executable,'-m','app.operations'],
            'alembic-current':[sys.executable,'-m','alembic','current'],
            'alembic-check':[sys.executable,'-m','alembic','check'],
            'check':[sys.executable,'-m','app.operations','--readiness'],
        }
        if mode=='validate': print('Container configuration valid');return
        if mode not in commands: raise ValueError('Unknown container operation')
        os.execv(sys.executable,commands[mode])
    except StartupError as error:
        print('Container startup rejected at '+str(error)+'; inspect private configuration',file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print('Container startup rejected: check private configuration, secrets and storage permissions',file=sys.stderr)
        raise SystemExit(1) from None


if __name__=='__main__': main()
