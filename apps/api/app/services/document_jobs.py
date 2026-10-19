"""Durable PostgreSQL queue, expiring leases and fenced/idempotent publication."""
from dataclasses import asdict, dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Document, DocumentChunk, DocumentJob, StorageCleanup
from app.services.document_chunking import chunk_sources
from app.services.document_parsing import ParsingError, run_parser
from app.services.document_storage import DocumentStorage, StorageError


@dataclass(frozen=True)
class Claim:
    document_id: UUID
    workspace_id: UUID
    storage_key: str
    extension: str
    checksum: str
    lease_id: UUID


def eligible(job, now):
    return ((job.state == 'queued' and job.available_at <= now)
            or (job.state == 'running' and job.lease_expires_at is not None and job.lease_expires_at <= now))


def claim_job(db: Session, settings: Settings):
    now = db.scalar(select(func.clock_timestamp()))
    # Lock Document BEFORE Job everywhere, matching HTTP retry/delete lock order.
    document = db.scalar(select(Document).join(DocumentJob).where(or_(
        and_(DocumentJob.state == 'queued', DocumentJob.available_at <= now),
        and_(DocumentJob.state == 'running', DocumentJob.lease_expires_at <= now)))
        .order_by(DocumentJob.available_at,Document.id).with_for_update(of=Document,skip_locked=True)
        .limit(1).execution_options(populate_existing=True))
    if document is None:
        db.rollback()
        return None
    job = db.scalar(select(DocumentJob).where(DocumentJob.document_id == document.id)
                    .with_for_update().execution_options(populate_existing=True))
    if job is None or not eligible(job,now):
        db.rollback()
        return None
    if document.processing_attempts >= settings.document_max_attempts:
        document.processing_status, document.processing_error = 'failed', 'Processing attempt limit reached'
        job.state, job.lease_id, job.lease_expires_at = 'failed', None, None
        db.commit()
        return None
    from pathlib import Path
    lease = uuid4()
    job.state, job.lease_id = 'running', lease
    job.lease_expires_at = now + timedelta(seconds=settings.document_job_lease_seconds)
    document.processing_status, document.processing_error = 'processing', None
    document.processing_attempts += 1
    document.last_processed_at = now
    claim = Claim(document.id,document.workspace_id,document.storage_key,
                  Path(document.original_filename).suffix.lower(),document.checksum_sha256,lease)
    db.commit()
    return claim


def finish_job(db, claim: Claim, settings, *, chunks=None, error=None, transient=False):
    document = db.scalar(select(Document).where(Document.id == claim.document_id,
        Document.workspace_id == claim.workspace_id).with_for_update().execution_options(populate_existing=True))
    if document is None:
        db.rollback()
        return False  # Deleted while parsing: never recreate metadata/chunks.
    job = db.scalar(select(DocumentJob).where(DocumentJob.document_id == claim.document_id)
                    .with_for_update().execution_options(populate_existing=True))
    now = db.scalar(select(func.clock_timestamp()))
    if not job or job.state != 'running' or job.lease_id != claim.lease_id or job.lease_expires_at <= now:
        db.rollback()
        return False  # Expired/replaced lease cannot publish stale results.
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id,
                                           DocumentChunk.workspace_id == document.workspace_id))
    if error is None:
        db.add_all([DocumentChunk(**asdict(chunk)) for chunk in chunks])
        document.processing_status, document.processing_error = 'completed', None
        job.state = 'done'
    else:
        document.processing_error = error
        if transient and document.processing_attempts < settings.document_max_attempts:
            document.processing_status, job.state = 'pending', 'queued'
            job.available_at = now + timedelta(seconds=min(300, 2**document.processing_attempts))
        else:
            document.processing_status, job.state = 'failed', 'failed'
    job.lease_id, job.lease_expires_at = None, None
    db.commit()
    return True


def process_claim(db: Session, claim: Claim, settings: Settings, storage: DocumentStorage):
    import hashlib
    try:
        with storage.open(claim.storage_key) as stream:
            import os
            if os.fstat(stream.fileno()).st_size > settings.document_upload_max_bytes:
                raise ParsingError('limits')
            checksum = hashlib.file_digest(stream,'sha256').hexdigest()
            if checksum != claim.checksum:
                return finish_job(db,claim,settings,error='Original checksum mismatch')
            stream.seek(0)
            sources = run_parser(stream,claim.extension,settings)
        chunks = chunk_sources(sources,claim.document_id,claim.workspace_id,size=settings.document_chunk_size,
            overlap=settings.document_chunk_overlap,max_chunks=settings.document_max_chunks)
        if not chunks:
            raise ParsingError('empty')
    except StorageError:
        return finish_job(db,claim,settings,error='Original storage unavailable',transient=True)
    except ParsingError as error:
        return finish_job(db,claim,settings,error=str(error))
    except ValueError:
        return finish_job(db,claim,settings,error='Document exceeds chunk limits')
    except Exception:
        return finish_job(db,claim,settings,error='Document processing failed',transient=True)
    return finish_job(db,claim,settings,chunks=chunks)


def cleanup_one(db: Session, storage: DocumentStorage):
    now = db.scalar(select(func.clock_timestamp()))
    intent = db.scalar(select(StorageCleanup).where(StorageCleanup.available_at <= now)
                       .order_by(StorageCleanup.available_at).with_for_update(skip_locked=True).limit(1))
    if intent is None:
        db.rollback()
        return False
    # Also guards an ambiguous upload commit or a mistakenly retained reservation.
    live = db.scalar(select(Document.id).where(Document.storage_key == intent.storage_key).limit(1))
    if live is not None:
        db.delete(intent)
    else:
        try:
            storage.delete(intent.storage_key)
            db.delete(intent)
        except StorageError:
            intent.attempts += 1
            intent.last_error = 'Storage cleanup unavailable'
            intent.available_at = now + timedelta(seconds=min(3600,2**min(intent.attempts,12)))
    db.commit()
    return True


def run_once(db, settings, storage):
    cleaned = cleanup_one(db,storage)
    claim = claim_job(db,settings)
    if claim is not None:
        process_claim(db,claim,settings,storage)
    return cleaned or claim is not None
