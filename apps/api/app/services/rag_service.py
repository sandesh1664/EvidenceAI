"""Stateless authorized retrieval -> bounded generation -> validated source claims."""

import logging
import threading
import time
from dataclasses import dataclass, replace
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.exc import DBAPIError

from app.core.authorization import document_workspace_access
from app.models import ChunkEmbedding, Document, DocumentChunk, User, WorkspaceMember
from app.schemas.ask import AskResponse
from app.schemas.search import SearchRequest
from app.services import search_service
from app.services.citation_validation import CitationError, validate_answer
from app.services.conversation_context import evidence_question, retrieval_question
from app.services.embedding_providers import profile_for
from app.services.generation_capacity import CapacityBusy, generation_slot
from app.services.llm_providers import LLMEngine, LLMError, model_identifier
from app.services.rag_context import (
    Evidence,
    assemble_context,
    contradictory,
    make_prompt,
    relevant,
    sentences,
    terms,
)

INSUFFICIENT = "The indexed documents do not provide sufficient unambiguous evidence to answer this question."


@dataclass(frozen=True)
class AskOutcome:
    body: AskResponse
    http_status: int = 200


class RagMetrics:
    def __init__(self):
        self.lock, self.counts, self.total_ms = threading.Lock(), {}, 0.0

    def record(self, status, elapsed):
        with self.lock:
            self.counts[status] = self.counts.get(status, 0) + 1
            self.total_ms += elapsed

    def snapshot(self):
        with self.lock:
            return {"outcomes": dict(self.counts), "elapsed_ms_total": self.total_ms}


metrics = RagMetrics()
logger = logging.getLogger("evidenceai.rag")


def load_evidence(db, workspace_id, actor_id, retrieved, settings, *, full_chunks=False):
    if not retrieved:
        return []
    profile = profile_for(settings)
    rows = db.execute(
        select(DocumentChunk, Document.original_filename)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .join(
            WorkspaceMember,
            and_(
                WorkspaceMember.workspace_id == DocumentChunk.workspace_id,
                WorkspaceMember.user_id == actor_id,
            ),
        )
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            DocumentChunk.id.in_([r["chunk_id"] for r in retrieved]),
            DocumentChunk.workspace_id == workspace_id,
            Document.workspace_id == workspace_id,
            Document.processing_status == "completed",
            User.is_active.is_(True),
            ChunkEmbedding.profile_id == profile.id,
            ChunkEmbedding.dimensions == profile.dimensions,
            ChunkEmbedding.status == "completed",
        )
        .execution_options(populate_existing=True)
    ).all()
    mapping = {chunk.id: (chunk, filename) for chunk, filename in rows}
    result = []
    for row in retrieved:
        pair = mapping.get(row["chunk_id"])
        if pair is None:
            continue
        chunk, filename = pair
        if chunk.document_id != row["document_id"] or not chunk.text.startswith(
            row["excerpt"]
        ):
            continue
        result.append(
            Evidence(
                "",
                chunk.document_id,
                chunk.id,
                filename,
                chunk.text[:10000] if full_chunks else row["excerpt"],
                chunk.page_number,
                chunk.section,
                chunk.char_start,
                f"document:{chunk.document_id}"
                + (f"/page:{chunk.page_number}" if chunk.page_number else ""),
            )
        )
    return result


def revalidate_context(db, workspace_id, actor_id, context, filters, settings):
    document_workspace_access(db, workspace_id, actor_id)
    search_service.validate_filters(db, workspace_id, filters)
    current = load_evidence(
        db,
        workspace_id,
        actor_id,
        [
            {
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "excerpt": item.text,
            }
            for item in context
        ],
        settings,
    )
    valid = {item.chunk_id: item for item in current}
    return all(
        item.chunk_id in valid
        and replace(valid[item.chunk_id], citation_id=item.citation_id) == item
        for item in context
    )


def ask(db, workspace_id, actor_id, data, settings, *, engine=None, history=()):
    started = time.monotonic()
    deadline = started + settings.rag_request_timeout_seconds
    from app.core.telemetry import request_id as correlated_id, emit, registry
    from uuid import UUID
    request_id = UUID(correlated_id.get()) if correlated_id.get() else uuid4()
    context = []
    usage = None
    support_question = evidence_question(data.question, history)

    def finish(status, reason, *, http=200, claims=None, citations=None, answer=None):
        elapsed = (time.monotonic() - started) * 1000
        metrics.record(status, elapsed)
        registry.count('answers_total', (('outcome', status),))
        registry.observe('operation_seconds', (('operation','rag'),('outcome',status),('provider',settings.llm_provider)),elapsed/1000)
        emit('rag',workspace_id=workspace_id,request_id=request_id,provider=settings.llm_provider,outcome=status,duration_ms=round(elapsed,3))
        if reason in {'invalid_citations','citation_validation_failed','invalid_generation'}:
            registry.count('citation_rejections_total')
        if usage:
            for kind in ('input_tokens','output_tokens'):
                registry.count('tokens_total', (('kind',kind),('provider',settings.llm_provider)),getattr(usage,kind,0))
        logger.info(
            "rag_completed request_id=%s status=%s reason=%s elapsed_ms=%d evidence_count=%d provider=%s",
            request_id,
            status,
            reason,
            round(elapsed),
            len(context),
            settings.llm_provider,
        )
        return AskOutcome(
            AskResponse(
                answer=answer or INSUFFICIENT,
                status=status,
                reason=reason,
                claims=claims or [],
                citations=citations or [],
                retrieved_evidence_count=len(context),
                model_identifier=model_identifier(settings),
                usage=usage,
                request_id=request_id,
            ),
            http,
        )

    document_workspace_access(db, workspace_id, actor_id)
    search_service.validate_filters(db, workspace_id, data.document_ids)
    if not terms(data.question):
        return finish("insufficient_evidence", "ambiguous_question")
    try:
        retrieval_settings = settings.model_copy(
            update={
                "search_min_similarity": settings.rag_min_similarity,
                "embedding_request_budget_seconds": min(
                    settings.embedding_request_budget_seconds,
                    max(0.1, deadline - time.monotonic()),
                ),
                "embedding_http_timeout_seconds": min(
                    settings.embedding_http_timeout_seconds,
                    max(0.1, deadline - time.monotonic()),
                ),
            }
        )
        limit = min(data.retrieval_limit or settings.rag_retrieval_limit, settings.rag_retrieval_limit)
        if data.mode == "comparison":
            if limit < 2:
                return finish("insufficient_evidence", "comparison_passage_budget")
            groups = []
            for document_id in data.document_ids:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    return finish("retrieval_unavailable", "request_timeout", http=504)
                current_settings = retrieval_settings.model_copy(update={
                    "embedding_request_budget_seconds": min(remaining, settings.embedding_request_budget_seconds),
                    "embedding_http_timeout_seconds": min(remaining, settings.embedding_http_timeout_seconds)})
                groups.append(search_service.search(db, workspace_id, actor_id,
                    SearchRequest(query=retrieval_question(data.question, history),
                                  document_ids=[document_id], limit=max(1, limit//2)), current_settings))
            # Interleave so bounded context admits both sources before extra passages.
            found = [row for pair in zip(*groups) for row in pair]
        else:
            found = search_service.search(db, workspace_id, actor_id,
                SearchRequest(query=retrieval_question(data.question, history),
                              document_ids=data.document_ids, limit=limit), retrieval_settings)
        context = assemble_context(
            load_evidence(db, workspace_id, actor_id, found, settings, full_chunks=True), settings
        )
    except HTTPException as error:
        if error.status_code in {401, 403, 404, 422}:
            raise
        db.rollback()
        from app.services.provider_errors import PUBLIC_EMBEDDING_MESSAGES
        if isinstance(error.detail, dict) and error.detail.get("code") in PUBLIC_EMBEDDING_MESSAGES:
            code = error.detail["code"]
            return finish("retrieval_unavailable", code, http=503, answer=PUBLIC_EMBEDDING_MESSAGES[code])
        return finish(
            "retrieval_unavailable",
            "retrieval_unavailable",
            http=503,
            answer="Document retrieval is temporarily unavailable.",
        )
    except DBAPIError:
        db.rollback()
        return finish(
            "retrieval_unavailable",
            "retrieval_unavailable",
            http=503,
            answer="Document retrieval is temporarily unavailable.",
        )
    if time.monotonic() >= deadline:
        return finish(
            "retrieval_unavailable",
            "request_timeout",
            http=504,
            answer="Document retrieval exceeded the request time budget.",
        )
    if data.mode == "comparison" and {item.document_id for item in context} != set(data.document_ids):
        return finish("insufficient_evidence", "comparison_sources_missing")
    if not context:
        return finish("insufficient_evidence", "no_evidence", answer=(
            "No passages matched the selected sources and active embedding profile. "
            "Check the Documents page: extraction alone is not indexing. Index completed documents "
            "with the active profile, check source selection, then retry your question."))
    if contradictory(context, support_question):
        return finish("insufficient_evidence", "contradictory_evidence")
    if settings.llm_provider != "gemini" and not any(
        relevant(sentence, support_question)
        for item in context
        for sentence in sentences(item.text)
    ):
        return finish("insufficient_evidence", "unsupported_question")
    prompt = make_prompt(data.question, context, history, mode=data.mode)
    db.rollback()  # No source transaction spans provider I/O.
    try:
        with generation_slot(db, settings):
            engine = engine or LLMEngine(settings)
            reply = engine.generate(prompt, deadline=deadline)
            usage = reply.usage
            if not revalidate_context(
                db, workspace_id, actor_id, context, data.document_ids, settings
            ):
                return finish("insufficient_evidence", "evidence_changed")
            if time.monotonic() >= deadline:
                raise LLMError("timeout")
            claims, citations = validate_answer(
                reply.output, context, support_question, settings,
                relevance_verified=reply.relevance_verified
            )
            if data.mode == "comparison" and {item.document_id for item in citations} != set(data.document_ids):
                return finish("insufficient_evidence", "comparison_support_missing")
            if not claims:
                return finish("insufficient_evidence", "model_abstained")
            answer = "\n".join(
                claim.text
                + " "
                + "".join(f"[{identifier}]" for identifier in claim.citation_ids)
                for claim in claims
            )
            return finish(
                "answered",
                "validated_extracts",
                claims=claims,
                citations=citations,
                answer=answer,
            )
    except CapacityBusy:
        return finish(
            "provider_error",
            "capacity_busy",
            http=429,
            answer="Generation capacity is busy. Retry later.",
        )
    except LLMError as error:
        from app.services.provider_errors import GENERATION_MESSAGES
        return finish(
            "provider_error",
            "provider_" + error.code,
            http=504 if error.code == "timeout" else 503,
            answer=GENERATION_MESSAGES.get(error.code, "A validated document-grounded answer could not be generated. Please retry later."),
        )
    except CitationError:
        return finish(
            "provider_error",
            "invalid_generation",
            http=503,
            answer="The generated answer could not be validated against the document evidence.",
        )
    except DBAPIError:
        db.rollback()
        return finish(
            "retrieval_unavailable",
            "evidence_recheck_failed",
            http=503,
            answer="Document evidence could not be revalidated.",
        )
