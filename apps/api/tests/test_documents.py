"""Authenticated document API + real parser/worker, isolated DB writes and storage."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import os
import stat
import uuid

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from pypdf import PdfWriter
from pypdf.actions import JavaScript
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from test_workspaces import (client, people, encoded_password, workspace, identity, sign_in)
from app.core.config import get_settings, Settings
from app.main import app
from app.models import Document, DocumentChunk, DocumentJob, StorageCleanup
from app.services.document_storage import LocalDocumentStorage, StorageError, UploadTooLarge, get_document_storage
from app.services import document_service, document_jobs
from app.services.document_parsing import ParsingError, run_parser, validate_filename
from app.services.document_chunking import chunk_sources
from app.schemas.workspace import WorkspaceCreate
from app.services.workspace_service import create_workspace


def pdf_bytes(texts=('First page text','Second page text'), *, encrypted=False, scripts=False):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612,height=792)
        if text:
            font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),
                                     NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({
                NameObject('/F1'):writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode())
            page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted: writer.encrypt('unavailable-password')
    if scripts:
        writer.add_open_action(JavaScript('app.alert("DO NOT EXECUTE")'))
        writer.add_attachment('unused.txt',b'not extracted')
    target = BytesIO()
    writer.write(target)
    return target.getvalue()


@pytest.fixture
def storage(tmp_path):
    return LocalDocumentStorage(tmp_path.resolve()/'private')


@pytest.fixture
def doc_client(client,storage):
    app.dependency_overrides[get_document_storage] = lambda:storage
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_document_storage,None)


@pytest.fixture
def settings(doc_client):
    return app.dependency_overrides[get_settings]()


def base(workspace): return f'/api/v1/workspaces/{workspace.id}/documents'


def upload(client,workspace,data=b'Private research text',name='research.txt',mime='text/plain'):
    return client.post(base(workspace)+'/',files={'file':(name,data,mime)})


def stored_document(db,response):
    assert response.status_code == 202,response.text
    return db.get(Document,uuid.UUID(response.json()['id']))


def process(db,settings,storage):
    claim = document_jobs.claim_job(db,settings)
    assert claim is not None
    assert document_jobs.process_claim(db,claim,settings,storage)
    return claim


@pytest.mark.parametrize('name,mime,data', [
    ('research.txt','text/plain',b'Plain UTF-8 text\r\nnext line'),
    ('research.md','text/markdown',b'# Heading\n\nMarkdown **text**'),
    ('research.pdf','application/pdf',pdf_bytes()),
])
def test_successful_upload_and_background_extraction(doc_client,db,people,workspace,settings,storage,name,mime,data):
    document = stored_document(db,upload(doc_client,workspace,data,name,mime))
    assert document.processing_status == 'pending' and document.processing_attempts == 0
    assert document.mime_type == mime and document.file_size == len(data)
    import hashlib
    assert document.checksum_sha256 == hashlib.sha256(data).hexdigest()
    assert document.original_filename == name
    assert len(document.storage_key) == 32 and name not in document.storage_key
    assert db.get(DocumentJob,document.id).state == 'queued'
    assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
    assert db.scalar(select(func.count()).select_from(StorageCleanup)) == 0
    assert stat.S_IMODE(storage.root.stat().st_mode) == 0o700
    assert stat.S_IMODE((storage.root/document.storage_key).stat().st_mode) == 0o600
    document_id = document.id
    process(db,settings,storage)
    db.expire_all()
    document = db.get(Document,document_id)
    assert document.processing_status == 'completed' and document.processing_error is None
    assert document.processing_attempts == 1 and document.last_processed_at is not None
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id)
                        .order_by(DocumentChunk.chunk_index)).all()
    assert chunks and all(c.workspace_id == workspace.id and c.text.strip() for c in chunks)
    assert document_jobs.claim_job(db,settings) is None
    assert db.get(DocumentJob,document_id).state == 'done'


def test_pdf_page_references_and_scripts_are_not_executed(doc_client,db,workspace,settings,storage):
    document = stored_document(db,upload(doc_client,workspace,pdf_bytes(scripts=True),'references.pdf','application/pdf'))
    process(db,settings,storage)
    chunks = db.scalars(select(DocumentChunk).order_by(DocumentChunk.chunk_index)).all()
    assert [c.page_number for c in chunks] == [1,2]
    assert 'First page text' in chunks[0].text and 'Second page text' in chunks[1].text
    assert chunks[0].source_ref == f'document:{document.id}/page:1'
    assert chunks[1].source_ref == f'document:{document.id}/page:2'
    assert 'DO NOT EXECUTE' not in ''.join(c.text for c in chunks)


def test_metadata_and_pagination_hide_storage_and_text(doc_client,db,workspace):
    response = upload(doc_client,workspace)
    stored_document(db,response)
    item = doc_client.get(base(workspace)+'/'+response.json()['id'])
    assert item.status_code == 200
    assert set(item.json()) == {'id','workspace_id','uploaded_by','original_filename','mime_type','file_size',
        'checksum_sha256','processing_status','processing_error','processing_attempts','last_processed_at','created_at','updated_at'}
    assert 'storage_key' not in item.text and 'Private research text' not in item.text
    assert len(doc_client.get(base(workspace)+'/?limit=1').json()) == 1
    assert doc_client.get(base(workspace)+'/?offset=1').json() == []
    for query in ['limit=0','limit=101','offset=-1']:
        assert doc_client.get(base(workspace)+'/?'+query).status_code == 422


@pytest.mark.parametrize('role', ['owner','admin','member'])
def test_authorized_downloads(doc_client,db,people,workspace,role):
    document = stored_document(db,upload(doc_client,workspace))
    sign_in(doc_client,people,role)
    response = doc_client.get(base(workspace)+f'/{document.id}/download')
    assert response.status_code == 200 and response.content == b'Private research text'
    assert response.headers['content-type'] == 'application/octet-stream'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert 'storage' not in response.headers['content-disposition']
    assert response.headers['cache-control'] == 'no-store'
    assert doc_client.get(base(workspace)+'/').status_code == 200
    assert doc_client.get(base(workspace)+f'/{document.id}').status_code == 200


@pytest.mark.parametrize('role,status', [('owner',202),('admin',202),('member',403),('outsider',404)])
def test_upload_permissions(doc_client,people,workspace,role,status):
    sign_in(doc_client,people,role)
    assert upload(doc_client,workspace).status_code == status


@pytest.mark.parametrize('method,suffix', [('GET','/'),('GET','/{id}'),('GET','/{id}/download'),
    ('DELETE','/{id}'),('POST','/{id}/retry')])
def test_nonmember_and_missing_workspace_indistinguishable(doc_client,db,people,workspace,method,suffix):
    document = stored_document(db,upload(doc_client,workspace))
    suffix = suffix.format(id=document.id)
    sign_in(doc_client,people,'outsider')
    denied = doc_client.request(method,base(workspace)+suffix)
    absent = doc_client.request(method,f'/api/v1/workspaces/{uuid.uuid4()}/documents'+suffix)
    assert denied.status_code == absent.status_code == 404
    assert denied.json() == absent.json() == {'detail':'Workspace not found'}


@pytest.mark.parametrize('suffix', ['', '/download','/retry'])
def test_document_id_cannot_be_used_in_another_accessible_workspace(doc_client,db,people,workspace,suffix):
    document = stored_document(db,upload(doc_client,workspace))
    other = create_workspace(db,identity(people,'owner'),WorkspaceCreate(name='Another workspace'))
    method = 'POST' if suffix == '/retry' else 'GET'
    response = doc_client.request(method,base(other)+f'/{document.id}'+suffix)
    assert response.status_code == 404 and response.json()['detail'] == 'Document not found'


@pytest.mark.parametrize('method,suffix', [('POST','/'),('GET','/'),('GET','/{id}'),
    ('GET','/{id}/download'),('DELETE','/{id}'),('POST','/{id}/retry')])
def test_all_document_endpoints_require_real_auth(doc_client,workspace,method,suffix):
    doc_client.cookies.clear()
    assert doc_client.request(method,base(workspace)+suffix.format(id=uuid.uuid4())).status_code == 401


@pytest.mark.parametrize('suffix,method', [('/', 'POST'),('/{id}','DELETE'),('/{id}/retry','POST')])
def test_document_csrf(doc_client,workspace,suffix,method):
    doc_client.headers.pop('X-CSRF-Protection')
    assert doc_client.request(method,base(workspace)+suffix.format(id=uuid.uuid4())).status_code == 403


@pytest.mark.parametrize('kind,data,name,mime,status', [
    ('unsupported',b'abc','a.docx','application/octet-stream',415),
    ('fake_pdf',b'This is not PDF','a.pdf','application/pdf',422),
    ('mime_mismatch',b'Valid UTF8','a.txt','application/pdf',422),
    ('binary',b'abc\x00def','a.txt','text/plain',422),
    ('invalid_utf8',b'\xff\xfe','a.txt','text/plain',422),
    ('pdf_as_text',pdf_bytes(),'a.txt','text/plain',422),
    ('malformed',b'%PDF-1.7\nbroken %%EOF','a.pdf','application/pdf',422),
    ('encrypted',pdf_bytes(encrypted=True),'a.pdf','application/pdf',422),
    ('empty',b'','a.txt','text/plain',422),
])
def test_file_validation_and_complete_cleanup(doc_client,db,workspace,storage,kind,data,name,mime,status):
    response = upload(doc_client,workspace,data,name,mime)
    assert response.status_code == status,response.text
    assert list(storage.root.iterdir()) == []
    assert db.scalar(select(func.count()).select_from(Document)) == 0
    assert db.scalar(select(func.count()).select_from(DocumentJob)) == 0
    assert db.scalar(select(func.count()).select_from(StorageCleanup)) == 0
    decoded = data[:20].decode('utf8',errors='ignore')
    if decoded: assert decoded not in response.text


@pytest.mark.parametrize('name', ['../paper.txt','nested/paper.txt','nested\\paper.txt','..paper.txt',
    'paper\x00.txt','paper\n.txt','paper\u202e.txt',' C.txt','C:paper.txt','x'*260+'.txt'])
def test_unsafe_filename_rejected(name):
    with pytest.raises(ValueError): validate_filename(name)


def test_filename_traversal_http(doc_client,workspace,storage):
    response = upload(doc_client,workspace,b'content','../outside.txt')
    assert response.status_code == 422
    assert list(storage.root.iterdir()) == []


def test_strict_file_limit_and_exact_boundary(doc_client,db,workspace,storage,settings):
    settings.document_upload_max_bytes = 32
    assert upload(doc_client,workspace,b'x'*33).status_code == 413
    assert list(storage.root.iterdir()) == []
    assert upload(doc_client,workspace,b'x'*32).status_code == 202


def test_body_limit_before_multipart_spooling(doc_client,workspace,settings,storage):
    settings.document_upload_max_bytes = 32
    response = upload(doc_client,workspace,b'x'*70000)
    assert response.status_code == 413
    assert list(storage.root.iterdir()) == []


def test_duplicate_same_workspace_conflict_other_workspace_allowed(doc_client,db,people,workspace,storage):
    document = stored_document(db,upload(doc_client,workspace))
    assert upload(doc_client,workspace,name='renamed.txt').status_code == 409
    assert len(list(storage.root.iterdir())) == 1
    assert db.scalar(select(func.count()).select_from(StorageCleanup)) == 0
    other = create_workspace(db,identity(people,'owner'),WorkspaceCreate(name='Other'))
    assert upload(doc_client,other).status_code == 202
    assert db.scalar(select(func.count()).select_from(Document)) == 2


@pytest.mark.parametrize('kind,message', [('scanned','OCR is not supported'),('empty','contains no text')])
def test_empty_and_image_only_pdf_fail_without_ocr(doc_client,db,workspace,settings,storage,kind,message):
    data = pdf_bytes(texts=('',) if kind == 'scanned' else ())
    document = stored_document(db,upload(doc_client,workspace,data,'empty.pdf','application/pdf'))
    document_id = document.id
    process(db,settings,storage)
    db.expire_all()
    document = db.get(Document,document_id)
    assert document.processing_status == 'failed' and message in document.processing_error
    assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0


def test_utf8_bom_markdown_sections_and_newlines(doc_client,db,workspace,settings,storage):
    text = '\ufeff# First\r\n\r\nOne.\r# Second\nTwo.'
    document = stored_document(db,upload(doc_client,workspace,text.encode(),'notes.md','text/markdown'))
    process(db,settings,storage)
    chunks = db.scalars(select(DocumentChunk).order_by(DocumentChunk.chunk_index)).all()
    assert [c.section for c in chunks] == ['First','Second']
    assert all('\r' not in c.text and '\ufeff' not in c.text and c.page_number is None for c in chunks)
    assert chunks[1].char_start == len('# First\n\nOne.\n')


def test_retry_failed_preserves_identity_and_chunks_are_idempotent(doc_client,db,workspace,settings,storage,monkeypatch):
    document = stored_document(db,upload(doc_client,workspace))
    document_id = document.id
    real_parser = document_jobs.run_parser
    monkeypatch.setattr(document_jobs,'run_parser',lambda *_: (_ for _ in ()).throw(ParsingError('timeout')))
    process(db,settings,storage)
    assert doc_client.get(base(workspace)+f'/{document_id}').json()['processing_status'] == 'failed'
    response = doc_client.post(base(workspace)+f'/{document_id}/retry')
    assert response.status_code == 202 and response.json()['id'] == str(document_id)
    assert doc_client.post(base(workspace)+f'/{document_id}/retry').status_code == 409
    monkeypatch.setattr(document_jobs,'run_parser',real_parser)
    claim = process(db,settings,storage)
    initial = db.scalars(select(DocumentChunk.id)).all()
    assert initial and not document_jobs.process_claim(db,claim,settings,storage)
    assert db.scalars(select(DocumentChunk.id)).all() == initial
    assert doc_client.post(base(workspace)+f'/{document_id}/retry').status_code == 409


@pytest.mark.parametrize('role,status', [('owner',202),('admin',202),('member',403)])
def test_retry_permissions(doc_client,db,people,workspace,role,status,settings,storage):
    document = stored_document(db,upload(doc_client,workspace,pdf_bytes(texts=('',)),'scanned.pdf','application/pdf'))
    process(db,settings,storage)
    sign_in(doc_client,people,role)
    assert doc_client.post(base(workspace)+f'/{document.id}/retry').status_code == status


def test_max_attempt_limit(doc_client,db,workspace,settings,storage):
    document = stored_document(db,upload(doc_client,workspace,pdf_bytes(texts=('',)),'scanned.pdf','application/pdf'))
    for attempt in range(settings.document_max_attempts):
        process(db,settings,storage)
        response = doc_client.post(base(workspace)+f'/{document.id}/retry')
        assert response.status_code == (202 if attempt+1 < settings.document_max_attempts else 409)
    assert db.get(Document,document.id).processing_attempts == settings.document_max_attempts


def test_interrupted_job_recovery_and_stale_fencing(doc_client,db,workspace,settings,storage):
    document = stored_document(db,upload(doc_client,workspace))
    first = document_jobs.claim_job(db,settings)
    assert first and document_jobs.claim_job(db,settings) is None
    job = db.get(DocumentJob,document.id)
    job.lease_expires_at = db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)
    db.commit()
    second = document_jobs.claim_job(db,settings)
    assert second and first.lease_id != second.lease_id
    assert not document_jobs.process_claim(db,first,settings,storage)
    assert document_jobs.process_claim(db,second,settings,storage)
    assert db.get(Document,document.id).processing_attempts == 2
    assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 1


def test_interrupted_job_exhaustion(doc_client,db,workspace,settings,storage):
    document = stored_document(db,upload(doc_client,workspace))
    settings.document_max_attempts = 1
    assert document_jobs.claim_job(db,settings)
    job = db.get(DocumentJob,document.id)
    job.lease_expires_at = db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)
    db.commit()
    assert document_jobs.claim_job(db,settings) is None
    assert db.get(Document,document.id).processing_status == 'failed'
    assert db.get(DocumentJob,document.id).state == 'failed'


def test_transient_storage_failure_retries_with_backoff(doc_client,db,workspace,settings,storage,monkeypatch):
    document = stored_document(db,upload(doc_client,workspace))
    original = storage.open
    def unavailable(*_,**__): raise StorageError('sensitive details never returned')
    monkeypatch.setattr(storage,'open',unavailable)
    process(db,settings,storage)
    assert db.get(Document,document.id).processing_status == 'pending'
    assert document_jobs.claim_job(db,settings) is None
    job = db.get(DocumentJob,document.id)
    job.available_at = db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(storage,'open',original)
    process(db,settings,storage)
    assert db.get(Document,document.id).processing_status == 'completed'


@pytest.mark.parametrize('role,status', [('owner',204),('admin',204),('member',403)])
def test_deletion_permissions_and_durable_cleanup(doc_client,db,people,workspace,settings,storage,role,status):
    document = stored_document(db,upload(doc_client,workspace))
    document_id,key = document.id,document.storage_key
    process(db,settings,storage)
    sign_in(doc_client,people,role)
    assert doc_client.delete(base(workspace)+f'/{document_id}').status_code == status
    if status == 204:
        assert db.get(Document,document_id) is None and db.get(DocumentJob,document_id) is None
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
        assert doc_client.get(base(workspace)+f'/{document_id}/download').status_code == 404
        assert db.get(StorageCleanup,key) is not None and (storage.root/key).exists()
        assert document_jobs.cleanup_one(db,storage)
        assert not (storage.root/key).exists() and db.get(StorageCleanup,key) is None
    else:
        assert doc_client.get(base(workspace)+f'/{document_id}/download').status_code == 200


def test_delete_during_processing_fences_late_worker(doc_client,db,workspace,settings,storage):
    document = stored_document(db,upload(doc_client,workspace))
    claim = document_jobs.claim_job(db,settings)
    assert doc_client.delete(base(workspace)+f'/{document.id}').status_code == 204
    assert not document_jobs.process_claim(db,claim,settings,storage)
    assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
    assert document_jobs.cleanup_one(db,storage)


def test_failed_file_cleanup_is_durable_and_recoverable(doc_client,db,workspace,storage,monkeypatch):
    document = stored_document(db,upload(doc_client,workspace))
    key = document.storage_key
    assert doc_client.delete(base(workspace)+f'/{document.id}').status_code == 204
    original = storage.delete
    def unavailable(*_): raise StorageError('private path')
    monkeypatch.setattr(storage,'delete',unavailable)
    assert document_jobs.cleanup_one(db,storage)
    intent = db.get(StorageCleanup,key)
    assert intent.attempts == 1 and intent.last_error == 'Storage cleanup unavailable'
    assert (storage.root/key).exists()
    intent.available_at = db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(storage,'delete',original)
    assert document_jobs.cleanup_one(db,storage)
    assert db.get(StorageCleanup,key) is None and not (storage.root/key).exists()


def test_failed_upload_database_transaction_rolls_back_metadata_job_and_file(doc_client,db,workspace,storage):
    def fail_job(session,context,instances):
        if any(isinstance(obj,DocumentJob) for obj in session.new):
            raise IntegrityError('private SQL',{},RuntimeError('private'))
    event.listen(db,'before_flush',fail_job)
    try:
        response = upload(doc_client,workspace)
    finally:
        event.remove(db,'before_flush',fail_job)
    assert response.status_code == 409 and 'private' not in response.text
    for model in [Document,DocumentJob,StorageCleanup]:
        assert db.scalar(select(func.count()).select_from(model)) == 0
    assert list(storage.root.iterdir()) == []


def test_stale_upload_intent_recovers_part_file(db,storage):
    key = storage.new_key()
    db.add(StorageCleanup(storage_key=key,available_at=db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)))
    db.commit()
    storage.stage(key,BytesIO(b'partial'),100)
    assert document_jobs.cleanup_one(db,storage)
    assert list(storage.root.iterdir()) == []


def test_cleanup_intent_never_unlinks_live_original(doc_client,db,workspace,storage):
    document = stored_document(db,upload(doc_client,workspace))
    key = document.storage_key
    db.add(StorageCleanup(storage_key=key,available_at=db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)))
    db.commit()
    assert document_jobs.cleanup_one(db,storage)
    assert (storage.root/key).exists() and db.get(StorageCleanup,key) is None


def test_checksum_tampering_is_detected(doc_client,db,workspace,settings,storage):
    document = stored_document(db,upload(doc_client,workspace))
    (storage.root/document.storage_key).write_bytes(b'tampered')
    process(db,settings,storage)
    assert db.get(Document,document.id).processing_error == 'Original checksum mismatch'


def test_symlink_download_escape_rejected(doc_client,db,workspace,storage,tmp_path):
    document = stored_document(db,upload(doc_client,workspace))
    target = storage.root/document.storage_key
    target.unlink()
    outside = tmp_path/'private-outside.txt'
    outside.write_text('Must never be downloaded')
    target.symlink_to(outside)
    response = doc_client.get(base(workspace)+f'/{document.id}/download')
    assert response.status_code == 503 and 'Must never' not in response.text


def test_storage_symlink_root_and_unsafe_keys_rejected(tmp_path,storage):
    actual = tmp_path/'actual'; actual.mkdir()
    link = tmp_path/'link';link.symlink_to(actual,target_is_directory=True)
    with pytest.raises(StorageError): LocalDocumentStorage(link)
    for key in ['../outside','/tmp/outside','a/b','.'*32,'A'*32]:
        with pytest.raises(StorageError): storage.open(key)
        with pytest.raises(StorageError): storage.delete(key)


def test_partial_stream_error_cleans_staging(storage):
    class BrokenStream:
        calls = 0
        def read(self,size):
            self.calls += 1
            if self.calls > 1: raise OSError('private')
            return b'partial'
    with pytest.raises(StorageError): storage.stage(storage.new_key(),BrokenStream(),100)
    assert list(storage.root.iterdir()) == []


def test_parser_page_and_character_limits(doc_client,db,workspace,settings,storage):
    settings.document_max_pages = 1
    assert upload(doc_client,workspace,pdf_bytes(),'many.pdf','application/pdf').status_code == 422
    settings.document_max_text_chars = 5
    document = stored_document(db,upload(doc_client,workspace,b'Long text over five characters'))
    process(db,settings,storage)
    assert db.get(Document,document.id).processing_status == 'failed'
    assert db.get(Document,document.id).processing_error == 'Document exceeds parser resource limits'


def test_invalid_uuid_and_missing_documents(doc_client,workspace):
    assert doc_client.get(base(workspace)+'/invalid').status_code == 422
    assert doc_client.get(f'/api/v1/workspaces/invalid/documents/').status_code == 422
    assert doc_client.get(base(workspace)+f'/{uuid.uuid4()}').status_code == 404


def test_worker_tick_runs_cleanup_and_processing(doc_client,db,workspace,settings,storage):
    document = stored_document(db,upload(doc_client,workspace))
    assert document_jobs.run_once(db,settings,storage)
    assert db.get(Document,document.id).processing_status == 'completed'
    assert not document_jobs.run_once(db,settings,storage)


def test_chunk_determinism_overlap_order_offsets_and_small_inputs():
    doc,ws = uuid.uuid4(),uuid.uuid4()
    text = '0123456789abcdef'*40
    sources = [{'text':text,'page_number':2,'markdown':False}]
    first = chunk_sources(sources,doc,ws,size=64,overlap=16)
    assert first == chunk_sources(sources,doc,ws,size=64,overlap=16)
    assert [c.chunk_index for c in first] == list(range(len(first)))
    for chunk in first:
        assert chunk.text == text[chunk.char_start:chunk.char_end]
        assert chunk.document_id == doc and chunk.workspace_id == ws and chunk.page_number == 2
    for left,right in zip(first,first[1:]):
        assert left.text[-16:] == right.text[:16]
    small = chunk_sources([{'text':'tiny','page_number':None}],doc,ws)
    assert len(small) == 1 and small[0].text == 'tiny'
    assert chunk_sources([{'text':' \n ','page_number':None}],doc,ws) == []
    with pytest.raises(ValueError): chunk_sources(sources,doc,ws,size=10,overlap=10)
    with pytest.raises(ValueError): chunk_sources(sources,doc,ws,size=64,overlap=16,max_chunks=1)


def test_chunk_composite_foreign_key_blocks_wrong_workspace(doc_client,db,people,workspace):
    document = stored_document(db,upload(doc_client,workspace))
    other = create_workspace(db,identity(people,'owner'),WorkspaceCreate(name='Other'))
    db.add(DocumentChunk(document_id=document.id,workspace_id=other.id,chunk_index=0,text='wrong workspace',
                          source_ref='invalid',char_start=0,char_end=15))
    with pytest.raises(IntegrityError): db.commit()
    db.rollback()


def test_chunked_upload_body_limit_without_content_length(doc_client,workspace,settings,storage):
    settings.document_upload_max_bytes = 32
    def body():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="x.txt"\r\n\r\n'
        yield b'x'*70000
        yield b'\r\n--boundary--\r\n'
    response = doc_client.post(base(workspace)+'/',content=body(),headers={'Content-Type':'multipart/form-data; boundary=boundary'})
    assert response.status_code == 413
    assert list(storage.root.iterdir()) == []


def test_one_file_only(doc_client,workspace,storage):
    response = doc_client.post(base(workspace)+'/',files=[('file',('a.txt',b'a','text/plain')),('file',('b.txt',b'b','text/plain'))])
    assert response.status_code == 400
    assert list(storage.root.iterdir()) == []
    assert doc_client.post(base(workspace)+'/',data={'extra':'field'}).status_code in {400,422}


def test_retry_pending_and_running_is_rejected(doc_client,db,workspace,settings):
    document = stored_document(db,upload(doc_client,workspace))
    assert doc_client.post(base(workspace)+f'/{document.id}/retry').status_code == 409
    assert document_jobs.claim_job(db,settings)
    assert doc_client.post(base(workspace)+f'/{document.id}/retry').status_code == 409


def test_failed_partial_cleanup_intent_survives_request(doc_client,db,workspace,storage,monkeypatch):
    original = storage.delete
    def unavailable(*_): raise StorageError('private')
    monkeypatch.setattr(storage,'delete',unavailable)
    assert upload(doc_client,workspace,b'bad content','bad.pdf','application/pdf').status_code == 422
    intent = db.scalar(select(StorageCleanup))
    assert intent is not None and list(storage.root.iterdir())
    intent.available_at = db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(storage,'delete',original)
    assert document_jobs.cleanup_one(db,storage)
    assert list(storage.root.iterdir()) == []


def test_parser_timeout_kills_real_child(settings,tmp_path,monkeypatch):
    from app.services import document_parsing
    import subprocess
    settings.document_processing_timeout = 1
    original = subprocess.Popen
    processes = []
    def slow_child(command,**kwargs):
        child = original([command[0],'-I','-c','import time; time.sleep(10)'],**kwargs)
        processes.append(child)
        return child
    monkeypatch.setattr(document_parsing.subprocess,'Popen',slow_child)
    with (tmp_path/'input').open('w+b') as stream:
        stream.write(b'test');stream.seek(0)
        with pytest.raises(ParsingError,match='timed out'):
            run_parser(stream,'.txt',settings)
    assert len(processes) == 1 and processes[0].poll() is not None


def test_parser_memory_supervision_kills_child(settings,tmp_path,monkeypatch):
    from app.services import document_parsing
    import subprocess
    from types import SimpleNamespace
    original = subprocess.Popen
    processes = []
    def slow_child(command,**kwargs):
        child = original([command[0],'-I','-c','import time; time.sleep(10)'],**kwargs)
        processes.append(child)
        return child
    monkeypatch.setattr(document_parsing.subprocess,'Popen',slow_child)
    monkeypatch.setattr(document_parsing.psutil.Process,'memory_info',lambda _:SimpleNamespace(rss=3*1024**3))
    with (tmp_path/'input').open('w+b') as stream:
        stream.write(b'test');stream.seek(0)
        with pytest.raises(ParsingError,match='resource limits'):
            run_parser(stream,'.txt',settings)
    assert len(processes) == 1 and processes[0].poll() is not None


def test_worker_finalization_failure_rolls_back_partial_chunks(doc_client,db,workspace,settings,storage):
    document = stored_document(db,upload(doc_client,workspace))
    document_id = document.id
    claim = document_jobs.claim_job(db,settings)
    # after_flush sees new chunks before they join the identity map; use an unconditional
    # one-shot failure only during finalization, after the durable claim has committed.
    def fail_flush(session,context): raise RuntimeError('Injected chunk commit failure')
    event.listen(db,'after_flush',fail_flush)
    try:
        with pytest.raises(RuntimeError,match='Injected chunk commit failure'):
            document_jobs.process_claim(db,claim,settings,storage)
    finally:
        event.remove(db,'after_flush',fail_flush)
        db.rollback()
    assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
    assert db.get(Document,document_id).processing_status == 'processing'
    job = db.get(DocumentJob,document_id)
    job.lease_expires_at = db.scalar(select(func.clock_timestamp()))-timedelta(seconds=1)
    db.commit()
    process(db,settings,storage)
    assert db.get(Document,document_id).processing_status == 'completed'
    assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 1


def test_deletion_database_failure_keeps_original_and_metadata(doc_client,db,workspace,storage):
    document = stored_document(db,upload(doc_client,workspace))
    document_id,key = document.id,document.storage_key
    def fail_cleanup_intent(session,context,instances):
        if any(isinstance(obj,StorageCleanup) for obj in session.new):
            raise IntegrityError('private',{},RuntimeError('private'))
    event.listen(db,'before_flush',fail_cleanup_intent)
    try:
        response = doc_client.delete(base(workspace)+f'/{document_id}')
    finally:
        event.remove(db,'before_flush',fail_cleanup_intent)
    assert response.status_code == 409
    assert db.get(Document,document_id) is not None and db.get(DocumentJob,document_id) is not None
    assert (storage.root/key).exists()
    assert doc_client.get(base(workspace)+f'/{document_id}/download').status_code == 200


@pytest.mark.parametrize('options', [
    {'document_chunk_size':100,'document_chunk_overlap':100},
    {'document_upload_max_bytes':0}, {'document_job_lease_seconds':30},
    {'document_storage_root':'relative/path'},
    {'document_storage_root':str(Path(__file__).parents[2]/'web'/'public')},
])
def test_unsafe_document_settings_rejected(options):
    from pydantic import ValidationError
    with pytest.raises(ValidationError): Settings(**options)


def test_legacy_processing_errors_are_redacted_without_rewriting_records(doc_client,db,workspace):
    document = stored_document(db,upload(doc_client,workspace))
    private = 'Internal exception with private filesystem and document contents'
    document.processing_error = private
    db.commit()
    response = doc_client.get(base(workspace)+f'/{document.id}')
    assert response.status_code == 200 and private not in response.text
    assert response.json()['processing_error'] == 'Document processing failed'
    assert private not in doc_client.get(base(workspace)+'/').text
    db.refresh(document)
    assert document.processing_error == private


def test_unavailable_storage_dependency_returns_safe_503(monkeypatch):
    from fastapi import HTTPException
    from app.services import document_storage
    def broken_root(*args,**kwargs): raise StorageError('private storage detail')
    monkeypatch.setattr(document_storage,'LocalDocumentStorage',broken_root)
    with pytest.raises(HTTPException) as error:
        document_storage.get_document_storage()
    assert error.value.status_code == 503
    assert error.value.detail == 'Document storage unavailable'
