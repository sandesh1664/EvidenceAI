"""Configuration and active-profile readiness, without provider probes or secret output."""
from sqlalchemy import and_, case, func, select

from app.core.authorization import document_workspace_access
from app.models import Document, DocumentChunk, ChunkEmbedding, EmbeddingJob
from app.services.embedding_providers import profile_for


def provider_status(settings, kind):
    provider = getattr(settings, kind + '_provider')
    model = getattr(settings, kind + '_model')
    reason = None
    if provider == 'disabled':
        reason = 'provider_disabled'
    elif provider == 'gemini':
        from app.services.gemini_configuration import blocker
        reason = blocker(settings, kind)
    elif provider == 'openai' and (not getattr(settings, kind + '_hosted_allowed')
                                   or not settings.openai_api_key):
        reason = 'external_requests_not_authorized'
    return {'provider': provider, 'model': model, 'configured': reason is None,
            'offline': provider in {'fake', 'mock'}, 'blocker': reason,
            'live_access': 'NOT VERIFIED' if provider in {'gemini', 'openai'} else 'NOT APPLICABLE'}


def readiness(settings, total, indexed, complete):
    if not total:
        return False, 'no_extracted_chunks'
    if not complete or indexed != total:
        return False, 'active_profile_not_indexed'
    for kind in ('embedding', 'llm'):
        state = provider_status(settings, kind)
        if not state['configured']:
            return False, state['blocker']
    return True, None


def workspace_status(db, workspace_id, actor_id, settings):
    document_workspace_access(db, workspace_id, actor_id)
    profile = profile_for(settings)
    counts = (select(DocumentChunk.document_id.label('document_id'),
            func.count().label('total'),
            func.count(ChunkEmbedding.chunk_id).label('indexed'))
        .outerjoin(EmbeddingJob, and_(EmbeddingJob.document_id == DocumentChunk.document_id,
                                      EmbeddingJob.profile_id == profile.id))
        .outerjoin(ChunkEmbedding, and_(ChunkEmbedding.chunk_id == DocumentChunk.id,
            ChunkEmbedding.profile_id == profile.id, ChunkEmbedding.dimensions == profile.dimensions,
            ChunkEmbedding.status == 'completed', ChunkEmbedding.generation == EmbeddingJob.generation))
        .where(DocumentChunk.workspace_id == workspace_id)
        .group_by(DocumentChunk.document_id).subquery())
    indexed = and_(Document.processing_status == 'completed', counts.c.total > 0,
                   counts.c.total == counts.c.indexed, EmbeddingJob.state == 'done')
    aggregate = db.execute(select(func.count(Document.id),
        func.count(case((Document.processing_status == 'completed', 1))),
        func.count(case((indexed, 1))))
        .outerjoin(counts, counts.c.document_id == Document.id)
        .outerjoin(EmbeddingJob, and_(EmbeddingJob.document_id == Document.id,
                                      EmbeddingJob.profile_id == profile.id))
        .where(Document.workspace_id == workspace_id)).one()
    providers = {kind: provider_status(settings, kind) for kind in ('embedding', 'llm')}
    enabled = all(value['configured'] for value in providers.values())
    return {'embedding_profile': profile.identifier, 'providers': providers,
            'documents': aggregate[0], 'processing_complete': aggregate[1],
            'indexing_complete': aggregate[2],
            'ready_for_research': aggregate[2] if enabled else 0,
            'readiness_scope': 'Configuration and database state; provider availability and answer quality are not probed'}
