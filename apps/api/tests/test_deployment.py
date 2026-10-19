"""Deployment security defaults and guardrails; no Docker or public services required."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('deployment',ROOT/'infra/scripts/deploy.py')
deployment=importlib.util.module_from_spec(spec);spec.loader.exec_module(deployment)


@pytest.fixture
def deployment_env(tmp_path):
    secrets=tmp_path/'secrets';secrets.mkdir(mode=0o700)
    for name in ('db_password','postgres_password','operations_token','grafana_password'):
        (secrets/name).write_text('synthetic-secret-'+'a'*32)
    (secrets/'provider_key').write_text('')
    (secrets/'age_identity').write_text('AGE-SECRET-KEY-SYNTHETIC-ONLY')
    values={'DEPLOY_PROJECT':'evidenceai-staging-test','SITE_HOST':'localhost','PUBLIC_ORIGIN':'https://localhost:18443',
        'ACME_EMAIL':'operator@example.invalid','API_IMAGE':'evidenceai-api:test','WEB_IMAGE':'evidenceai-web:test',
        'BACKUP_IMAGE':'evidenceai-backup:test','PROXY_IMAGE':'evidenceai-proxy:test','SECRETS_DIR':str(secrets),'AGE_RECIPIENT':'age1'+'a'*58}
    def write(changes=None):
        path=tmp_path/'deployment.env';actual={**values,**(changes or {})}
        path.write_text('\n'.join(k+'='+v for k,v in actual.items()))
        return path
    return write,values


def test_staging_validates_without_rendering_secrets(deployment_env):
    write,values=deployment_env
    assert deployment.configuration(write(),'staging')==values


@pytest.mark.parametrize('changes',[
    {'DEPLOY_PROJECT':'infra'}, {'PUBLIC_ORIGIN':'http://localhost:18443'},
    {'PUBLIC_ORIGIN':'https://evil.invalid'}, {'PUBLIC_ORIGIN':'https://localhost/path'},
    {'AUTH_ALLOW_INSECURE_HTTP':'true'}, {'API_IMAGE':'REPLACE_WITH_IMAGE'},
    {'AGE_RECIPIENT':'invalid'}, {'BACKUP_RETENTION_DAYS':'0'},
])
def test_invalid_deployment_rejected(deployment_env,changes):
    write,_=deployment_env
    with pytest.raises(ValueError): deployment.configuration(write(changes),'staging')


def test_weak_or_public_secret_directory_rejected(deployment_env):
    write,values=deployment_env
    path=write();directory=Path(values['SECRETS_DIR']);directory.chmod(0o755)
    with pytest.raises(ValueError): deployment.configuration(path,'staging')
    directory.chmod(0o700);(directory/'db_password').write_text('weak')
    with pytest.raises(ValueError): deployment.configuration(path,'staging')


def test_production_requires_digests_and_dns(deployment_env):
    write,_=deployment_env
    values={'DEPLOY_PROJECT':'evidenceai-production','SITE_HOST':'evidenceai.example.com',
        'PUBLIC_ORIGIN':'https://evidenceai.example.com','ACME_EMAIL':'operator@example.com'}
    with pytest.raises(ValueError): deployment.configuration(write(values),'production')
    values.update({key:'registry.example.com/evidenceai@sha256:'+'a'*64 for key in ('API_IMAGE','WEB_IMAGE','BACKUP_IMAGE','PROXY_IMAGE')})
    assert deployment.configuration(write(values),'production')['DEPLOY_PROJECT']=='evidenceai-production'


def test_container_secret_handling_is_bounded(tmp_path):
    from app.container_entrypoint import read_secret
    path=tmp_path/'secret';path.write_text('x'*64+'\n')
    assert read_secret(path)=='x'*64
    path.write_text('')
    assert read_secret(path,required=False) is None
    with pytest.raises(ValueError,match='Required secret file unavailable'): read_secret(path)
    path.write_text('PRIVATE'+'x'*9000)
    with pytest.raises(ValueError): read_secret(path)


def test_container_security_policy_fails_closed(monkeypatch,tmp_path):
    from app import container_entrypoint as entry
    import app.core.config as config
    settings=SimpleNamespace(app_env='development',auth_allow_insecure_http=True)
    def fake(): return settings
    fake.cache_clear=lambda:None
    monkeypatch.setattr(config,'get_settings',fake)
    for name in ('DATABASE_PASSWORD_FILE','OPERATIONS_TOKEN_FILE','OPENAI_API_KEY_FILE'):
        monkeypatch.delenv(name,raising=False)
    with pytest.raises(entry.StartupError,match='security_policy'): entry.configure()


def test_production_compose_never_reuses_dev_volume():
    import yaml
    text=(ROOT/'infra/compose.production.yml').read_text()
    # Base file has ordinary YAML; the staging overlay uses explicit Compose tags.
    config=yaml.safe_load(text)
    assert set(config['services']['proxy']['ports'])=={'80:8080','443:8443'}
    assert all('ports' not in service for name,service in config['services'].items() if name!='proxy')
    assert 'evidenceai_pgdata' not in text and 'docker.sock' not in text
    assert config['networks']['database']['internal']
    assert config['networks']['monitoring']['internal']
    assert config['services']['api']['read_only']
    assert config['services']['db']['user']=='999:999'


def test_restore_guard_rejects_non_disposable_targets(monkeypatch):
    spec=importlib.util.spec_from_file_location('backup',ROOT/'infra/backup/backup.py')
    backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)
    monkeypatch.setenv('PGHOST','db');monkeypatch.setenv('PGDATABASE','evidenceai')
    with pytest.raises(ValueError,match='disposable'): backup.restore()
    monkeypatch.setenv('PGHOST','restore-db');monkeypatch.setenv('PGDATABASE','restorecheck')
    monkeypatch.setenv('BACKUP_FILE','../../private')
    with pytest.raises(ValueError,match='exact encrypted'): backup.restore()


def test_migration_refuses_live_writers():
    instance=object.__new__(deployment.Deployment)
    calls=[]
    def compose(*args,**kwargs):
        calls.append(args)
        return 'api\nworker\n' if args[0]=='ps' else ''
    instance.compose=compose
    with pytest.raises(ValueError,match='Stop API'): instance.migrate()
    assert len(calls)==1


def test_rollout_requires_previous_release_reference():
    instance=object.__new__(deployment.Deployment)
    instance.args=SimpleNamespace(previous_env=None)
    with pytest.raises(ValueError,match='previous-env'): instance.rollout()


def test_restore_key_not_needed_for_normal_start(deployment_env):
    write,values=deployment_env
    (Path(values['SECRETS_DIR'])/'age_identity').unlink()
    assert deployment.configuration(write(),'staging')
    with pytest.raises(ValueError): deployment.configuration(write(),'staging',recovery=True)



def test_rollout_migrates_before_any_new_writer_start(monkeypatch):
    instance=object.__new__(deployment.Deployment)
    instance.args=SimpleNamespace(previous_env=Path('/synthetic/previous.env'),environment='staging')
    instance.values={'DEPLOY_PROJECT':'evidenceai-staging','SECRETS_DIR':'/synthetic','PUBLIC_ORIGIN':'https://localhost'}
    monkeypatch.setattr(deployment,'configuration',lambda *args,**kwargs:instance.values)
    calls=[]
    def compose(*args,**kwargs): calls.append(args);return ''
    instance.compose=compose
    instance.backup=lambda **kwargs:calls.append(('backup',kwargs['restart']))
    instance.ready=lambda:calls.append(('ready',))
    instance.rollout()
    assert ('backup',False) in calls
    migration=next(i for i,item in enumerate(calls) if item==('run','--rm','migrate'))
    assert all(item[0]!='up' for item in calls[:migration])
    assert calls[-1]==('ready',)


def test_release_packaging_rejects_dirty_source(monkeypatch,tmp_path):
    import sys
    spec=importlib.util.spec_from_file_location('release',ROOT/'infra/scripts/release_manifest.py')
    release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
    monkeypatch.setattr(release,'output',lambda *_:' M application.py')
    monkeypatch.setattr(sys,'argv',['release','--output',str(tmp_path/'manifest.json')])
    with pytest.raises(SystemExit,match='clean committed'): release.main()
    assert not (tmp_path/'manifest.json').exists()


def test_release_acceptance_missing_or_failed_evidence_blocks():
    spec=importlib.util.spec_from_file_location('acceptance',ROOT/'infra/scripts/verify_release.py')
    acceptance=importlib.util.module_from_spec(spec);spec.loader.exec_module(acceptance)
    complete={name:'PASS' for name in acceptance.REQUIRED}
    assert acceptance.decision(complete)['release']=='PASS'
    for status in ('FAIL','NOT VERIFIED'):
        assert acceptance.decision({**complete,'container_security':status})['release']=='BLOCKED'
    assert acceptance.decision({})['release']=='BLOCKED'
    with pytest.raises(ValueError): acceptance.decision({'container_security':'WAIVED'})


@pytest.mark.parametrize('destination',['/data/documents','/documents','../../originals','/tmp/restored-documents'])
def test_recovery_documents_cannot_target_application_storage(monkeypatch,destination):
    spec=importlib.util.spec_from_file_location('backup',ROOT/'infra/backup/backup.py')
    backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)
    monkeypatch.setenv('RESTORE_DOCUMENTS_TO',destination)
    with pytest.raises(ValueError,match='empty isolated mount'): backup.recovery_directory()
    monkeypatch.delenv('RESTORE_DOCUMENTS_TO')
    assert backup.recovery_directory() is None
