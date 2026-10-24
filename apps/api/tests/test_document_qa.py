"""Actual upload/worker/index/ask path with Gemini HTTP mocked, never live."""
import json
from dataclasses import replace
import httpx
import pytest
from sqlalchemy import select

from app.models import DocumentChunk
from app.services import document_jobs, embedding_jobs, search_service, rag_service
from app.services.embedding_providers import EmbeddingEngine, EmbeddingError
from app.services.llm_providers import LLMEngine, LLMError
from app.services.gemini_providers import GeminiEmbeddingProvider, GeminiLLMProvider
from app.services.citation_validation import CitationError, validate_answer
from test_documents import doc_client, settings, storage, upload, stored_document
from test_workspaces import client, people, encoded_password, workspace, identity, sign_in
from test_gemini import config, reply

QUOTE = 'Employees receive twenty days of paid vacation each year.'
QUESTION = 'How much annual leave is available?'


def payload_output(output):
    data = reply()
    data['candidates'][0]['content']['parts'][0]['text'] = json.dumps(output)
    return data


def transport_for(*, review_supported=True, invented=False, code=200):
    calls = []
    def handler(request):
        data = json.loads(request.content)
        if request.url.path.endswith(':batchEmbedContents'):
            calls.append('embedding')
            return httpx.Response(200, json={'embeddings':[{'values':[1.0]*768} for _ in data['requests']]})
        content = json.loads(data['contents'][0]['parts'][0]['text'])
        if content.get('relevance_review'):
            calls.append('review')
            return httpx.Response(code, json=payload_output({'supported':[review_supported], 'contradictory':False}))
        calls.append('answer')
        item = next(x for x in content['evidence'] if QUOTE in x['text'])
        quote = 'Employees receive ninety days of paid vacation each year.' if invented else QUOTE
        return httpx.Response(200, json=payload_output({'outcome':'answered','claims':[
            {'text':quote,'supports':[{'citation_id':item['citation_id'],'quote':quote}]}]}))
    return httpx.MockTransport(handler), calls


def test_upload_to_gemini_adapter_answer_and_citation(doc_client, db, people, workspace, settings, storage, monkeypatch):
    s = config()
    for key in ('embedding_provider','embedding_model','embedding_revision','embedding_dimensions',
                'embedding_hosted_allowed','llm_provider','llm_model','llm_hosted_allowed','gemini_api_key',
                'gemini_free_tier_confirmed','gemini_data_transfer_allowed','gemini_live_requests_allowed',
                'gemini_private_documents_allowed'):
        setattr(settings,key,getattr(s,key))
    settings.rag_min_similarity = 0.35
    transport, calls = transport_for()
    embedding = EmbeddingEngine(settings, GeminiEmbeddingProvider(settings, transport=transport))
    generation = LLMEngine(settings, GeminiLLMProvider(settings, transport=transport))
    monkeypatch.setattr(search_service, 'EmbeddingEngine', lambda _:embedding)
    monkeypatch.setattr(rag_service, 'LLMEngine', lambda _:generation)
    sign_in(doc_client,people,'owner')
    # The actual answer starts AFTER the old search-preview truncation boundary.
    content = ('Research background. '*60)+QUOTE
    assert content.index(QUOTE) > 1000
    document = stored_document(db, upload(doc_client,workspace,content.encode(), name='synthetic-leave.txt'))
    claim = document_jobs.claim_job(db,settings)
    assert document_jobs.process_claim(db,claim,settings,storage)
    embedding_jobs.request_index(db,workspace.id,document.id,identity(people,'owner'),settings)
    claim = embedding_jobs.claim_job(db,settings)
    assert embedding_jobs.process_claim(db,claim,settings,embedding)
    path = f'/api/v1/workspaces/{workspace.id}'
    state = doc_client.get(path+f'/documents/{document.id}/index').json()
    assert state['indexing_complete'] and state['ready_for_research']
    response = doc_client.post(path+'/ask', json={'question':QUESTION,'document_ids':[str(document.id)]})
    assert response.status_code == 200
    answer = response.json()
    assert answer['status'] == 'answered' and QUOTE in answer['answer']
    assert answer['model_identifier'].startswith('gemini:gemini-2.5-flash@')
    citation = answer['citations'][0]
    chunk = db.get(DocumentChunk, citation['chunk_id'])
    assert citation['document_id'] == str(document.id)
    assert chunk.text[citation['char_start']:citation['char_end']] == citation['supporting_excerpt'] == QUOTE
    assert calls == ['embedding','embedding','answer','review']
    sign_in(doc_client,people,'outsider')
    assert doc_client.post(path+'/ask',json={'question':QUESTION}).status_code == 404
    assert calls == ['embedding','embedding','answer','review']


@pytest.mark.parametrize('supported', [False, True])
def test_review_decides_semantic_relevance_without_fabricating_quotes(supported):
    from test_rag import source
    from app.services.rag_context import make_prompt
    transport,calls = transport_for(review_supported=supported)
    s=config(); context=[source(QUOTE)]
    result=GeminiLLMProvider(s,transport=transport).generate(make_prompt(QUESTION,context),timeout=2)
    claims,citations=validate_answer(result.output,context,QUESTION,s,relevance_verified=result.relevance_verified)
    assert bool(claims) == supported and bool(citations) == supported
    assert calls == ['answer','review']
    assert result.usage.total_tokens == 240


def test_invented_quote_rejected_before_second_call():
    from test_rag import source
    from app.services.rag_context import make_prompt
    transport,calls=transport_for(invented=True)
    with pytest.raises(LLMError):
        GeminiLLMProvider(config(),transport=transport).generate(make_prompt(QUESTION,[source(QUOTE)]),timeout=2)
    assert calls == ['answer']


def test_numeric_qualifiers_cannot_be_bypassed_by_semantic_review():
    from test_rag import source, output
    with pytest.raises(CitationError):
        validate_answer(output(QUOTE),[source(QUOTE)],'Are 90 days of vacation provided?',config(),relevance_verified=True)


@pytest.mark.parametrize('status,code',[(400,'invalid_key'),(401,'invalid_key'),(403,'access_denied'),(404,'model_unavailable'),(429,'quota')])
def test_safe_provider_error_codes(status,code):
    def handler(request):
        return httpx.Response(status,json={'error':{'message':'PRIVATE PROVIDER DIAGNOSTIC',
            'details':[{'reason':'API_KEY_INVALID'}]}})
    s=config()
    with pytest.raises(LLMError) as caught:
        GeminiLLMProvider(s,transport=httpx.MockTransport(handler)).generate('{}',timeout=1)
    assert caught.value.code == code and 'PRIVATE' not in str(caught.value)


def test_blocked_gemini_can_start_and_show_missing_key_without_network():
    from app.services.research_readiness import provider_status
    s=config(gemini_api_key=None,gemini_live_requests_allowed=False,
             gemini_free_tier_confirmed=False,gemini_data_transfer_allowed=False,
             embedding_hosted_allowed=False,llm_hosted_allowed=False)
    assert provider_status(s,'embedding')['blocker'] == 'api_key_missing'
    with pytest.raises(EmbeddingError): GeminiEmbeddingProvider(s).embed(['synthetic'],timeout=1)
    with pytest.raises(LLMError): GeminiLLMProvider(s).generate('{}',timeout=1)


@pytest.mark.parametrize('review_output', [
    {'supported':[], 'contradictory':False},
    {'supported':[True,True], 'contradictory':False},
    {'supported':[True], 'contradictory':True},
])
def test_wrong_review_coverage_or_conflict_never_publishes(review_output):
    from test_rag import source
    from app.services.rag_context import make_prompt
    transport,calls=transport_for()
    original=transport.handler
    def handler(request):
        content=json.loads(json.loads(request.content)['contents'][0]['parts'][0]['text'])
        if content.get('relevance_review'):
            return httpx.Response(200,json=payload_output(review_output))
        return original(request)
    result=GeminiLLMProvider(config(),transport=httpx.MockTransport(handler)).generate(make_prompt(QUESTION,[source(QUOTE)]),timeout=2)
    assert result.output == {'outcome':'insufficient_evidence','claims':[]}


def test_review_quota_stops_generation_without_fallback():
    from test_rag import source
    from app.services.rag_context import make_prompt
    transport,calls=transport_for(code=429)
    with pytest.raises(LLMError) as error:
        GeminiLLMProvider(config(),transport=transport).generate(make_prompt(QUESTION,[source(QUOTE)]),timeout=2)
    assert error.value.code == 'quota' and not error.value.transient
    assert calls == ['answer','review']


def test_worker_waits_for_consent_without_exhausting_index_attempts(db, workspace, people):
    from test_embeddings import seed_completed
    from app.models import EmbeddingJob
    from app.services.embedding_providers import profile_for
    s=config(gemini_live_requests_allowed=False)
    doc=seed_completed(db,workspace,identity(people,'owner'),(QUOTE,))
    embedding_jobs.request_index(db,workspace.id,doc.id,identity(people,'owner'),s)
    assert embedding_jobs.run_once(db,s) is False
    job=db.get(EmbeddingJob,(doc.id,profile_for(s).id),populate_existing=True)
    assert job.state == 'queued' and job.attempts == 0 and job.lease_id is None
