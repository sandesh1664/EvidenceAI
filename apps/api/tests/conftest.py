"""Each database test owns an outer transaction; session commits use savepoints."""
import os

# Test processes must never inherit a paid provider/key from the developer's .env.
# Explicit Settings(...) kwargs in hosted MockTransport tests still take precedence.
for setting, value in {
    "LLM_PROVIDER": "disabled", "LLM_MODEL": "mock-extractive-v1", "LLM_REVISION": "1",
    "LLM_HOSTED_ALLOWED": "false",
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
