"""Synthetic offline Gemini contracts; all HTTP uses explicit MockTransport."""
import json
import math
import time
from dataclasses import replace

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.ask import AskRequest
from app.schemas.search import SearchRequest
from app.services import embedding_jobs, rag_service, search_service
from app.services.citation_validation import CitationError, validate_answer
from app.services.embedding_providers import EmbeddingEngine, EmbeddingError, profile_for
from app.services.gemini_providers import GeminiEmbeddingProvider, GeminiLLMProvider
from app.services.llm_providers import LLMEngine, LLMError
from app.services.rag_context import assemble_context, make_prompt
from test_rag import source, TEXT, QUESTION
from test_embeddings import (embedding_settings, document, workspace, people, identity,
                             settings, storage, doc_client, client, encoded_password)


def config(**changes):
    values = dict(_env_file=None, database_url='postgresql://localhost/test',
        gemini_api_key='synthetic-offline-contract-value', gemini_free_tier_confirmed=True,
        gemini_data_transfer_allowed=True, gemini_live_requests_allowed=True,
        gemini_private_documents_allowed=True, embedding_hosted_allowed=True, llm_hosted_allowed=True,
        embedding_provider='gemini', embedding_model='gemini-embedding-001',
        embedding_dimensions=768, embedding_revision='retrieval-v1',
        llm_provider='gemini', llm_model='gemini-2.5-flash')
    values.update(changes)
    return Settings(**values)


def reply(output=None):
    return {'modelVersion': 'gemini-2.5-flash', 'candidates': [
        {'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [{'text': json.dumps(output or {
            'outcome': 'answered', 'claims': [{'text': TEXT, 'supports': [{'citation_id': 'C1', 'quote': TEXT}]}]})}]}}],
        'usageMetadata': {'promptTokenCount': 80, 'candidatesTokenCount': 40, 'totalTokenCount': 120}}


def response_for(request, output=None):
    request_data = json.loads(request.content)
    contents = json.loads(request_data['contents'][0]['parts'][0]['text'])
    data = reply(output)
    if contents.get('relevance_review'):
        data['candidates'][0]['content']['parts'][0]['text'] = json.dumps({
            'supported': [True for _ in contents['claims']], 'contradictory': False})
    return httpx.Response(200, json=data)


@pytest.mark.parametrize('changes', [dict(gemini_api_key=None), dict(gemini_free_tier_confirmed=False),
    dict(gemini_data_transfer_allowed=False), dict(embedding_hosted_allowed=False),
    dict(llm_hosted_allowed=False), dict(app_env='production'), dict(app_env='staging'),
    dict(embedding_dimensions=128), dict(embedding_model='other'), dict(llm_model='other')])
def test_configuration_fail_closed(changes):
    with pytest.raises(ValidationError):
        config(**changes)


def test_embedding_batch_tasks_and_normalization():
    seen = []
    def handler(request):
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.url.query == b''
        assert request.headers['x-goog-api-key'] == 'synthetic-offline-contract-value'
        assert 'authorization' not in request.headers
        data = json.loads(request.content)
        seen.append(data)
        assert request.url.path.endswith('gemini-embedding-001:batchEmbedContents')
        return httpx.Response(200, json={'embeddings': [{'values': [1.0]*768} for _ in data['requests']]})
    s = config()
    engine = EmbeddingEngine(s, GeminiEmbeddingProvider(s, transport=httpx.MockTransport(handler)))
    vectors = engine.embed(['Synthetic solar document.', 'Synthetic wind document.'])
    assert len(vectors) == 2 and math.isclose(math.hypot(*vectors[0]), 1)
    engine.embed_query('Solar question?')
    assert [x['taskType'] for x in seen[0]['requests']] == ['RETRIEVAL_DOCUMENT']*2
    assert seen[1]['requests'][0]['taskType'] == 'RETRIEVAL_QUERY'
    assert all(x['outputDimensionality'] == 768 for x in seen[0]['requests'])
    assert profile_for(s).id != profile_for(s.model_copy(update={'embedding_provider': 'fake'})).id


@pytest.mark.parametrize('payload', [{}, {'embeddings': []}, {'embeddings': [{'values': [0]*768}]},
    {'embeddings': [{'values': [1]*767}]}, {'embeddings': [{'values': [True]*768}]},
    {'embeddings': [{'values': ['bad']*768}]}, {'embeddings': [None]}])
def test_invalid_embeddings(payload):
    s = config()
    p = GeminiEmbeddingProvider(s, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    with pytest.raises(EmbeddingError):
        EmbeddingEngine(s, p).embed(['Synthetic text'])


def test_generation_contract_and_real_citation_validation():
    def handler(request):
        data = json.loads(request.content)
        assert request.url.query == b'' and request.url.path.endswith('gemini-2.5-flash:generateContent')
        content = json.loads(data['contents'][0]['parts'][0]['text'])
        if content.get('relevance_review'):
            assert content['question'] == QUESTION
            assert data['generationConfig']['maxOutputTokens'] == 250
            return response_for(request)
        assert data['contents'][0]['parts'][0]['text'] == prompt
        assert 'untrusted' in data['systemInstruction']['parts'][0]['text']
        assert data['generationConfig']['thinkingConfig'] == {'thinkingBudget': 0}
        assert data['generationConfig']['maxOutputTokens'] == 750
        assert data['generationConfig']['responseMimeType'] == 'application/json'
        assert 'tools' not in data and 'cachedContent' not in data
        return response_for(request)
    s, context = config(), [source()]
    prompt = make_prompt(QUESTION, context)
    result = LLMEngine(s, GeminiLLMProvider(s, transport=httpx.MockTransport(handler))).generate(
        prompt, deadline=time.monotonic()+10)
    claims, citations = validate_answer(result.output, context, QUESTION, s)
    assert claims and citations and result.usage.total_tokens == 240
    assert result.model == 'gemini-2.5-flash'
    for output in [dict(outcome='answered', claims=[dict(text=TEXT, supports=[dict(citation_id='C2', quote=TEXT)])]),
                   dict(outcome='answered', claims=[dict(text='Solar panels convert stones into gold.', supports=[dict(citation_id='C1', quote='Solar panels convert stones into gold.')])])]:
        with pytest.raises(CitationError):
            validate_answer(output, context, QUESTION, s)
    secret_context = [replace(context[0], text='Synthetic text '+s.gemini_api_key.get_secret_value())]
    assert assemble_context(secret_context, s) == []


@pytest.mark.parametrize('mutation', ['model', 'finish', 'parts', 'json', 'usage', 'thinking', 'empty'])
def test_invalid_generation(mutation):
    data = reply()
    if mutation == 'model': data['modelVersion'] = 'unapproved-model'
    if mutation == 'finish': data['candidates'][0]['finishReason'] = 'MAX_TOKENS'
    if mutation == 'parts': data['candidates'][0]['content']['parts'][0]['thought'] = True
    if mutation == 'json': data['candidates'][0]['content']['parts'][0]['text'] = '{}'
    if mutation == 'usage': data['usageMetadata']['totalTokenCount'] = 1
    if mutation == 'thinking': data['usageMetadata']['thoughtsTokenCount'] = 5
    if mutation == 'empty': data['candidates'] = []
    s = config()
    with pytest.raises(LLMError):
        GeminiLLMProvider(s, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data))).generate('{}', timeout=1)


@pytest.mark.parametrize('kind', ['embedding', 'generation'])
@pytest.mark.parametrize('status', [429, 403, 500, 302])
def test_error_retry_and_no_raw_error_disclosure(kind, status):
    calls, pauses = [], []
    def handler(request):
        calls.append(1)
        return httpx.Response(status, text='SENSITIVE_PROVIDER_DIAGNOSTIC', headers={'location': 'https://elsewhere.invalid'})
    s = config()
    if kind == 'embedding':
        engine = EmbeddingEngine(s, GeminiEmbeddingProvider(s, transport=httpx.MockTransport(handler)), sleep=pauses.append)
        with pytest.raises(EmbeddingError) as caught: engine.embed(['synthetic'])
        attempts = s.embedding_provider_attempts
    else:
        engine = LLMEngine(s, GeminiLLMProvider(s, transport=httpx.MockTransport(handler)), sleep=pauses.append)
        with pytest.raises(LLMError) as caught: engine.generate('{}', deadline=time.monotonic()+10)
        attempts = s.llm_max_attempts
    assert len(calls) == (attempts if status == 500 else 1)
    assert 'SENSITIVE' not in str(caught.value)


@pytest.mark.parametrize('kind', ['embedding', 'generation'])
def test_timeout_budget(kind):
    def handler(request): raise httpx.ReadTimeout('PRIVATE_DIAGNOSTIC')
    s = config(embedding_provider_attempts=1, llm_max_attempts=1)
    transport = httpx.MockTransport(handler)
    if kind == 'embedding':
        with pytest.raises(EmbeddingError, match='timed out'):
            EmbeddingEngine(s, GeminiEmbeddingProvider(s, transport=transport)).embed(['synthetic'])
    else:
        with pytest.raises(LLMError, match='timeout'):
            LLMEngine(s, GeminiLLMProvider(s, transport=transport)).generate('{}', deadline=time.monotonic()+1)


def test_runtime_optin_rechecked():
    s = config().model_copy(update={'gemini_data_transfer_allowed': False})
    with pytest.raises(EmbeddingError): GeminiEmbeddingProvider(s).embed(['synthetic'], timeout=1)
    with pytest.raises(LLMError): GeminiLLMProvider(s).generate('{}', timeout=1)


def test_gemini_index_search_profile_and_workspace_isolation(db, workspace, people, document, monkeypatch):
    from app.models import DocumentChunk, ChunkEmbedding, Document
    from sqlalchemy import select
    s = config(search_min_similarity=0)
    actor = identity(people, 'owner')
    original_chunks = db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == document.id)).all()
    old = s.model_copy(update={'embedding_provider': 'fake', 'embedding_model': 'fake-hash-v1',
                               'embedding_dimensions': 128, 'embedding_revision': '1'})
    embedding_jobs.request_index(db, workspace.id, document.id, actor, old)
    old_claim = embedding_jobs.claim_job(db, old)
    assert embedding_jobs.process_claim(db, old_claim, old)
    old_vector = list(db.scalars(select(ChunkEmbedding).where(
        ChunkEmbedding.profile_id == profile_for(old).id)).first().vector)

    tasks = []
    def handler(request):
        data = json.loads(request.content)
        tasks.extend(x['taskType'] for x in data['requests'])
        return httpx.Response(200, json={'embeddings': [{'values': [1.0]*768} for _ in data['requests']]})
    engine = EmbeddingEngine(s, GeminiEmbeddingProvider(s, transport=httpx.MockTransport(handler)))
    embedding_jobs.request_index(db, workspace.id, document.id, actor, s)
    claim = embedding_jobs.claim_job(db, s)
    assert embedding_jobs.process_claim(db, claim, s, engine)
    assert embedding_jobs.status_for(db, document.id, s)['state'] == 'done'
    assert db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == document.id)).all() == original_chunks
    assert db.get(Document, document.id).processing_status == 'completed'
    found = search_service.search(db, workspace.id, actor, SearchRequest(query=QUESTION), s, engine)
    assert found and found[0]['embedding_model'].startswith('gemini:gemini-embedding-001@')
    assert list(db.scalars(select(ChunkEmbedding).where(
        ChunkEmbedding.profile_id == profile_for(old).id)).first().vector) == old_vector
    assert tasks == ['RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY']
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        search_service.search(db, workspace.id, identity(people, 'outsider'), SearchRequest(query=QUESTION), s, engine)
    assert tasks == ['RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY']
    wrong = s.model_copy(update={'embedding_revision': 'other'})
    assert search_service.search(db, workspace.id, actor, SearchRequest(query=QUESTION), wrong, engine) == []
    monkeypatch.setattr(search_service, 'EmbeddingEngine', lambda _: engine)
    llm = LLMEngine(s, GeminiLLMProvider(s, transport=httpx.MockTransport(response_for)))
    result = rag_service.ask(db, workspace.id, actor, AskRequest(question=QUESTION), s, engine=llm)
    assert result.body.status == 'answered' and result.body.citations
    assert result.body.model_identifier.startswith('gemini:gemini-2.5-flash@')


def test_synthetic_probe_full_path_offline(db):
    from app.gemini_probe import exercise
    seen = {'embedding': 0, 'generation': 0}
    def handler(request):
        if request.url.path.endswith(':batchEmbedContents'):
            seen['embedding'] += 1
            return httpx.Response(200, json={'embeddings': [{'values': [1.0]*768}]})
        seen['generation'] += 1
        return response_for(request)
    s = config()
    transport = httpx.MockTransport(handler)
    result = exercise(db, s, EmbeddingEngine(s, GeminiEmbeddingProvider(s, transport=transport)),
                      LLMEngine(s, GeminiLLMProvider(s, transport=transport)))
    assert result['indexing'] == result['retrieval_and_citations'] == 'PASS'
    assert seen == {'embedding': 3, 'generation': 2}


def test_probe_stops_after_first_quota_error(db):
    from app.gemini_probe import exercise
    seen = []
    def handler(request):
        seen.append(1)
        return httpx.Response(429, text='PRIVATE_QUOTA_DIAGNOSTIC')
    s = config()
    transport = httpx.MockTransport(handler)
    with pytest.raises(EmbeddingError):
        exercise(db, s, EmbeddingEngine(s, GeminiEmbeddingProvider(s, transport=transport)),
                 LLMEngine(s, GeminiLLMProvider(s, transport=transport)))
    assert len(seen) == 1


@pytest.mark.parametrize('kind', ['embedding', 'generation'])
def test_malformed_and_oversize_http_body(kind):
    s = config()
    for body in [b'invalid-json', b'[]', b'x'*1000000]:
        transport = httpx.MockTransport(lambda _: httpx.Response(200, content=body))
        if kind == 'embedding':
            with pytest.raises(EmbeddingError):
                GeminiEmbeddingProvider(s, transport=transport).embed(['synthetic'], timeout=1)
        else:
            with pytest.raises(LLMError):
                GeminiLLMProvider(s, transport=transport).generate('{}', timeout=1)


def test_empty_unused_key_does_not_exclude_all_context():
    s = Settings(_env_file=None, database_url='postgresql://localhost/test',
                 openai_api_key='', gemini_api_key='')
    assert assemble_context([source()], s)
