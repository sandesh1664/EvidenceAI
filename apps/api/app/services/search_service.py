from app.core.telemetry import measured
from fastapi import HTTPException
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import and_, case, cast, select

from app.core.authorization import document_workspace_access
from app.models import Document, DocumentChunk, WorkspaceMember, ChunkEmbedding
from app.services.embedding_providers import EmbeddingEngine, EmbeddingError, profile_for
from app.services.embedding_jobs import enabled


def validate_filters(db,workspace_id,ids):
    if ids is None:
        return
    found = set(db.scalars(select(Document.id).where(Document.workspace_id == workspace_id,Document.id.in_(ids))).all())
    if found != set(ids):
        raise HTTPException(404,'Document filter not found')


@measured("retrieval")
def search(db,workspace_id,actor_id,data,settings,engine=None):
    document_workspace_access(db,workspace_id,actor_id)
    enabled(settings)
    validate_filters(db,workspace_id,data.document_ids)
    if data.document_ids == []:
        return []  # An explicit empty selection intentionally requests no evidence.
    if settings.embedding_provider == 'gemini':
        from app.services.gemini_configuration import blocker, MESSAGES
        blocked = blocker(settings, 'embedding')
        if blocked:
            from app.services.provider_errors import EMBEDDING_ERRORS
            code, message = EMBEDDING_ERRORS[MESSAGES[blocked]]
            raise HTTPException(503, {'code': code, 'message': message})
    profile = profile_for(settings)
    base = (select(ChunkEmbedding).join(DocumentChunk).join(Document,Document.id == DocumentChunk.document_id)
        .where(Document.workspace_id == workspace_id,DocumentChunk.workspace_id == workspace_id,
               Document.processing_status == 'completed',ChunkEmbedding.profile_id == profile.id,
               ChunkEmbedding.dimensions == profile.dimensions,ChunkEmbedding.status == 'completed'))
    if data.document_ids is not None:
        base = base.where(Document.id.in_(data.document_ids))
    if db.scalar(base.with_only_columns(ChunkEmbedding.chunk_id).limit(1)) is None:
        return []
    db.rollback()  # Do not hold a transaction during a hosted query embedding request.
    try:
        engine = engine or EmbeddingEngine(settings)
        if engine.profile.id != profile.id:
            raise EmbeddingError('Embedding model identity mismatch')
        vector = (engine.embed_query(data.query) if settings.embedding_provider == 'gemini'
                  else engine.embed([data.query])[0])
    except EmbeddingError as error:
        from app.services.provider_errors import EMBEDDING_ERRORS
        if str(error) in EMBEDDING_ERRORS:
            code, message = EMBEDDING_ERRORS[str(error)]
            raise HTTPException(503, {'code': code, 'message': message}) from None
        raise HTTPException(503,'Semantic search temporarily unavailable') from None
    # Reauthorize AFTER remote I/O. Query also joins the actor's current membership.
    document_workspace_access(db,workspace_id,actor_id)
    validate_filters(db,workspace_id,data.document_ids)
    compatible = and_(ChunkEmbedding.profile_id == profile.id,ChunkEmbedding.dimensions == profile.dimensions,
                      ChunkEmbedding.status == 'completed')
    # CASE prevents distance evaluation on incompatible dimensions, even if the planner
    # rearranges predicates across joins. Exact search deliberately uses no ANN index.
    vector_column = cast(case((compatible,ChunkEmbedding.vector),else_=None),VECTOR(profile.dimensions))
    distance = vector_column.cosine_distance(vector)
    statement = (select(DocumentChunk,Document.original_filename,distance.label('distance'))
        .join(Document,Document.id == DocumentChunk.document_id)
        .join(ChunkEmbedding,ChunkEmbedding.chunk_id == DocumentChunk.id)
        .join(WorkspaceMember,and_(WorkspaceMember.workspace_id == DocumentChunk.workspace_id,
                                  WorkspaceMember.user_id == actor_id))
        .where(DocumentChunk.workspace_id == workspace_id,Document.workspace_id == workspace_id,
               Document.processing_status == 'completed',compatible,distance <= 1-settings.search_min_similarity)
        .order_by(distance,Document.id,DocumentChunk.chunk_index,DocumentChunk.id).limit(data.limit).offset(data.offset))
    if data.document_ids is not None:
        statement = statement.where(Document.id.in_(data.document_ids))
    return [dict(chunk_id=chunk.id,document_id=chunk.document_id,filename=filename,excerpt=chunk.text[:1000],
                 page_number=chunk.page_number,section=chunk.section,source_ref=chunk.source_ref,
                 similarity=max(-1.0,min(1.0,1-float(value))),embedding_model=profile.identifier)
            for chunk,filename,value in db.execute(statement)]
