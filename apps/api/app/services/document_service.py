from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session

from app.core.authorization import document_access, document_workspace_access
from app.core.config import Settings
from app.models import Document, DocumentChunk, DocumentJob, StorageCleanup
from app.services.document_parsing import MIME_TYPES, ParsingError, validate_filename, validate_upload
from app.services.document_storage import DocumentStorage, LocalDocumentStorage, StorageError, UploadTooLarge
from app.services.workspace_transaction import workspace_transaction


def authorize_upload(db, workspace_id, actor_id):
    try:
        document_workspace_access(db, workspace_id, actor_id, write=True)
    finally:
        # No workspace locks/transaction are held during upload I/O or validation.
        db.rollback()


def upload_document(db: Session, workspace_id: UUID, actor_id: UUID, file, settings: Settings, storage: DocumentStorage):
    authorize_upload(db, workspace_id, actor_id)
    try:
        extension = validate_filename(file.filename)
    except ValueError as error:
        raise HTTPException(415 if str(error) == 'Unsupported file format' else 422, str(error)) from None
    key = LocalDocumentStorage.new_key()
    # Durable orphan-recovery intent precedes any file creation. It is removed in
    # the SAME transaction that publishes metadata and the processing job.
    reservation = StorageCleanup(storage_key=key,
        available_at=db.scalar(select(func.clock_timestamp())) + timedelta(hours=1))
    db.add(reservation)
    db.commit()
    try:
        uploaded = storage.stage(key, file.file, settings.document_upload_max_bytes)
        if uploaded.size == 0:
            raise HTTPException(422, 'Empty upload')
        validate_upload(storage, key, extension, file.content_type, settings)
        storage.promote(key)
        with workspace_transaction(db):
            document_workspace_access(db, workspace_id, actor_id, write=True, lock=True)
            intent = db.scalar(select(StorageCleanup).where(StorageCleanup.storage_key == key)
                               .with_for_update().execution_options(populate_existing=True))
            if intent is None:
                raise HTTPException(503, 'Upload expired; upload again')
            with storage.open(key):
                pass  # Verify publication while holding the cleanup reservation lock.
            if db.scalar(select(Document.id).where(Document.workspace_id == workspace_id,
                                                  Document.checksum_sha256 == uploaded.checksum)):
                raise HTTPException(409, 'Document content already exists in this workspace')
            document = Document(workspace_id=workspace_id, uploaded_by=actor_id, original_filename=file.filename,
                mime_type=MIME_TYPES[extension], file_size=uploaded.size, checksum_sha256=uploaded.checksum,
                storage_key=key, processing_status='pending')
            db.add(document)
            db.flush()
            db.add(DocumentJob(document_id=document.id))
            db.delete(intent)
            db.flush()
        from app.core.telemetry import emit
        emit('document_enqueued', workspace_id=workspace_id, job_id=document.id)
        return document
    except BaseException as error:
        db.rollback()
        # A commit error can be ambiguous. Never unlink a live document's original.
        # If the DB/storage is unavailable, leave the durable intent for the worker.
        try:
            intent = db.scalar(select(StorageCleanup).where(StorageCleanup.storage_key == key).with_for_update())
            live = db.scalar(select(Document.id).where(Document.storage_key == key).limit(1))
            if intent is not None and live is None:
                storage.delete(key)
                db.delete(intent)
            db.commit()
        except Exception:
            db.rollback()
        if isinstance(error, UploadTooLarge):
            raise HTTPException(413, 'File exceeds upload byte limit') from None
        if isinstance(error, ParsingError):
            raise HTTPException(422, str(error)) from None
        if isinstance(error, StorageError):
            raise HTTPException(503, 'Document storage unavailable') from None
        raise


def list_documents(db, workspace_id, actor_id, limit, offset):
    document_workspace_access(db, workspace_id, actor_id)
    return db.scalars(select(Document).where(Document.workspace_id == workspace_id)
                      .order_by(Document.created_at,Document.id).limit(limit).offset(offset)).all()


def read_document(db, workspace_id, document_id, actor_id):
    return document_access(db, workspace_id, document_id, actor_id)


def open_download(db, workspace_id, document_id, actor_id, storage):
    document = document_access(db, workspace_id, document_id, actor_id)
    try:
        stream = storage.open(document.storage_key)
    except StorageError:
        raise HTTPException(503, 'Document original unavailable') from None
    return document, stream


def retry_document(db, workspace_id, document_id, actor_id, settings):
    with workspace_transaction(db):
        document = document_access(db, workspace_id, document_id, actor_id, write=True)
        if document.processing_status != 'failed' or document.processing_attempts >= settings.document_max_attempts:
            raise HTTPException(409, 'Document is not eligible for retry')
        job = db.scalar(select(DocumentJob).where(DocumentJob.document_id == document_id).with_for_update())
        if job is None:
            # Legacy documents are never automatically enqueued by a schema migration.
            job = DocumentJob(document_id=document_id)
            db.add(job)
        job.state, job.lease_id, job.lease_expires_at = 'queued', None, None
        job.available_at = db.scalar(select(func.clock_timestamp()))
        document.processing_status, document.processing_error = 'pending', None
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id,
                                               DocumentChunk.workspace_id == workspace_id))
        db.flush()
    return document


def delete_document(db, workspace_id, document_id, actor_id):
    with workspace_transaction(db):
        document = document_access(db, workspace_id, document_id, actor_id, write=True)
        try:
            LocalDocumentStorage.validate_key(document.storage_key)
        except StorageError:
            raise HTTPException(409, 'Legacy storage requires explicit operator cleanup') from None
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id,
                                               DocumentChunk.workspace_id == workspace_id))
        db.execute(delete(DocumentJob).where(DocumentJob.document_id == document_id))
        db.add(StorageCleanup(storage_key=document.storage_key,
                              available_at=db.scalar(select(func.clock_timestamp()))))
        db.delete(document)
        db.flush()
