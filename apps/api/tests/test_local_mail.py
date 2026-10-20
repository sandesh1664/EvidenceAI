"""Actual verified TLS SMTP + HTTP registration against disposable PostgreSQL."""
import importlib.util
from pathlib import Path
import re
import smtplib
import ssl
import threading
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select, func
from app.core.config import Settings
from app.core.security import hash_token
from app.models import RegistrationIntent, User
from app.services.registration_service import deliver as real_deliver
from test_auth import client, settings, payload  # shared guarded database fixtures

spec = importlib.util.spec_from_file_location('local_mail', Path(__file__).resolve().parents[3] / 'infra/development/mail.py')
mail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mail)


@pytest.fixture
def receiver(tmp_path):
    directory = tmp_path / 'mail'
    mail.initialize(directory)
    with mail.Server(directory, port=0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield server, directory
        server.shutdown()
        thread.join(timeout=12)


@pytest.mark.parametrize('kind', ['same_browser', 'other_browser', 'expired', 'replay'])
def test_real_tls_signup(client, db, settings, payload, monkeypatch, receiver, kind):
    from app.services import registration_service
    server, directory = receiver
    settings.app_env = 'development'
    settings.registration_email_enabled = True
    settings.registration_public_origin = 'http://localhost:3000'
    settings.smtp_host = '127.0.0.1'
    settings.smtp_port = server.server_address[1]
    settings.smtp_sender = 'noreply@evidenceai.test'
    settings.smtp_ca_file = directory / 'ca.pem'
    Settings.model_validate(settings.model_dump())
    monkeypatch.setattr(registration_service, 'deliver', real_deliver)
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 202
    paths = list(directory.glob('*.eml'))
    assert len(paths) == 1 and paths[0].stat().st_mode & 0o777 == 0o600
    from email.parser import BytesParser
    from email import policy
    content = BytesParser(policy=policy.default).parsebytes(paths[0].read_bytes()).get_content()
    token = re.search(r'http://localhost:3000/verify-email#token=([A-Za-z0-9_-]{43})', content).group(1)
    assert token not in response.text
    intent = db.scalar(select(RegistrationIntent).where(RegistrationIntent.email == payload['email']))
    assert intent.token_hash == hash_token(token) and intent.token_hash != token
    assert db.scalar(select(User).where(User.email == payload['email'])) is None
    cookie = client.cookies.get('evidenceai_registration')
    if kind == 'other_browser':
        client.cookies.delete('evidenceai_registration')
    if kind == 'expired':
        intent.expires_at = db.scalar(select(func.clock_timestamp())) - timedelta(seconds=1)
        db.commit()
    verify = lambda: client.post('/api/v1/auth/verify-registration', json={'token': token})
    if kind == 'replay':
        assert verify().status_code == 202
    assert verify().status_code == (202 if kind == 'same_browser' else 400)
    if kind == 'other_browser':
        client.cookies.set('evidenceai_registration', cookie)
        assert verify().status_code == 202  # Failed cross-browser attempt did not consume proof.
    if kind == 'expired':
        assert db.scalar(select(User).where(User.email == payload['email'])) is None
    else:
        assert client.post('/api/v1/auth/login', json={k: payload[k] for k in ('email', 'password')}).status_code == 200


def test_receiver_rejects_untrusted_ca_and_wrong_hostname(receiver):
    server, directory = receiver
    with pytest.raises(ssl.SSLCertVerificationError):
        smtplib.SMTP_SSL('127.0.0.1', server.server_address[1], context=ssl.create_default_context(), timeout=3)
    context = ssl.create_default_context(cafile=str(directory / 'ca.pem'))
    import socket
    with socket.create_connection(server.server_address, timeout=3) as connection:
        with pytest.raises(ssl.SSLCertVerificationError):
            context.wrap_socket(connection, server_hostname='wrong.example.invalid')


@pytest.mark.parametrize('environment,origin,insecure,allowed', [
    ('development', 'http://localhost:3000', True, True),
    ('development', 'http://localhost:3000', False, False),
    ('test', 'http://localhost:3000', True, False),
    ('staging', 'http://localhost:3000', False, False),
    ('production', 'http://localhost:3000', False, False),
    ('development', 'http://127.0.0.1:3000', True, False),
    ('development', 'http://localhost:3000.evil.invalid', True, False),
])
def test_local_origin_is_development_only(environment, origin, insecure, allowed):
    kwargs = dict(_env_file=None, database_url='postgresql://unused@127.0.0.1/unused',
        app_env=environment, auth_allow_insecure_http=insecure, registration_public_origin=origin,
        trusted_frontend_origins=[origin], registration_email_enabled=True,
        smtp_host='127.0.0.1', smtp_sender='noreply@evidenceai.test')
    if allowed:
        assert Settings(**kwargs).registration_public_origin == origin
    else:
        with pytest.raises(ValidationError):
            Settings(**kwargs)


def test_launcher_uses_process_only_local_settings(receiver, monkeypatch):
    import os
    import sys
    server, directory = receiver
    monkeypatch.setattr(os, 'environ', dict(os.environ))
    monkeypatch.setenv('APP_ENV', 'development')
    environment_file = directory / 'development.env'
    environment_file.write_text('APP_ENV=development\nAUTH_ALLOW_INSECURE_HTTP=true\n')
    monkeypatch.setitem(Settings.model_config, 'env_file', environment_file)
    monkeypatch.setattr(sys, 'argv', ['mail.py', 'api', '--directory', str(directory)])
    captured = {}
    def fake_exec(binary, args):
        captured['args'] = args
        captured['settings'] = Settings()
    monkeypatch.setattr(os, 'execv', fake_exec)
    monkeypatch.chdir(Path.cwd())  # Restore launcher's working-directory change at teardown.
    before = environment_file.read_bytes()
    mail.main()
    configured = captured['settings']
    assert configured.app_env == 'development' and configured.registration_email_enabled
    assert configured.registration_public_origin == 'http://localhost:3000'
    assert configured.trusted_frontend_origins == ['http://localhost:3000']
    assert configured.smtp_host == '127.0.0.1' and configured.smtp_port == 1465
    assert configured.smtp_ca_file == directory / 'ca.pem'
    assert '--no-access-log' in captured['args'] and '--no-proxy-headers' in captured['args']
    assert environment_file.read_bytes() == before


def test_launcher_refuses_hosted_settings(monkeypatch, receiver):
    import sys
    server, directory = receiver
    monkeypatch.setenv('APP_ENV', 'staging')
    monkeypatch.setenv('AUTH_ALLOW_INSECURE_HTTP', 'false')
    monkeypatch.setenv('TRUSTED_FRONTEND_ORIGINS', '["https://staging.example.invalid"]')
    monkeypatch.setattr(sys, 'argv', ['mail.py', 'api', '--directory', str(directory)])
    with pytest.raises(ValueError, match='refuses non-development'):
        mail.main()
