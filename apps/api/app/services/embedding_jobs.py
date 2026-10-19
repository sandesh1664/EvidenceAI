"""Embedding jobs reuse document-first locks, expiring leases and generation fences."""
from dataclasses import asdict, dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.authorization import document_access
from app.models import Document, DocumentChunk, EmbeddingProfile, ChunkEmbedding, EmbeddingJob
from app.services.embedding_providers import EmbeddingEngine, EmbeddingError, profile_for
from app.services.workspace_transaction import workspace_transaction

SAFE_ERRORS = {
    'Embedding provider unavailable','Embedding provider temporarily unavailable','Embedding provider timed out',
    'Embedding provider rejected the request','Invalid embedding provider output','Embedding model identity mismatch',
    'Invalid embedding vector dimensions','Embedding vectors must contain finite numbers','Embedding vectors must be nonzero',
    'Embedding input exceeds limits or is empty','Embedding provider failed','Embedding attempt limit reached',
}


def safe_error(error):
    value = str(error)
    return value if value in SAFE_ERRORS else 'Embedding provider failed'


def enabled(settings):
    if settings.embedding_provider == 'disabled':
        raise HTTPException(503,'Embeddings are disabled')


def ensure_profile(db,settings):
    profile = profile_for(settings)
    values = asdict(profile)
    db.execute(insert(EmbeddingProfile).values(**values).on_conflict_do_nothing(index_elements=['id']))
    saved = db.get(EmbeddingProfile,profile.id,populate_existing=True)
    if any(getattr(saved,key) != value for key,value in values.items()):
        raise RuntimeError('Embedding profile identity conflict')
    return profile


def enqueue(db: Session,document: Document,settings,*,force=False):
    """Caller owns Document lock and transaction; never commit separately here."""
    enabled(settings)
    if document.processing_status != 'completed':
        raise HTTPException(409,'Document must finish extraction before indexing')
    profile = ensure_profile(db,settings)
    job = db.get(EmbeddingJob,(document.id,profile.id),populate_existing=True,with_for_update=True)
    now = db.scalar(select(func.clock_timestamp()))
    if job is not None:
        if job.state in {'queued','running'}:
            if force:
                raise HTTPException(409,'Indexing is already queued or running')
            return job
        if not force:
            return job  # done is idempotent; failed requires explicit retry/force.
    generation = uuid4()
    if job is None:
        job = EmbeddingJob(document_id=document.id,profile_id=profile.id,generation=generation)
        db.add(job)
    else:
        job.generation = generation
    job.state,job.attempts,job.error = 'queued',0,None
    job.lease_id,job.lease_expires_at,job.last_attempt_at = None,None,None
    job.available_at = now
    ids = db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == document.id,
                                                   DocumentChunk.workspace_id == document.workspace_id)).all()
    if not ids:
        raise HTTPException(409,'Document has no chunks to index')
    # Preserve already usable vectors, including during a forced same-profile rebuild.
    for start in range(0,len(ids),500):
        rows = [dict(chunk_id=chunk_id,profile_id=profile.id,dimensions=profile.dimensions,
                     generation=generation,status='pending') for chunk_id in ids[start:start+500]]
        db.execute(insert(ChunkEmbedding).values(rows).on_conflict_do_nothing(index_elements=['chunk_id','profile_id']))
    db.flush()
    return job


def status(db,workspace_id,document_id,actor_id,settings):
    enabled(settings)
    document_access(db,workspace_id,document_id,actor_id)
    return status_for(db,document_id,settings)


def status_for(db,document_id,settings):
    profile = profile_for(settings)
    job = db.get(EmbeddingJob,(document_id,profile.id),populate_existing=True)
    total = db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == document_id))
    counts = select(func.count()).select_from(ChunkEmbedding).join(DocumentChunk).where(
        DocumentChunk.document_id == document_id,ChunkEmbedding.profile_id == profile.id,
        ChunkEmbedding.dimensions == profile.dimensions,ChunkEmbedding.status == 'completed')
    indexed = db.scalar(counts)
    current = db.scalar(counts.where(ChunkEmbedding.generation == job.generation)) if job else 0
    return dict(document_id=document_id,embedding_model=profile.identifier,dimensions=profile.dimensions,
                state=job.state if job else 'not_indexed',generation=job.generation if job else None,
                attempts=job.attempts if job else 0,total_chunks=total,indexed_chunks=indexed,
                current_generation_chunks=current,error=safe_error(job.error) if job and job.error else None,
                last_attempt_at=job.last_attempt_at if job else None)


def request_index(db,workspace_id,document_id,actor_id,settings,*,force=False,retry=False):
    enabled(settings)
    with workspace_transaction(db):
        document = document_access(db,workspace_id,document_id,actor_id,write=True)
        if retry:
            profile = profile_for(settings)
            job = db.get(EmbeddingJob,(document_id,profile.id),populate_existing=True,with_for_update=True)
            if (document.processing_status != 'completed' or job is None or job.state != 'failed'
                    or job.attempts >= settings.embedding_job_max_attempts):
                raise HTTPException(409,'Indexing is not eligible for retry')
            job.state,job.error,job.lease_id,job.lease_expires_at = 'queued',None,None,None
            job.available_at = db.scalar(select(func.clock_timestamp()))
        else:
            enqueue(db,document,settings,force=force)
        db.flush()
    return status_for(db,document_id,settings)


@dataclass(frozen=True)
class EmbeddingClaim:
    document_id: UUID
    workspace_id: UUID
    profile_id: str
    generation: UUID
    lease_id: UUID


def claim_job(db,settings):
    if settings.embedding_provider == 'disabled':
        return None
    profile = profile_for(settings)
    now = db.scalar(select(func.clock_timestamp()))
    document = db.scalar(select(Document).join(EmbeddingJob).where(
        Document.processing_status == 'completed',EmbeddingJob.profile_id == profile.id,
        or_(and_(EmbeddingJob.state == 'queued',EmbeddingJob.available_at <= now),
            and_(EmbeddingJob.state == 'running',EmbeddingJob.lease_expires_at <= now)))
        .order_by(EmbeddingJob.available_at,Document.id).with_for_update(of=Document,skip_locked=True)
        .limit(1).execution_options(populate_existing=True))
    if document is None:
        db.rollback()
        return None
    job = db.get(EmbeddingJob,(document.id,profile.id),populate_existing=True,with_for_update=True)
    if not job or not (job.state == 'queued' and job.available_at <= now or
                       job.state == 'running' and job.lease_expires_at and job.lease_expires_at <= now):
        db.rollback()
        return None
    if job.attempts >= settings.embedding_job_max_attempts:
        job.state,job.error,job.lease_id,job.lease_expires_at = 'failed','Embedding attempt limit reached',None,None
        db.commit()
        return None
    lease_id = uuid4()
    job.state,job.lease_id = 'running',lease_id
    job.lease_expires_at = now+timedelta(seconds=settings.embedding_job_lease_seconds)
    job.attempts += 1
    job.last_attempt_at,job.error = now,None
    claim = EmbeddingClaim(document.id,document.workspace_id,profile.id,job.generation,lease_id)
    db.commit()
    return claim


def locked_job(db,claim):
    document = db.scalar(select(Document).where(Document.id == claim.document_id,
        Document.workspace_id == claim.workspace_id).with_for_update().execution_options(populate_existing=True))
    if document is None or document.processing_status != 'completed':
        return None
    job = db.get(EmbeddingJob,(claim.document_id,claim.profile_id),populate_existing=True,with_for_update=True)
    now = db.scalar(select(func.clock_timestamp()))
    if (not job or job.state != 'running' or job.generation != claim.generation or job.lease_id != claim.lease_id
            or job.lease_expires_at is None or job.lease_expires_at <= now):
        return None
    return job


def process_claim(db,claim,settings,engine=None):
    if profile_for(settings).id != claim.profile_id:
        return False
    try:
        engine = engine or EmbeddingEngine(settings)
    except EmbeddingError:
        return fail_claim(db,claim,settings,EmbeddingError('Embedding provider unavailable'))
    if engine.profile.id != claim.profile_id:
        return fail_claim(db,claim,settings,EmbeddingError('Embedding model identity mismatch'))
    while True:
        job = locked_job(db,claim)
        if job is None:
            db.rollback()
            return False
        rows = db.execute(select(DocumentChunk.id,DocumentChunk.text).join(ChunkEmbedding).where(
            DocumentChunk.document_id == claim.document_id,DocumentChunk.workspace_id == claim.workspace_id,
            ChunkEmbedding.profile_id == claim.profile_id,
            or_(ChunkEmbedding.status != 'completed',ChunkEmbedding.generation != claim.generation))
            .order_by(DocumentChunk.chunk_index,DocumentChunk.id).limit(settings.embedding_batch_size)).all()
        if not rows:
            job.state,job.error,job.lease_id,job.lease_expires_at = 'done',None,None,None
            db.commit()
            return True
        job.lease_expires_at = db.scalar(select(func.clock_timestamp()))+timedelta(seconds=settings.embedding_job_lease_seconds)
        db.commit()  # No DB transaction or row locks span a hosted provider request.
        try:
            vectors = engine.embed([row.text for row in rows])
        except EmbeddingError as error:
            return fail_claim(db,claim,settings,error,chunk_ids=[row.id for row in rows])
        job = locked_job(db,claim)
        if job is None:
            db.rollback()
            return False
        now = db.scalar(select(func.clock_timestamp()))
        for row,vector in zip(rows,vectors,strict=True):
            embedding = db.get(ChunkEmbedding,(row.id,claim.profile_id),populate_existing=True)
            if embedding is None:
                db.rollback()
                return False
            embedding.vector,embedding.status,embedding.generation = vector,'completed',claim.generation
            embedding.generated_at,embedding.error = now,None
        job.lease_expires_at = now+timedelta(seconds=settings.embedding_job_lease_seconds)
        db.commit()  # Each validated batch persists independently and idempotently.


def fail_claim(db,claim,settings,error,*,chunk_ids=()):
    job = locked_job(db,claim)
    if job is None:
        db.rollback()
        return False
    message = safe_error(error)
    job.error = message
    if error.transient and job.attempts < settings.embedding_job_max_attempts:
        job.state = 'queued'
        job.available_at = db.scalar(select(func.clock_timestamp()))+timedelta(seconds=min(300,2**job.attempts))
    else:
        job.state = 'failed'
    job.lease_id,job.lease_expires_at = None,None
    for chunk_id in chunk_ids:
        embedding = db.get(ChunkEmbedding,(chunk_id,claim.profile_id),populate_existing=True)
        if embedding is not None:
            embedding.error = message
            if embedding.status != 'completed':
                embedding.status = 'failed'
    db.commit()
    return True


def run_once(db,settings):
    claim = claim_job(db,settings)
    if claim is None:
        return False
    process_claim(db,claim,settings)
    return True
