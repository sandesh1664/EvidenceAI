"""Real PostgreSQL + TestClient, all writes rolled back by the existing fixtures."""
from datetime import datetime, timedelta, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.core.config import Settings, get_settings
from app.core.security import hash_token, password_hasher
from app.db.session import get_db
from app.models import User, AuthSession, AuthRateLimit

ORIGIN = 'http://localhost:3000'
HEADERS = {'Origin': ORIGIN, 'X-CSRF-Protection': '1'}
PASSWORD = 'a secure test password 123!'


@pytest.fixture
def settings():
    return Settings(auth_allow_insecure_http=True, app_env='test', auth_rate_limit=100,
                    trusted_frontend_origins=[ORIGIN])


@pytest.fixture
def client(db, settings):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    # Middleware uses runtime configuration, independent of route DI.
    import app.core.browser_security as browser
    original = browser.get_settings
    browser.get_settings = lambda: settings
    app.middleware_stack = None
    with TestClient(app, headers=HEADERS) as client:
        yield client
    app.dependency_overrides.clear()
    browser.get_settings = original
    app.middleware_stack = None


@pytest.fixture
def payload():
    return {'email': f'{uuid.uuid4()}@example.com', 'display_name': ' Researcher ', 'password': PASSWORD}


def register(client, payload):
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def login(client, payload):
    return client.post('/api/v1/auth/login', json={k: payload[k] for k in ('email', 'password')})


def test_registration_hash_and_safe_response(client, db, payload):
    result = register(client, payload)
    assert set(result) == {'id', 'email', 'display_name', 'is_active', 'created_at'}
    assert result['display_name'] == 'Researcher'
    assert result['is_active'] is True
    user = db.get(User, uuid.UUID(result['id']))
    assert user.password_hash.startswith('$argon2id$')
    assert password_hasher.verify(user.password_hash, PASSWORD)
    assert PASSWORD not in str(result)
    assert client.get('/api/v1/auth/me').status_code == 401


@pytest.mark.parametrize('variant', ['same', 'case', 'spaces'])
def test_duplicate_email(client, payload, variant):
    register(client, payload)
    if variant == 'case': payload['email'] = payload['email'].upper()
    if variant == 'spaces': payload['email'] = '  ' + payload['email'] + '  '
    assert client.post('/api/v1/auth/register', json=payload).status_code == 409
    # The failed transaction was rolled back and the session remains usable.
    assert login(client, payload).status_code == 200


def test_case_normalization(client, payload):
    payload['email'] = '  ' + payload['email'].upper() + '  '
    result = register(client, payload)
    assert result['email'] == payload['email'].strip().lower()
    assert login(client, payload).status_code == 200


@pytest.mark.parametrize('field,value', [('email','bad'), ('password','short'), ('password','x'*129),
    ('display_name',' '), ('display_name','x'*201)])
def test_validation_does_not_echo_credentials(client, payload, field, value):
    payload[field] = value
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 422
    assert 'input' not in response.text
    assert PASSWORD not in response.text
    assert 'password_hash' not in response.text


def test_login_session_cookie_and_me(client, db, payload):
    user = register(client, payload)
    response = login(client, payload)
    assert response.status_code == 200
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Path=/' in cookie
    assert 'Domain=' not in cookie and 'Max-Age=' not in cookie
    token = client.cookies['evidenceai_session']
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    assert session and session.token_hash != token
    assert session.expires_at > session.created_at
    assert 'token' not in response.text and 'password' not in response.text
    response = client.get('/api/v1/auth/me')
    assert response.status_code == 200 and response.json() == user
    db.refresh(session)
    assert session.last_used_at is not None
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('kind', ['password', 'unknown', 'inactive', 'no_password'])
def test_login_failures_generic(client, db, payload, kind):
    user = register(client, payload)
    if kind == 'password': payload['password'] = 'wrong password'
    elif kind == 'unknown': payload['email'] = f'{uuid.uuid4()}@example.com'
    else:
        record = db.get(User, uuid.UUID(user['id']))
        if kind == 'inactive': record.is_active = False
        else: record.password_hash = None
        db.commit()
    response = login(client, payload)
    assert response.status_code == 401
    assert response.json() == {'detail':'Invalid email or password'}
    assert 'set-cookie' not in response.headers
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_unauthenticated_me(client):
    assert client.get('/api/v1/auth/me').status_code == 401


def test_logout_revokes_and_clears_cookie(client, db, payload):
    register(client, payload)
    login(client, payload)
    token = client.cookies['evidenceai_session']
    response = client.post('/api/v1/auth/logout')
    assert response.status_code == 204
    assert 'Max-Age=0' in response.headers['set-cookie']
    assert 'evidenceai_session' not in client.cookies
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    assert session.revoked_at is not None
    client.cookies.set('evidenceai_session', token)
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.post('/api/v1/auth/logout').status_code == 401


@pytest.mark.parametrize('kind', ['expired', 'inactive', 'revoked'])
def test_session_rejections(client, db, payload, kind):
    user = register(client, payload)
    login(client, payload)
    session = db.scalar(select(AuthSession))
    # Authentication uses PostgreSQL time; Docker/host clocks can drift.
    if kind == 'expired': session.expires_at = db.scalar(select(func.clock_timestamp())) - timedelta(seconds=1)
    elif kind == 'revoked': session.revoked_at = datetime.now(timezone.utc)
    else: db.get(User, uuid.UUID(user['id'])).is_active = False
    db.commit()
    assert client.get('/api/v1/auth/me').status_code == 401


@pytest.mark.parametrize('token', ['invalid', 'a'*43, 'a'*200, '!'*43])
def test_invalid_tokens(client, token):
    client.cookies.set('evidenceai_session', token)
    assert client.get('/api/v1/auth/me').status_code == 401


@pytest.mark.parametrize('path', ['register','login','logout'])
@pytest.mark.parametrize('headers', [{}, {'Origin':ORIGIN}, {'X-CSRF-Protection':'1'},
    {'Origin':'https://evil.example','X-CSRF-Protection':'1'},
    {'Origin':'null','X-CSRF-Protection':'1'}])
def test_csrf(client, path, headers):
    client.headers.clear()
    response = client.post('/api/v1/auth/'+path, json={}, headers=headers)
    assert response.status_code == 403


def test_csrf_rejection_preserves_session(client, db, payload):
    register(client, payload)
    login(client, payload)
    client.headers.pop('X-CSRF-Protection')
    assert client.post('/api/v1/auth/logout').status_code == 403
    assert db.scalar(select(AuthSession)).revoked_at is None
    assert client.get('/api/v1/auth/me').status_code == 200


def test_cors(client):
    allowed = client.options('/api/v1/auth/login', headers={'Origin':ORIGIN,
        'Access-Control-Request-Method':'POST', 'Access-Control-Request-Headers':'content-type,x-csrf-protection'})
    assert allowed.status_code == 200
    assert allowed.headers['access-control-allow-origin'] == ORIGIN
    assert allowed.headers['access-control-allow-credentials'] == 'true'
    bad = client.options('/api/v1/auth/login', headers={'Origin':'https://evil.example',
        'Access-Control-Request-Method':'POST'})
    assert bad.status_code == 400 and 'access-control-allow-origin' not in bad.headers
    assert client.get('/api/v1/auth/me', headers={'Origin':'https://evil.example'}).status_code == 403


def test_production_secure_cookies(client, settings, payload):
    settings.auth_allow_insecure_http = False
    settings.app_env = 'production'
    settings.trusted_frontend_origins = ['https://app.example.com']
    app.middleware_stack = None
    client.base_url = 'https://api.example.com'
    client.headers['Origin'] = 'https://app.example.com'
    register(client, payload)
    response = login(client, payload)
    cookie = response.headers['set-cookie']
    assert cookie.startswith('__Host-evidenceai_session=') and 'Secure' in cookie and 'HttpOnly' in cookie
    assert client.get('/api/v1/auth/me').status_code == 200
    assert 'Secure' in client.post('/api/v1/auth/logout').headers['set-cookie']
    client.base_url = 'http://api.example.com'
    assert login(client, payload).status_code == 403


@pytest.mark.parametrize('kwargs', [
    {'app_env':'production', 'auth_allow_insecure_http':True},
    {'app_env':'production'}, {'app_env':'staging'},
    {'trusted_frontend_origins':['*']}, {'trusted_frontend_origins':[]},
    {'trusted_frontend_origins':['https://example.com/path']},
    {'trusted_frontend_origins':['https://user@example.com']},
    {'session_ttl_seconds':0},
])
def test_unsafe_configuration_rejected(kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url='postgresql://localhost/test', **kwargs)


def test_production_configuration():
    settings = Settings(_env_file=None, database_url='postgresql://localhost/test', app_env='production',
                        trusted_frontend_origins=['https://app.example.com'])
    assert settings.secure_cookies and settings.session_cookie_name.startswith('__Host-')


@pytest.mark.parametrize('path', ['login','register'])
def test_shared_rate_limit_and_proxy_headers(client, db, settings, payload, path):
    settings.auth_rate_limit = 2
    for _ in range(2):
        assert client.post('/api/v1/auth/'+path, json={}, headers={'X-Forwarded-For':str(uuid.uuid4())}).status_code == 422
    response = client.post('/api/v1/auth/'+path, json=payload)
    assert response.status_code == 429 and int(response.headers['retry-after']) > 0
    assert db.scalar(select(AuthRateLimit.attempts)) == 3


def test_case_insensitive_database_constraint(db, payload):
    db.add(User(email=payload['email'].upper(), display_name='Legacy'))
    db.commit()
    db.add(User(email=' '+payload['email']+' ', display_name='Conflicting'))
    with pytest.raises(IntegrityError): db.commit()
    db.rollback()
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_existing_legacy_identity_login(client, db, payload):
    db.add(User(email=' '+payload['email'].upper()+' ', display_name='Legacy',
                password_hash=password_hasher.hash(PASSWORD)))
    db.commit()
    assert login(client, payload).status_code == 200
    assert client.post('/api/v1/auth/register', json=payload).status_code == 409


def test_session_expiration_configuration(client, db, settings, payload):
    settings.session_ttl_seconds = 120
    register(client, payload)
    login(client, payload)
    session = db.scalar(select(AuthSession))
    assert 119 <= (session.expires_at - session.created_at).total_seconds() <= 122


def test_login_rotates_session_tokens(client, db, payload):
    register(client, payload)
    login(client, payload)
    first = client.cookies['evidenceai_session']
    login(client, payload)
    assert client.cookies['evidenceai_session'] != first
    assert len(db.scalars(select(AuthSession)).all()) == 2


def test_migration_conflicting_identities_preflight(db, payload):
    # Isolate the migration guard on a temporary shadow table; no existing rows change.
    from sqlalchemy import text
    db.execute(text('CREATE TEMP TABLE users (email text) ON COMMIT DROP'))
    db.execute(text("INSERT INTO pg_temp.users VALUES ('User@example.com'), (' user@example.com ')"))
    source = (__import__('pathlib').Path(__file__).parents[1] /
              'alembic/versions/a31f8c9d204e_authentication.py').read_text()
    import ast
    tree = ast.parse(source)
    guard = next(node.value.args[0].value for node in ast.walk(tree)
                 if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                 and getattr(node.value.func, 'attr', None) == 'execute')
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError, match='Conflicting email identities'):
        db.execute(text(guard))
    db.rollback()


def test_auth_session_commit_is_rolled_back():
    from app.db.session import get_engine
    from sqlalchemy.orm import Session
    engine = get_engine()
    user_id, session_id = uuid.uuid4(), uuid.uuid4()
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
                session.add(User(id=user_id, email=f'{user_id}@example.com', display_name='Isolated'))
                session.flush()
                session.add(AuthSession(id=session_id, user_id=user_id, token_hash=hash_token(str(session_id)),
                                        expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
                session.commit()
                assert session.get(AuthSession, session_id) is not None
        finally:
            outer.rollback()
    with Session(engine) as session:
        assert session.get(User, user_id) is None
        assert session.get(AuthSession, session_id) is None


def test_limiter_shared_across_sessions(connection, settings):
    from sqlalchemy.orm import Session
    from fastapi import HTTPException
    from app.services.auth_service import rate_limit
    settings.auth_rate_limit = 1
    for attempt in range(2):
        with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
            if attempt == 0:
                rate_limit(session, settings, 'test-shared-client', 'login')
            else:
                with pytest.raises(HTTPException) as error:
                    rate_limit(session, settings, 'test-shared-client', 'login')
                assert error.value.status_code == 429


def test_failed_login_consumes_rate_budget(client, db, settings, payload):
    settings.auth_rate_limit = 1
    assert login(client, payload).status_code == 401
    assert login(client, payload).status_code == 429
    assert db.scalar(select(AuthRateLimit.attempts)) == 2


def test_limiter_new_window(client, db, settings, payload):
    settings.auth_rate_limit = 1
    assert login(client, payload).status_code == 401
    counter = db.scalar(select(AuthRateLimit))
    counter.window_start -= timedelta(seconds=settings.auth_rate_window_seconds)
    db.commit()
    assert login(client, payload).status_code == 401
    assert len(db.scalars(select(AuthRateLimit)).all()) == 2


def test_legacy_null_password_uses_generic_failure(client, db, payload):
    db.add(User(email=payload['email'], display_name='Legacy'))
    db.commit()
    response = login(client, payload)
    assert response.status_code == 401 and response.json()['detail'] == 'Invalid email or password'


def test_health_without_configuration(monkeypatch):
    import app.core.browser_security as browser
    def unavailable():
        raise RuntimeError('Configuration deliberately unavailable')
    monkeypatch.setattr(browser, 'get_settings', unavailable)
    app.middleware_stack = None
    try:
        with TestClient(app) as client:
            assert client.get('/api/v1/health').status_code == 200
    finally:
        app.middleware_stack = None
