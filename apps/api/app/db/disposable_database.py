"""Fail-closed entry point shared by pytest and the browser API fixture.

An explicit, generated test database is mandatory. Never fall back to .env.
The disposable container runner owns provisioning and cleanup.
"""
import os
import re
from sqlalchemy.engine import make_url


def disposable_database_url(environ=None):
    env = os.environ if environ is None else environ
    value = env.get('EVIDENCEAI_TEST_DATABASE_URL', '')
    try:
        url = make_url(value)
        valid = (url.drivername == 'postgresql+psycopg'
                 and url.host in {'127.0.0.1', 'localhost'}
                 and url.port is not None
                 and re.fullmatch(r'evidenceai_test_[a-f0-9]{32}', url.database or '')
                 and not url.query)
    except Exception:
        valid = False
    if not valid:
        raise RuntimeError('Explicit loopback disposable EVIDENCEAI_TEST_DATABASE_URL required; use infra/testing/run_isolated.py')
    return value


def activate():
    value = disposable_database_url()
    os.environ['DATABASE_URL'] = value
    os.environ['APP_ENV'] = 'test'
    return value


def require_disposable_database():
    """Offline evaluators may not write schemas using inherited development URLs."""
    expected = make_url(disposable_database_url())
    from app.core.config import get_settings
    from app.db.session import get_engine
    if make_url(get_settings().database_url.get_secret_value()) != expected or get_engine().url != expected:
        raise RuntimeError('Offline evaluation requires the configured disposable test database; use the isolated runner')
