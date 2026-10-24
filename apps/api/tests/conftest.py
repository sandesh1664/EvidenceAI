"""Each database test owns an outer transaction; session commits use savepoints."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra/testing"))
from database_guard import activate
activate()  # Before importing application modules or constructing any engine.

# Test processes must never inherit a paid provider/key from the developer's .env.
# Explicit Settings(...) kwargs in hosted MockTransport tests still take precedence.
for setting, value in {
    "LLM_PROVIDER": "disabled", "LLM_MODEL": "mock-extractive-v1", "LLM_REVISION": "1",
    "LLM_HOSTED_ALLOWED": "false",
    "GEMINI_API_KEY": "offline-test-placeholder",
    "GEMINI_LIVE_REQUESTS_ALLOWED": "false", "GEMINI_PRIVATE_DOCUMENTS_ALLOWED": "false",
    "GEMINI_FREE_TIER_CONFIRMED": "false", "GEMINI_DATA_TRANSFER_ALLOWED": "false",
    "EMBEDDING_PROVIDER": "disabled", "EMBEDDING_MODEL": "fake-hash-v1",
    "EMBEDDING_REVISION": "1", "EMBEDDING_DIMENSIONS": "128",
    "EMBEDDING_HOSTED_ALLOWED": "false", "OPENAI_API_KEY": "offline-test-placeholder",
    "EMBEDDING_BATCH_SIZE": "16", "EMBEDDING_INPUT_MAX_BYTES": "8000",
    "EMBEDDING_HTTP_TIMEOUT_SECONDS": "10", "EMBEDDING_REQUEST_BUDGET_SECONDS": "30",
    "EMBEDDING_PROVIDER_ATTEMPTS": "3", "EMBEDDING_JOB_MAX_ATTEMPTS": "3",
    "EMBEDDING_JOB_LEASE_SECONDS": "120", "SEARCH_MIN_SIMILARITY": "0.25",
}.items():
    os.environ[setting] = value

import httpx
import pytest
from sqlalchemy.orm import Session
from app.db.session import get_engine


@pytest.fixture
def connection():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def db(connection):
    with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as session:
        yield session


@pytest.fixture(autouse=True)
def offline_http_only(monkeypatch):
    def reject_network(self, request):
        raise AssertionError("Tests require TestClient or explicit MockTransport; live HTTP is disabled")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_network)
    async def reject_async_network(self, request):
        raise AssertionError("Tests require explicit MockTransport; live HTTP is disabled")
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", reject_async_network)


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    """Never let unscoped test workers/queries see development records.

    Existing function references use the cached engine factory, so replacing its
    constructor preserves every imported get_engine reference during this session.
    """
    import uuid
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema
    from app.core.config import get_settings
    from app.db import session as sessions
    from app.db.base import Base
    import app.models  # register every table before creating the isolated schema
    settings=get_settings()
    url=settings.database_url.get_secret_value()
    if make_url(url).host not in {'localhost','127.0.0.1'} or settings.app_env not in {'test','development'}:
        raise RuntimeError('Tests require a loopback development/test database')
    schema='test_suite_'+uuid.uuid4().hex
    control=create_engine(url,hide_parameters=True)
    scratch=None
    original_constructor=sessions.create_engine
    try:
        with control.begin() as connection:
            connection.execute(CreateSchema(schema))
            revision=connection.scalar(text('SELECT version_num FROM public.alembic_version'))
            connection.execute(text(f'CREATE TABLE {schema}.alembic_version (version_num varchar(32) NOT NULL PRIMARY KEY)'))
            connection.execute(text(f'INSERT INTO {schema}.alembic_version VALUES (:revision)'),{'revision':revision})
        scratch=create_engine(url,hide_parameters=True,
            connect_args={'options':f'-c search_path={schema},public -c statement_timeout=15000 -c lock_timeout=5000', 'connect_timeout':5},
            execution_options={'schema_translate_map':{None:schema}})
        Base.metadata.create_all(scratch)
        sessions.get_engine.cache_clear()
        sessions.get_session_factory.cache_clear()
        sessions.create_engine=lambda *args,**kwargs:scratch
        yield scratch
    finally:
        sessions.create_engine=original_constructor
        sessions.get_engine.cache_clear()
        sessions.get_session_factory.cache_clear()
        if scratch is not None: scratch.dispose()
        assert schema.startswith('test_suite_') and len(schema)==43
        with control.begin() as connection: connection.execute(DropSchema(schema,cascade=True))
        control.dispose()
