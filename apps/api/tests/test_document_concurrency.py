"""Real worker races use independent connections and a disposable test-only schema."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import BytesIO
from threading import Event
import uuid

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers, UploadFile

from test_workspace_concurrency import scratch_database
from app.core.config import Settings
from app.models import User, Document, DocumentChunk, DocumentJob, StorageCleanup
from app.schemas.workspace import WorkspaceCreate
from app.services.workspace_service import create_workspace
from app.services import document_service, document_jobs
from app.services.document_storage import LocalDocumentStorage


@pytest.fixture
def queue(scratch_database,tmp_path):
    factory = sessionmaker(scratch_database,expire_on_commit=False)
    storage = LocalDocumentStorage(tmp_path.resolve()/'private')
    settings = Settings(app_env='test',auth_allow_insecure_http=True)
    with factory() as db:
        owner = User(email=f'{uuid.uuid4()}@example.com',display_name='Owner',password_hash='session-only-test')
        db.add(owner);db.commit()
        actor_id = owner.id
        workspace = create_workspace(db,actor_id,WorkspaceCreate(name='Queue race'))
        workspace_id = workspace.id
        file = UploadFile(BytesIO(b'Deterministic background text'),filename='queued.txt',headers=Headers({'content-type':'text/plain'}))
        document = document_service.upload_document(db,workspace_id,actor_id,file,settings,storage)
        document_id = document.id
    return factory,storage,settings,workspace_id,actor_id,document_id


def test_concurrent_workers_claim_document_only_once(queue):
    factory,storage,settings,workspace_id,actor_id,document_id = queue
    locked,release = Event(),Event()
    def first_claim():
        with factory() as db:
            def hold(session):
                locked.set()
                if not release.wait(5): raise RuntimeError('Test lock not released')
            event.listen(db,'before_commit',hold,once=True)
            return document_jobs.claim_job(db,settings)
    def second_claim():
        with factory() as db:
            return document_jobs.claim_job(db,settings)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_claim)
        try:
            assert locked.wait(5)
            # Must finish WITHOUT waiting on the first worker's Document row lock.
            assert pool.submit(second_claim).result(timeout=3) is None
        finally:
            release.set()
        claim = first.result(timeout=5)
    assert claim is not None
    with factory() as db:
        assert document_jobs.process_claim(db,claim,settings,storage)
        assert not document_jobs.process_claim(db,claim,settings,storage)
        assert db.get(Document,document_id).processing_attempts == 1
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 1


def test_delete_while_worker_is_parsing_never_recreates_chunks(queue,monkeypatch):
    factory,storage,settings,workspace_id,actor_id,document_id = queue
    with factory() as db: claim = document_jobs.claim_job(db,settings)
    parsing,release = Event(),Event()
    original = document_jobs.run_parser
    def delayed_parser(*args,**kwargs):
        parsing.set()
        if not release.wait(5): raise RuntimeError('Test parser not released')
        return original(*args,**kwargs)
    monkeypatch.setattr(document_jobs,'run_parser',delayed_parser)
    def worker():
        with factory() as db: return document_jobs.process_claim(db,claim,settings,storage)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        try:
            assert parsing.wait(5)
            with factory() as db:
                document_service.delete_document(db,workspace_id,document_id,actor_id)
        finally:
            release.set()
        assert future.result(timeout=5) is False
    with factory() as db:
        assert db.get(Document,document_id) is None
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
        assert document_jobs.cleanup_one(db,storage)
    assert list(storage.root.iterdir()) == []


def test_duplicate_upload_race_creates_one_document_and_one_job(queue):
    factory,storage,settings,workspace_id,actor_id,existing_document_id = queue
    from threading import Barrier
    from fastapi import HTTPException
    barrier = Barrier(2)
    def upload():
        file = UploadFile(BytesIO(b'A different concurrent upload'),filename='race.txt',headers=Headers({'content-type':'text/plain'}))
        with factory() as db:
            barrier.wait(timeout=5)
            try:
                document_service.upload_document(db,workspace_id,actor_id,file,settings,storage)
                return 202
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        first,second = pool.submit(upload),pool.submit(upload)
        assert sorted([first.result(timeout=8),second.result(timeout=8)]) == [202,409]
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 2  # seed + one winning race
        assert db.scalar(select(func.count()).select_from(DocumentJob)) == 2
        assert db.scalar(select(func.count()).select_from(StorageCleanup)) == 0
    assert len(list(storage.root.iterdir())) == 2


def test_abandoned_upload_cleaned_during_publish_is_not_committed(queue,monkeypatch):
    factory,storage,settings,workspace_id,actor_id,document_id = queue
    from fastapi import HTTPException
    promoted,release = Event(),Event()
    original = storage.promote
    def delayed_promote(key):
        original(key)
        promoted.set()
        if not release.wait(5): raise RuntimeError('Test upload not released')
    monkeypatch.setattr(storage,'promote',delayed_promote)
    def upload():
        with factory() as db:
            file = UploadFile(BytesIO(b'Abandoned upload content'),filename='abandoned.txt',headers=Headers({'content-type':'text/plain'}))
            try:
                document_service.upload_document(db,workspace_id,actor_id,file,settings,storage)
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(upload)
        try:
            assert promoted.wait(5)
            with factory() as db:
                intent = db.scalar(select(StorageCleanup))
                assert intent is not None
                intent.available_at = db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)
                db.commit()
                assert document_jobs.cleanup_one(db,storage)
        finally:
            release.set()
        assert future.result(timeout=5) == 503
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 1
        assert db.scalar(select(func.count()).select_from(StorageCleanup)) == 0
    assert len(list(storage.root.iterdir())) == 1
