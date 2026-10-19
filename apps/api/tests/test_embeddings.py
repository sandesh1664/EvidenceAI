"""Offline provider contract tests plus real PostgreSQL indexing and retrieval."""
from datetime import timedelta
import hashlib
import json
import math
import uuid

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import cast, func, select, String, text
from sqlalchemy.exc import IntegrityError, StatementError

from test_workspaces import client, people, encoded_password, workspace, identity, sign_in
from test_documents import doc_client, storage, settings, upload, stored_document
from app.core.config import Settings
from app.models import Document, DocumentChunk, ChunkEmbedding, EmbeddingJob, EmbeddingProfile
from app.services import embedding_jobs, search_service, document_jobs
from app.services.embedding_providers import (EmbeddingEngine, EmbeddingError, FakeEmbeddingProvider,
    OpenAIEmbeddingProvider, profile_for, validated_vectors)
from app.schemas.search import SearchRequest
from app.schemas.workspace import WorkspaceCreate
from app.services.workspace_service import create_workspace


def fake_settings(**kwargs):
    return Settings(_env_file=None,database_url='postgresql://localhost/test',embedding_provider='fake',**kwargs)


def hosted_settings(**kwargs):
    return Settings(_env_file=None,database_url='postgresql://localhost/test',embedding_provider='openai',
        embedding_model='text-embedding-3-small',embedding_dimensions=8,embedding_hosted_allowed=True,
        openai_api_key='dummy-offline-test-key',**kwargs)


@pytest.fixture
def embedding_settings(settings):
    settings.embedding_provider = 'fake'
    return settings


def seed_completed(db,workspace,actor_id,texts=('Solar panels convert sunlight into renewable electricity.',),name='solar.txt'):
    document = Document(workspace_id=workspace.id,uploaded_by=actor_id,original_filename=name,
        storage_key=uuid.uuid4().hex,mime_type='text/plain',file_size=100,checksum_sha256=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        processing_status='completed')
    db.add(document);db.flush()
    for index,content in enumerate(texts):
        db.add(DocumentChunk(document_id=document.id,workspace_id=workspace.id,chunk_index=index,text=content,
            page_number=index+1,section='Synthetic section',source_ref=f'document:{document.id}/page:{index+1}',
            char_start=0,char_end=len(content)))
    db.commit()
    return document


@pytest.fixture
def document(db,workspace,people):
    return seed_completed(db,workspace,identity(people,'owner'))


def base(workspace):return f'/api/v1/workspaces/{workspace.id}'
def index_path(workspace,document):return base(workspace)+f'/documents/{document.id}/index'


def index_document(db,workspace,document,people,settings,engine=None):
    embedding_jobs.request_index(db,workspace.id,document.id,identity(people,'owner'),settings)
    claim = embedding_jobs.claim_job(db,settings)
    assert claim
    assert embedding_jobs.process_claim(db,claim,settings,engine)
    return claim


def test_fake_embeddings_deterministic_and_normalized():
    engine = EmbeddingEngine(fake_settings())
    assert engine.embed(['solar electricity']) == engine.embed(['solar electricity'])
    assert engine.embed(['SOLAR electricity']) == engine.embed(['electricity solar'])
    assert engine.embed(['the and']) == engine.embed(['the and'])
    assert math.isclose(math.hypot(*engine.embed(['energy'])[0]),1)
    assert engine.embed(['solar']) != engine.embed(['medicine'])


@pytest.mark.parametrize('vector', [[1]*7,[1]*9,[float('nan')]*8,[float('inf')]*8,
    [0]*8,[True]*8,['1']*8,[1e308]*8])
def test_invalid_provider_vectors_rejected(vector):
    with pytest.raises(EmbeddingError):validated_vectors([vector],1,8)


@pytest.mark.parametrize('inputs', [[],[''],[' '],['x\x00y'],['x'*8001],['x']*17])
def test_embedding_input_limits(inputs):
    with pytest.raises(EmbeddingError):EmbeddingEngine(fake_settings()).embed(inputs)


def test_provider_retries_are_bounded_and_exponential():
    class Failing:
        calls=0
        def embed(self,*_,**__):
            self.calls+=1
            raise EmbeddingError('Embedding provider temporarily unavailable',transient=True)
    provider,pauses = Failing(),[]
    engine = EmbeddingEngine(fake_settings(),provider,sleep=pauses.append)
    with pytest.raises(EmbeddingError):engine.embed(['private input'])
    assert provider.calls==3 and pauses==[0.5,1.0]


def test_permanent_failure_is_not_retried():
    class Failing:
        calls=0
        def embed(self,*_,**__):
            self.calls+=1;raise EmbeddingError('Embedding provider rejected the request')
    provider=Failing()
    with pytest.raises(EmbeddingError):EmbeddingEngine(fake_settings(),provider,sleep=lambda _:None).embed(['text'])
    assert provider.calls==1


def test_hosted_contract_ordering_and_secret_handling():
    requests=[]
    def handler(request):
        requests.append(request)
        assert str(request.url)=='https://api.openai.com/v1/embeddings'
        body=json.loads(request.content)
        assert body==dict(model='text-embedding-3-small',dimensions=8,encoding_format='float',input=['first','second'])
        return httpx.Response(200,json={'model':body['model'],'data':[
            {'index':1,'embedding':[0,1,0,0,0,0,0,0]}, {'index':0,'embedding':[1,0,0,0,0,0,0,0]}]})
    settings=hosted_settings()
    engine=EmbeddingEngine(settings,OpenAIEmbeddingProvider(settings,transport=httpx.MockTransport(handler)))
    assert engine.embed(['first','second'])==[[1.,0,0,0,0,0,0,0],[0,1.,0,0,0,0,0,0]]
    assert len(requests)==1 and 'dummy-offline-test-key' not in repr(settings)


@pytest.mark.parametrize('kind', ['rate_limit','timeout','server_error','permanent','malformed','model','indices','nonfinite','dimensions','redirect'])
def test_hosted_failures_no_paid_network_and_no_error_leaks(kind):
    calls=[];settings=hosted_settings()
    def handler(request):
        calls.append(request)
        if kind=='rate_limit':return httpx.Response(429,headers={'Retry-After':'0.1'},text='PRIVATE provider body')
        if kind=='timeout':raise httpx.ReadTimeout('PRIVATE request details',request=request)
        if kind=='server_error':return httpx.Response(500,text='PRIVATE')
        if kind=='permanent':return httpx.Response(401,text='PRIVATE key')
        if kind=='redirect':return httpx.Response(302,headers={'Location':'https://evil.invalid'})
        if kind=='malformed':return httpx.Response(200,content=b'not JSON PRIVATE')
        payload={'model':'wrong-model' if kind=='model' else settings.embedding_model,
                 'data':[{'index':2 if kind=='indices' else 0,'embedding':[1]* (7 if kind=='dimensions' else 8)}]}
        if kind=='nonfinite':
            return httpx.Response(200,content=b'{"model":"text-embedding-3-small","data":[{"index":0,"embedding":[NaN,0,0,0,0,0,0,0]}]}')
        return httpx.Response(200,json=payload)
    engine=EmbeddingEngine(settings,OpenAIEmbeddingProvider(settings,transport=httpx.MockTransport(handler)),sleep=lambda _:None)
    with pytest.raises(EmbeddingError) as error:engine.embed(['PRIVATE document'])
    assert 'PRIVATE' not in str(error.value) and 'dummy-offline-test-key' not in str(error.value)
    assert len(calls)==(3 if kind in {'rate_limit','timeout','server_error'} else 1)


@pytest.mark.parametrize('options', [
    {'embedding_provider':'openai'}, {'embedding_dimensions':0}, {'embedding_model':'bad/model'},
    {'embedding_provider':'fake','embedding_model':'other'},
    {'embedding_request_budget_seconds':120,'embedding_job_lease_seconds':120},
])
def test_invalid_config(options):
    with pytest.raises(ValidationError):Settings(_env_file=None,database_url='postgresql://localhost/test',**options)


def test_profile_separates_model_revision_dimension_and_provider():
    settings=fake_settings()
    ids={profile_for(settings).id}
    for values in [{'embedding_revision':'2'},{'embedding_dimensions':64},{'embedding_provider':'disabled'}]:
        ids.add(profile_for(settings.model_copy(update=values)).id)
    assert len(ids)==4


def test_correct_indexing_and_source_chunks_unchanged(doc_client,db,workspace,people,document,embedding_settings):
    before=db.execute(select(DocumentChunk.id,DocumentChunk.text,DocumentChunk.source_ref).order_by(DocumentChunk.id)).all()
    response=doc_client.post(index_path(workspace,document),json={})
    assert response.status_code==202,response.text
    assert response.json()['state']=='queued'
    claim=embedding_jobs.claim_job(db,embedding_settings)
    assert claim and embedding_jobs.process_claim(db,claim,embedding_settings)
    status=doc_client.get(index_path(workspace,document)).json()
    assert status['state']=='done' and status['indexed_chunks']==status['total_chunks']==1
    assert status['current_generation_chunks']==1 and status['attempts']==1
    assert before==db.execute(select(DocumentChunk.id,DocumentChunk.text,DocumentChunk.source_ref).order_by(DocumentChunk.id)).all()
    assert not embedding_jobs.process_claim(db,claim,embedding_settings)
    assert db.scalar(select(func.count()).select_from(ChunkEmbedding))==1
    assert doc_client.post(index_path(workspace,document),json={}).json()['state']=='done'


def test_repeated_enqueue_does_not_duplicate_jobs(doc_client,db,workspace,document,embedding_settings):
    first=doc_client.post(index_path(workspace,document),json={}).json()
    second=doc_client.post(index_path(workspace,document),json={}).json()
    assert first['generation']==second['generation'] and second['attempts']==0
    assert db.scalar(select(func.count()).select_from(EmbeddingJob))==1
    assert doc_client.post(index_path(workspace,document),json={'force':True}).status_code==409


def test_unprocessed_document_not_indexable(doc_client,db,workspace,document,embedding_settings):
    document.processing_status='pending';db.commit()
    assert doc_client.post(index_path(workspace,document),json={}).status_code==409


@pytest.mark.parametrize('role,status', [('owner',202),('admin',202),('member',403),('outsider',404)])
def test_index_permissions(doc_client,people,workspace,document,embedding_settings,role,status):
    sign_in(doc_client,people,role)
    assert doc_client.post(index_path(workspace,document),json={}).status_code==status


@pytest.mark.parametrize('role', ['owner','admin','member'])
def test_search_relevance_and_read_permissions(doc_client,db,people,workspace,document,embedding_settings,role):
    index_document(db,workspace,document,people,embedding_settings)
    sign_in(doc_client,people,role)
    response=doc_client.post(base(workspace)+'/search',json={'query':'solar sunlight renewable electricity','limit':5})
    assert response.status_code==200,response.text
    result=response.json()
    assert len(result)==1 and result[0]['document_id']==str(document.id)
    assert 'Solar panels' in result[0]['excerpt'] and result[0]['similarity']>0.5
    assert result[0]['embedding_model']==profile_for(embedding_settings).identifier
    assert result[0]['page_number']==1 and result[0]['section']=='Synthetic section'
    assert set(result[0])=={'chunk_id','document_id','filename','excerpt','page_number','section','source_ref','similarity','embedding_model'}
    assert 'storage_key' not in response.text
    assert doc_client.get(index_path(workspace,document)).status_code==200


def test_exact_cosine_similarity_in_postgresql(db):
    assert db.scalar(text("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector"))==pytest.approx(1)
    assert db.scalar(text("SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector"))==pytest.approx(0)
    assert db.scalar(text("SELECT '[1,0,0]'::vector <=> '[-1,0,0]'::vector"))==pytest.approx(2)


def test_stable_order_and_limit(doc_client,db,people,workspace,embedding_settings):
    docs=[seed_completed(db,workspace,identity(people,'owner'),texts=('solar electricity',),name=f'{i}.txt') for i in range(3)]
    for document in docs:index_document(db,workspace,document,people,embedding_settings)
    first=doc_client.post(base(workspace)+'/search',json={'query':'solar electricity','limit':2}).json()
    second=doc_client.post(base(workspace)+'/search',json={'query':'solar electricity','limit':2}).json()
    assert first==second and len(first)==2
    assert [item['document_id'] for item in first]==[str(i) for i in sorted([d.id for d in docs])[:2]]
    assert all(item['similarity']==pytest.approx(1,abs=1e-6) for item in first)


def test_empty_unindexed_and_no_suitable_results(doc_client,db,people,workspace,document,embedding_settings):
    assert doc_client.post(base(workspace)+'/search',json={'query':'solar'}).json()==[]
    index_document(db,workspace,document,people,embedding_settings)
    embedding_settings.search_min_similarity=1
    assert doc_client.post(base(workspace)+'/search',json={'query':'unrelated xylophone improvisation'}).json()==[]


def test_document_filters_and_workspace_isolation(doc_client,db,people,workspace,document,embedding_settings):
    index_document(db,workspace,document,people,embedding_settings)
    other=create_workspace(db,identity(people,'owner'),WorkspaceCreate(name='Other'))
    hidden=seed_completed(db,other,identity(people,'owner'),texts=('solar sunlight renewable electricity PRIVATE OTHER WORKSPACE',))
    index_document(db,other,hidden,people,embedding_settings)
    response=doc_client.post(base(workspace)+'/search',json={'query':'solar sunlight renewable electricity'})
    assert len(response.json())==1 and 'PRIVATE OTHER' not in response.text
    assert doc_client.post(base(workspace)+'/search',json={'query':'solar','document_ids':[]}).json()==[]
    assert len(doc_client.post(base(workspace)+'/search',json={'query':'solar','document_ids':[str(document.id)]}).json())==1
    foreign=doc_client.post(base(workspace)+'/search',json={'query':'solar','document_ids':[str(hidden.id)]})
    missing=doc_client.post(base(workspace)+'/search',json={'query':'solar','document_ids':[str(uuid.uuid4())]})
    assert foreign.status_code==missing.status_code==404 and foreign.json()==missing.json()
    sign_in(doc_client,people,'outsider')
    forbidden=doc_client.post(base(workspace)+'/search',json={'query':'solar'})
    absent=doc_client.post(f'/api/v1/workspaces/{uuid.uuid4()}/search',json={'query':'solar'})
    assert forbidden.status_code==absent.status_code==404 and forbidden.json()==absent.json()


@pytest.mark.parametrize('body', [{}, {'query':' '}, {'query':'x'*2001}, {'query':'\x00'}, {'query':'solar','limit':0},
    {'query':'solar','limit':51}, {'query':'solar','limit':True}, {'query':'solar','document_ids':['invalid']},
    {'query':'solar','owner_id':str(uuid.uuid4())}])
def test_search_validation(doc_client,workspace,embedding_settings,body):
    assert doc_client.post(base(workspace)+'/search',json=body).status_code==422


@pytest.mark.parametrize('suffix,method,body', [('/search','POST',{'query':'solar'}),
    ('/documents/{id}/index','GET',None),('/documents/{id}/index','POST',{}),
    ('/documents/{id}/index/retry','POST',None)])
def test_new_endpoints_require_auth(doc_client,workspace,document,embedding_settings,suffix,method,body):
    doc_client.cookies.clear()
    assert doc_client.request(method,base(workspace)+suffix.format(id=document.id),json=body).status_code==401


@pytest.mark.parametrize('suffix,body', [('/search',{'query':'solar'}),('/documents/{id}/index',{}),
    ('/documents/{id}/index/retry',None)])
def test_new_writes_require_csrf(doc_client,workspace,document,embedding_settings,suffix,body):
    doc_client.headers.pop('X-CSRF-Protection')
    assert doc_client.post(base(workspace)+suffix.format(id=document.id),json=body).status_code==403


def test_sql_injection_query_is_data(doc_client,db,people,workspace,document,embedding_settings):
    index_document(db,workspace,document,people,embedding_settings)
    response=doc_client.post(base(workspace)+'/search',json={'query':"'); DROP TABLE document_chunks; --"})
    assert response.status_code==200
    assert db.scalar(select(func.count()).select_from(DocumentChunk))==1
    assert db.get(Document,document.id) is not None


def test_partial_batch_failure_preserves_completed_vectors_and_retry_resumes(doc_client,db,people,workspace,embedding_settings):
    embedding_settings.embedding_batch_size=1
    document=seed_completed(db,workspace,identity(people,'owner'),texts=('solar energy','wind electricity','battery storage'))
    embedding_jobs.request_index(db,workspace.id,document.id,identity(people,'owner'),embedding_settings)
    class Partial:
        calls=0
        def embed(self,texts,**kwargs):
            self.calls+=1
            if self.calls>1:raise EmbeddingError('PRIVATE provider failure')
            return FakeEmbeddingProvider(128).embed(texts)
    claim=embedding_jobs.claim_job(db,embedding_settings)
    provider=Partial()
    assert embedding_jobs.process_claim(db,claim,embedding_settings,EmbeddingEngine(embedding_settings,provider))
    status=doc_client.get(index_path(workspace,document)).json()
    assert status['state']=='failed' and status['indexed_chunks']==1 and 'PRIVATE' not in status['error']
    before=db.execute(select(ChunkEmbedding.chunk_id,cast(ChunkEmbedding.vector,String),ChunkEmbedding.generated_at)
        .where(ChunkEmbedding.status=='completed')).all()
    assert doc_client.post(index_path(workspace,document)+'/retry').status_code==202
    retry=embedding_jobs.claim_job(db,embedding_settings)
    assert retry and embedding_jobs.process_claim(db,retry,embedding_settings)
    after=db.execute(select(ChunkEmbedding.chunk_id,cast(ChunkEmbedding.vector,String),ChunkEmbedding.generated_at)
        .where(ChunkEmbedding.chunk_id==before[0][0])).all()
    assert before==after
    assert doc_client.get(index_path(workspace,document)).json()['indexed_chunks']==3


def test_job_retry_exhaustion_and_backoff(doc_client,db,people,workspace,document,embedding_settings):
    class Transient:
        def embed(self,*args,**kwargs):raise EmbeddingError('Embedding provider unavailable',transient=True)
    engine=EmbeddingEngine(embedding_settings,Transient(),sleep=lambda _:None)
    embedding_jobs.request_index(db,workspace.id,document.id,identity(people,'owner'),embedding_settings)
    for attempt in range(embedding_settings.embedding_job_max_attempts):
        claim=embedding_jobs.claim_job(db,embedding_settings)
        assert claim
        assert embedding_jobs.process_claim(db,claim,embedding_settings,engine)
        job=db.get(EmbeddingJob,(document.id,profile_for(embedding_settings).id))
        assert job.attempts==attempt+1
        if attempt+1 < embedding_settings.embedding_job_max_attempts:
            assert job.state=='queued' and embedding_jobs.claim_job(db,embedding_settings) is None
            job.available_at=db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1);db.commit()
        else:assert job.state=='failed'
    assert doc_client.post(index_path(workspace,document)+'/retry').status_code==409


def test_lease_recovery_stale_fencing_and_attempt_exhaustion(doc_client,db,people,workspace,document,embedding_settings):
    embedding_jobs.request_index(db,workspace.id,document.id,identity(people,'owner'),embedding_settings)
    first=embedding_jobs.claim_job(db,embedding_settings)
    assert first and embedding_jobs.claim_job(db,embedding_settings) is None
    job=db.get(EmbeddingJob,(document.id,first.profile_id))
    job.lease_expires_at=db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1);db.commit()
    second=embedding_jobs.claim_job(db,embedding_settings)
    assert second and first.lease_id!=second.lease_id
    assert not embedding_jobs.process_claim(db,first,embedding_settings)
    assert embedding_jobs.process_claim(db,second,embedding_settings)
    assert doc_client.get(index_path(workspace,document)).json()['attempts']==2


def test_reindex_version_and_dimension_isolation(doc_client,db,people,workspace,document,embedding_settings):
    old=index_document(db,workspace,document,people,embedding_settings)
    old_values=db.execute(select(ChunkEmbedding.chunk_id,cast(ChunkEmbedding.vector,String))).all()
    embedding_settings.embedding_revision='2';embedding_settings.embedding_dimensions=64
    assert doc_client.post(base(workspace)+'/search',json={'query':'solar electricity'}).json()==[]
    index_document(db,workspace,document,people,embedding_settings)
    assert db.scalar(select(func.count()).select_from(EmbeddingProfile))==2
    assert db.scalar(select(func.count()).select_from(ChunkEmbedding))==2
    assert old_values==db.execute(select(ChunkEmbedding.chunk_id,cast(ChunkEmbedding.vector,String))
        .where(ChunkEmbedding.profile_id==old.profile_id)).all()
    response=doc_client.post(base(workspace)+'/search',json={'query':'solar renewable electricity'}).json()
    assert response and response[0]['embedding_model'].endswith('@2/64')


def test_same_profile_force_reindex_and_old_generation_cannot_publish(doc_client,db,people,workspace,document,embedding_settings):
    old=index_document(db,workspace,document,people,embedding_settings)
    response=doc_client.post(index_path(workspace,document),json={'force':True})
    assert response.status_code==202 and response.json()['generation']!=str(old.generation)
    assert response.json()['indexed_chunks']==1 and response.json()['current_generation_chunks']==0
    current=embedding_jobs.claim_job(db,embedding_settings)
    assert not embedding_jobs.process_claim(db,old,embedding_settings)
    assert current and embedding_jobs.process_claim(db,current,embedding_settings)
    assert doc_client.get(index_path(workspace,document)).json()['current_generation_chunks']==1


def test_delete_during_indexing_removes_derived_data_and_fences_job(doc_client,db,people,workspace,document,embedding_settings):
    embedding_jobs.request_index(db,workspace.id,document.id,identity(people,'owner'),embedding_settings)
    claim=embedding_jobs.claim_job(db,embedding_settings)
    assert doc_client.delete(base(workspace)+f'/documents/{document.id}').status_code==204
    assert not embedding_jobs.process_claim(db,claim,embedding_settings)
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(EmbeddingJob))==0
    assert db.scalar(select(func.count()).select_from(ChunkEmbedding))==0
    assert doc_client.post(base(workspace)+'/search',json={'query':'solar'}).json()==[]


def test_extraction_auto_enqueues_and_worker_indexes(doc_client,db,workspace,embedding_settings,storage):
    document=stored_document(db,upload(doc_client,workspace,b'Solar renewable electricity sunlight'))
    assert document_jobs.run_once(db,embedding_settings,storage)
    assert db.get(Document,document.id).processing_status=='completed'
    status=doc_client.get(index_path(workspace,document)).json()
    assert status['state']=='done' and status['indexed_chunks']>0


def test_search_provider_failure_is_safe_503(doc_client,db,people,workspace,document,embedding_settings,monkeypatch):
    index_document(db,workspace,document,people,embedding_settings)
    def unavailable(*args,**kwargs):raise EmbeddingError('PRIVATE provider key and text')
    monkeypatch.setattr(search_service,'EmbeddingEngine',unavailable)
    response=doc_client.post(base(workspace)+'/search',json={'query':'solar'})
    assert response.status_code==503 and 'PRIVATE' not in response.text


def test_pg_constraints_enforce_profile_dimension_and_vector_dimension(db,people,workspace,document,embedding_settings):
    index_document(db,workspace,document,people,embedding_settings)
    embedding=db.scalar(select(ChunkEmbedding))
    embedding.vector=[1.0]*8
    with pytest.raises(IntegrityError):db.commit()
    db.rollback()
    embedding=db.scalar(select(ChunkEmbedding));embedding.dimensions=64;embedding.vector=[1.0]*64
    with pytest.raises(IntegrityError):db.commit()
    db.rollback()


def test_disabled_embeddings_do_not_send_or_index(doc_client,workspace,document,embedding_settings):
    embedding_settings.embedding_provider='disabled'
    assert doc_client.post(base(workspace)+'/search',json={'query':'solar'}).status_code==503
    assert doc_client.post(index_path(workspace,document),json={}).status_code==503


def test_evaluation_metric_definitions():
    from app.evaluate_retrieval import metrics
    result=metrics([['bad','yes'],['a']],[['yes'],['a','b']],2)
    assert result=={'recall_at_k':0.75,'precision_at_k':0.5,'mean_reciprocal_rank':0.75}


@pytest.mark.parametrize('role,status', [('owner',202),('admin',202),('member',403),('outsider',404)])
def test_index_retry_permissions(doc_client,db,people,workspace,document,embedding_settings,role,status):
    class Failure:
        def embed(self,*args,**kwargs):raise EmbeddingError('Embedding provider rejected the request')
    index_document(db,workspace,document,people,embedding_settings,EmbeddingEngine(embedding_settings,Failure()))
    sign_in(doc_client,people,role)
    assert doc_client.post(index_path(workspace,document)+'/retry').status_code==status


def test_forced_rebuild_failure_preserves_previously_usable_vectors(doc_client,db,people,workspace,document,embedding_settings):
    index_document(db,workspace,document,people,embedding_settings)
    initial=db.execute(select(cast(ChunkEmbedding.vector,String),ChunkEmbedding.generation)).all()
    assert doc_client.post(index_path(workspace,document),json={'force':True}).status_code==202
    class Failure:
        def embed(self,*args,**kwargs):raise EmbeddingError('Embedding provider rejected the request')
    claim=embedding_jobs.claim_job(db,embedding_settings)
    assert claim and embedding_jobs.process_claim(db,claim,embedding_settings,EmbeddingEngine(embedding_settings,Failure()))
    assert db.execute(select(cast(ChunkEmbedding.vector,String),ChunkEmbedding.generation)).all()==initial
    status=doc_client.get(index_path(workspace,document)).json()
    assert status['state']=='failed' and status['indexed_chunks']==1 and status['current_generation_chunks']==0
    assert doc_client.post(base(workspace)+'/search',json={'query':'solar sunlight electricity'}).json()


def test_interrupted_embedding_attempt_limit(doc_client,db,people,workspace,document,embedding_settings):
    embedding_settings.embedding_job_max_attempts=1
    embedding_jobs.request_index(db,workspace.id,document.id,identity(people,'owner'),embedding_settings)
    claim=embedding_jobs.claim_job(db,embedding_settings)
    job=db.get(EmbeddingJob,(document.id,claim.profile_id))
    job.lease_expires_at=db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1);db.commit()
    assert embedding_jobs.claim_job(db,embedding_settings) is None
    assert db.get(EmbeddingJob,(document.id,claim.profile_id)).state=='failed'
    assert doc_client.post(index_path(workspace,document)+'/retry').status_code==409


def test_search_rechecks_membership_after_embedding(doc_client,db,people,workspace,document,embedding_settings):
    from app.models import WorkspaceMember
    index_document(db,workspace,document,people,embedding_settings)
    class RevokeDuringCall:
        profile=profile_for(embedding_settings)
        def embed(self,texts):
            record=db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id==workspace.id,
                                                         WorkspaceMember.user_id==identity(people,'member')))
            db.delete(record);db.commit()
            return FakeEmbeddingProvider(embedding_settings.embedding_dimensions).embed(texts)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        search_service.search(db,workspace.id,identity(people,'member'),SearchRequest(query='solar electricity'),
                              embedding_settings,RevokeDuringCall())
    assert error.value.status_code==404


def test_source_generation_profile_mismatch_fails_without_overwrite(doc_client,db,people,workspace,document,embedding_settings):
    embedding_jobs.request_index(db,workspace.id,document.id,identity(people,'owner'),embedding_settings)
    claim=embedding_jobs.claim_job(db,embedding_settings)
    wrong=embedding_settings.model_copy(update={'embedding_revision':'wrong'})
    assert embedding_jobs.process_claim(db,claim,embedding_settings,EmbeddingEngine(wrong))
    job=db.get(EmbeddingJob,(document.id,claim.profile_id))
    assert job.state=='failed' and job.error=='Embedding model identity mismatch'
    assert db.scalar(select(func.count()).select_from(ChunkEmbedding).where(ChunkEmbedding.status=='completed'))==0


def test_repeatable_synthetic_evaluation_uses_real_pgvector_and_isolated_data():
    from app.evaluate_retrieval import evaluate
    report=evaluate()
    assert report['query_count']==8 and report['k']==2
    assert report['recall_at_k']==pytest.approx(0.9375)
    assert report['precision_at_k']==pytest.approx(0.9375)
    assert report['mean_reciprocal_rank']==1
    assert report['workspace_isolation_correctness']==1
    assert report['workspace_isolation_checks']==10
    assert report['latency_mean_ms']>0


def test_live_hosted_transport_is_blocked_by_test_harness():
    with httpx.Client(trust_env=False) as client:
        with pytest.raises(AssertionError,match='live HTTP is disabled'):
            client.post('https://api.openai.com/v1/embeddings',json={'input':'must never leave tests'})
