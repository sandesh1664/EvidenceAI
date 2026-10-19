"""Committed test-only schemas exercise concurrent embedding leases and deletion."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from sqlalchemy import cast,event,func,select,String

from test_workspace_concurrency import scratch_database
from test_document_concurrency import queue
from app.models import Document,ChunkEmbedding,EmbeddingJob
from app.services import document_jobs,document_service,embedding_jobs
from app.services.embedding_providers import EmbeddingEngine,FakeEmbeddingProvider,profile_for


@pytest.fixture
def index_queue(queue):
    factory,storage,settings,workspace_id,actor_id,document_id=queue
    settings.embedding_provider='fake'
    with factory() as db:
        claim=document_jobs.claim_job(db,settings)
        assert claim and document_jobs.process_claim(db,claim,settings,storage)
    return factory,storage,settings,workspace_id,actor_id,document_id


def test_concurrent_embedding_claims_only_one_valid_job(index_queue):
    factory,storage,settings,workspace_id,actor_id,document_id=index_queue
    locked,release=Event(),Event()
    def first_claim():
        with factory() as db:
            def hold(session):
                locked.set()
                if not release.wait(5):raise RuntimeError('Test release timed out')
            event.listen(db,'before_commit',hold,once=True)
            return embedding_jobs.claim_job(db,settings)
    def second_claim():
        with factory() as db:return embedding_jobs.claim_job(db,settings)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(first_claim)
        try:
            assert locked.wait(5)
            assert pool.submit(second_claim).result(timeout=3) is None
        finally:release.set()
        claim=first.result(timeout=5)
    assert claim
    with factory() as db:
        assert embedding_jobs.process_claim(db,claim,settings)
        assert not embedding_jobs.process_claim(db,claim,settings)
        assert db.get(EmbeddingJob,(document_id,claim.profile_id)).attempts==1
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding))==1


def test_document_deleted_while_provider_runs_never_recreates_vectors(index_queue):
    factory,storage,settings,workspace_id,actor_id,document_id=index_queue
    entered,release=Event(),Event()
    class Delayed:
        def embed(self,texts,**kwargs):
            entered.set()
            if not release.wait(5):raise RuntimeError('Test release timed out')
            return FakeEmbeddingProvider(settings.embedding_dimensions).embed(texts)
    with factory() as db:claim=embedding_jobs.claim_job(db,settings)
    def worker():
        with factory() as db:return embedding_jobs.process_claim(db,claim,settings,EmbeddingEngine(settings,Delayed()))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(worker)
        try:
            assert entered.wait(5)
            with factory() as db:document_service.delete_document(db,workspace_id,document_id,actor_id)
        finally:release.set()
        assert future.result(timeout=5) is False
    with factory() as db:
        assert db.get(Document,document_id) is None
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding))==0
        assert db.scalar(select(func.count()).select_from(EmbeddingJob))==0
        assert document_jobs.cleanup_one(db,storage)


def test_stale_provider_result_cannot_overwrite_new_reindex_generation(index_queue):
    factory,storage,settings,workspace_id,actor_id,document_id=index_queue
    entered,release=Event(),Event()
    class Delayed:
        def embed(self,texts,**kwargs):
            entered.set()
            if not release.wait(8):raise RuntimeError('Test release timed out')
            return [[1.0]*settings.embedding_dimensions for _ in texts]
    with factory() as db:first=embedding_jobs.claim_job(db,settings)
    def stale_worker():
        with factory() as db:return embedding_jobs.process_claim(db,first,settings,EmbeddingEngine(settings,Delayed()))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(stale_worker)
        try:
            assert entered.wait(5)
            with factory() as db:
                job=db.get(EmbeddingJob,(document_id,first.profile_id))
                job.lease_expires_at=db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1);db.commit()
                recovered=embedding_jobs.claim_job(db,settings)
                assert recovered and embedding_jobs.process_claim(db,recovered,settings)
                embedding_jobs.request_index(db,workspace_id,document_id,actor_id,settings,force=True)
                newest=embedding_jobs.claim_job(db,settings)
                assert newest and newest.generation!=first.generation
                assert embedding_jobs.process_claim(db,newest,settings)
                before=db.execute(select(cast(ChunkEmbedding.vector,String),ChunkEmbedding.generation)).all()
        finally:release.set()
        assert future.result(timeout=5) is False
    with factory() as db:
        assert db.execute(select(cast(ChunkEmbedding.vector,String),ChunkEmbedding.generation)).all()==before
        assert db.get(EmbeddingJob,(document_id,first.profile_id)).state=='done'
