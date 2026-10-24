"""Blocked Gemini diagnostics use only synthetic data in the isolated database."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.models import EmbeddingJob
from app.schemas.ask import AskRequest
from app.schemas.search import IndexStatus, SearchRequest
from app.services import embedding_jobs, rag_service, search_service
from app.services.embedding_providers import profile_for
from test_documents import doc_client, settings, storage
from test_embeddings import embedding_settings, fake_settings, index_document, seed_completed
from test_gemini import config as gemini_settings
from test_workspaces import client, encoded_password, identity, people, workspace


def reject_embedding_engine(_settings):
    raise AssertionError("Configuration-only checks must not construct a provider")


@pytest.mark.parametrize('changes,code', [
    ({'gemini_live_requests_allowed': False}, 'embedding_live_requests_blocked'),
    ({'gemini_live_requests_allowed': False, 'gemini_api_key': None}, 'embedding_api_key_missing'),
    ({'gemini_private_documents_allowed': False}, 'embedding_private_document_transfer_not_authorized'),
])
def test_blocked_gemini_with_no_vectors_returns_safe_diagnostic_without_writes(
        db, connection, workspace, people, monkeypatch, changes, code):
    settings = gemini_settings(**changes)
    monkeypatch.setattr(search_service, 'EmbeddingEngine', reject_embedding_engine)
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lstrip().split(None, 1)[0].upper())

    event.listen(connection, 'before_cursor_execute', record)
    try:
        with pytest.raises(HTTPException) as caught:
            search_service.search(db, workspace.id, identity(people, 'owner'),
                                  SearchRequest(query='Solar electricity'), settings)
        result = rag_service.ask(db, workspace.id, identity(people, 'owner'),
                                 AskRequest(question='What produces solar electricity?'), settings)
    finally:
        event.remove(connection, 'before_cursor_execute', record)
    assert caught.value.status_code == 503
    assert caught.value.detail['code'] == code
    assert result.http_status == 503
    assert result.body.status == 'retrieval_unavailable'
    assert result.body.reason == code
    assert result.body.retrieved_evidence_count == 0
    assert 'synthetic-offline-contract-value' not in result.body.model_dump_json()
    assert not {'INSERT', 'UPDATE', 'DELETE', 'COMMIT'} & set(statements)


def test_blocked_gemini_still_checks_membership_and_source_filters(db, workspace, people, monkeypatch):
    settings = gemini_settings(gemini_live_requests_allowed=False)
    monkeypatch.setattr(search_service, 'EmbeddingEngine', reject_embedding_engine)
    with pytest.raises(HTTPException) as denied:
        search_service.search(db, workspace.id, identity(people, 'outsider'),
                              SearchRequest(query='Solar electricity'), settings)
    assert denied.value.status_code == 404
    with pytest.raises(HTTPException) as missing:
        search_service.search(db, workspace.id, identity(people, 'owner'),
                              SearchRequest(query='Solar electricity', document_ids=[uuid4()]), settings)
    assert missing.value.status_code == 404


def test_explicit_empty_sources_remain_empty_even_with_blocked_gemini(db, workspace, people, monkeypatch):
    settings = gemini_settings(gemini_live_requests_allowed=False)
    monkeypatch.setattr(search_service, 'EmbeddingEngine', reject_embedding_engine)
    assert search_service.search(db, workspace.id, identity(people, 'owner'),
                                 SearchRequest(query='Solar electricity', document_ids=[]), settings) == []
    result = rag_service.ask(db, workspace.id, identity(people, 'owner'),
                             AskRequest(question='What produces solar electricity?', document_ids=[]), settings)
    assert result.http_status == 200
    assert result.body.reason == 'no_evidence'
    assert result.body.retrieved_evidence_count == 0


@pytest.mark.parametrize('settings_factory', [gemini_settings, fake_settings])
def test_configured_provider_with_no_vectors_remains_empty(
        db, workspace, people, monkeypatch, settings_factory):
    monkeypatch.setattr(search_service, 'EmbeddingEngine', reject_embedding_engine)
    assert search_service.search(db, workspace.id, identity(people, 'owner'),
                                 SearchRequest(query='Solar electricity'), settings_factory()) == []


def test_queued_index_reports_embedding_blocker_without_consuming_attempts(db, workspace, people):
    settings = gemini_settings(gemini_live_requests_allowed=False)
    document = seed_completed(db, workspace, identity(people, 'owner'))
    embedding_jobs.request_index(db, workspace.id, document.id, identity(people, 'owner'), settings)
    state = embedding_jobs.status_for(db, document.id, settings)
    assert state['state'] == 'queued'
    assert state['indexed_chunks'] == 0 and state['total_chunks'] == 1
    assert state['research_blocker'] == 'active_profile_not_indexed'
    assert IndexStatus(**state).indexing_blocker == 'live_requests_blocked'
    assert embedding_jobs.run_once(db, settings) is False
    job = db.get(EmbeddingJob, (document.id, profile_for(settings).id), populate_existing=True)
    assert job.state == 'queued' and job.attempts == 0 and job.lease_id is None


def test_llm_only_blocker_does_not_label_completed_embedding_index_blocked(
        db, workspace, people, embedding_settings):
    settings = embedding_settings.model_copy(update={
        'llm_provider': 'gemini', 'llm_model': 'gemini-2.5-flash',
        'gemini_live_requests_allowed': False,
    })
    document = seed_completed(db, workspace, identity(people, 'owner'))
    index_document(db, workspace, document, people, settings)
    state = IndexStatus(**embedding_jobs.status_for(db, document.id, settings))
    assert state.state == 'done' and state.indexing_complete
    assert state.indexing_blocker is None
    assert not state.ready_for_research
    assert state.research_blocker == 'live_requests_blocked'
