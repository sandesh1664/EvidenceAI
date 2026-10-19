"""Durable, idempotent conversation turns with short authorization transactions."""

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.exc import SQLAlchemyError

from app.core.authorization import document_workspace_access
from app.models import (
    ChunkEmbedding,
    Conversation,
    Document,
    DocumentChunk,
    Message,
    MessageCitation,
    User,
)
from app.schemas.ask import AskRequest
from app.schemas.conversation import (
    ConversationPage,
    ConversationResponse,
    MessagePage,
    MessageResponse,
    SavedCitation,
    TurnResponse,
)
from app.services import rag_service, search_service
from app.services.conversation_context import bounded_history
from app.services.embedding_providers import profile_for


@contextmanager
def transaction(db):
    try:
        yield
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            503, "Conversation storage temporarily unavailable"
        ) from None
    except BaseException:
        db.rollback()
        raise


def owned(db, workspace_id, conversation_id, actor_id, *, lock=False):
    document_workspace_access(db, workspace_id, actor_id, lock=lock)
    if (
        db.scalar(select(User.id).where(User.id == actor_id, User.is_active.is_(True)))
        is None
    ):
        raise HTTPException(404, "Conversation not found")
    query = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.workspace_id == workspace_id,
        Conversation.owner_id == actor_id,
    )
    if lock:
        query = query.with_for_update()
    result = db.scalar(query.execution_options(populate_existing=True))
    if result is None:
        raise HTTPException(404, "Conversation not found")
    return result


def create(db, workspace_id, actor_id, data):
    with transaction(db):
        document_workspace_access(db, workspace_id, actor_id, lock=True)
        result = Conversation(
            workspace_id=workspace_id, owner_id=actor_id, title=data.title
        )
        db.add(result)
        db.flush()
        response = ConversationResponse.model_validate(result)
    return response


def read(db, workspace_id, conversation_id, actor_id):
    return ConversationResponse.model_validate(
        owned(db, workspace_id, conversation_id, actor_id)
    )


def listing(db, workspace_id, actor_id, limit, cursor, include_archived):
    document_workspace_access(db, workspace_id, actor_id)
    query = select(Conversation).where(
        Conversation.workspace_id == workspace_id, Conversation.owner_id == actor_id
    )
    if not include_archived:
        query = query.where(Conversation.archived_at.is_(None))
    if cursor:
        anchor = owned(db, workspace_id, cursor, actor_id)
        if not include_archived and anchor.archived_at is not None:
            raise HTTPException(404, "Conversation cursor not found")
        query = query.where(
            tuple_(Conversation.created_at, Conversation.id)
            < tuple_(anchor.created_at, anchor.id)
        )
    rows = db.scalars(
        query.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(
            limit + 1
        )
    ).all()
    return ConversationPage(
        items=[ConversationResponse.model_validate(row) for row in rows[:limit]],
        next_cursor=rows[limit - 1].id if len(rows) > limit else None,
    )


def update(db, workspace_id, conversation_id, actor_id, data):
    with transaction(db):
        result = owned(db, workspace_id, conversation_id, actor_id, lock=True)
        now = db.scalar(select(func.clock_timestamp()))
        if "title" in data.model_fields_set:
            result.title = data.title
        if "archived" in data.model_fields_set:
            result.archived_at = now if data.archived else None
        result.updated_at = now
        db.flush()
        response = ConversationResponse.model_validate(result)
    return response


def remove(db, workspace_id, conversation_id, actor_id):
    with transaction(db):
        owned(db, workspace_id, conversation_id, actor_id, lock=True)
        db.execute(delete(Conversation).where(Conversation.id == conversation_id))


def message_models(db, rows):
    if not rows:
        return []
    citations = db.scalars(
        select(MessageCitation)
        .where(MessageCitation.message_id.in_([row.id for row in rows]))
        .order_by(MessageCitation.ordering)
        .execution_options(populate_existing=True)
    ).all()
    mapping = {}
    for citation in citations:
        mapping.setdefault(citation.message_id, []).append(
            SavedCitation.model_validate(citation)
        )
    return [
        MessageResponse.model_validate(row).model_copy(
            update={"citations": mapping.get(row.id, [])}
        )
        for row in rows
    ]


def messages(db, workspace_id, conversation_id, actor_id, limit, after_sequence):
    with transaction(db):
        owned(db, workspace_id, conversation_id, actor_id, lock=True)
        expire_pending(db, conversation_id, db.scalar(select(func.clock_timestamp())))
        rows = db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sequence > after_sequence,
            )
            .order_by(Message.sequence)
            .limit(limit + 1)
            .execution_options(populate_existing=True)
        ).all()
        response = MessagePage(
            items=message_models(db, rows[:limit]),
            next_after_sequence=rows[limit - 1].sequence if len(rows) > limit else None,
        )
    return response


def fingerprint(data):
    value = data.model_dump(mode="json", exclude={"idempotency_key"})
    if value["document_ids"] is not None:
        value["document_ids"].sort()
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def fail(message, reason):
    message.content = (
        "A validated answer could not be saved. Submit a new turn to retry."
    )
    message.generation_status = "failed"
    message.answer_status = "provider_error"
    message.reason = reason
    message.generation_http_status = 503
    message.lease_expires_at = None
    message.claims = []


def expire_pending(db, conversation_id, now):
    pending = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.generation_status == "pending",
        )
    )
    if pending and pending.lease_expires_at <= now:
        fail(pending, "generation_expired")
        db.flush()  # Release the partial unique index before another turn is reserved.
        return None
    return pending


def turn_response(db, conversation_id, sequence, replayed):
    rows = db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sequence.in_([sequence, sequence + 1]),
        )
        .order_by(Message.sequence)
        .execution_options(populate_existing=True)
    ).all()
    if len(rows) != 2:
        raise HTTPException(404, "Conversation turn not found")
    user, assistant = message_models(db, rows)
    return TurnResponse(
        user_message=user, assistant_message=assistant, replayed=replayed
    )


@dataclass(frozen=True)
class Reservation:
    assistant_id: object
    sequence: int
    history: list


def reserve(db, workspace_id, conversation_id, actor_id, data, settings):
    with transaction(db):
        conversation = owned(db, workspace_id, conversation_id, actor_id, lock=True)
        now = db.scalar(select(func.clock_timestamp()))
        pending = expire_pending(db, conversation_id, now)
        existing = db.scalar(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.idempotency_key == data.idempotency_key,
            )
        )
        if existing:
            if existing.request_fingerprint != fingerprint(data):
                raise HTTPException(
                    409, "Idempotency key was used for a different request"
                )
            return turn_response(db, conversation_id, existing.sequence, True)
        if conversation.archived_at is not None:
            raise HTTPException(409, "Conversation is archived")
        if pending:
            raise HTTPException(
                409,
                "A conversation turn is already generating",
                headers={"Retry-After": "2"},
            )
        search_service.validate_filters(db, workspace_id, data.document_ids)
        prior = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sequence.desc())
            .limit(settings.conversation_history_messages)
        ).all()
        history = bounded_history(list(reversed(prior)), settings)
        sequence = conversation.next_sequence
        user = Message(
            conversation_id=conversation_id,
            role="user",
            content=data.question,
            sequence=sequence,
            generation_status="completed",
            idempotency_key=data.idempotency_key,
            request_fingerprint=fingerprint(data),
        )
        assistant = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role="assistant",
            content="",
            sequence=sequence + 1,
            generation_status="pending",
            lease_expires_at=now
            + timedelta(seconds=settings.conversation_turn_lease_seconds),
            request_id=uuid4(),
        )
        db.add_all([user, assistant])
        conversation.next_sequence += 2
        conversation.last_activity_at = conversation.updated_at = now
        db.flush()
        return Reservation(assistant.id, sequence, history)


def current_citations(db, workspace_id, citations, settings):
    if not citations:
        return True
    profile = profile_for(settings)
    rows = db.execute(
        select(DocumentChunk, Document.original_filename)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .where(
            DocumentChunk.id.in_([item.chunk_id for item in citations]),
            DocumentChunk.workspace_id == workspace_id,
            Document.workspace_id == workspace_id,
            Document.processing_status == "completed",
            ChunkEmbedding.profile_id == profile.id,
            ChunkEmbedding.dimensions == profile.dimensions,
            ChunkEmbedding.status == "completed",
        )
        .execution_options(populate_existing=True)
    ).all()
    mapping = {chunk.id: (chunk, filename) for chunk, filename in rows}
    for item in citations:
        if item.chunk_id not in mapping:
            return False
        chunk, filename = mapping[item.chunk_id]
        start = item.char_start - chunk.char_start
        if (
            chunk.document_id != item.document_id
            or start < 0
            or filename != item.filename
            or chunk.page_number != item.page_number
            or chunk.section != item.section
            or chunk.text[start : start + len(item.supporting_excerpt)]
            != item.supporting_excerpt
        ):
            return False
    return True


def finalize(db, workspace_id, conversation_id, actor_id, reserved, outcome, settings):
    with transaction(db):
        conversation = owned(db, workspace_id, conversation_id, actor_id, lock=True)
        now = db.scalar(select(func.clock_timestamp()))
        expire_pending(db, conversation_id, now)
        assistant = db.get(Message, reserved.assistant_id, populate_existing=True)
        if assistant is None:
            raise HTTPException(404, "Conversation turn not found")
        if assistant.generation_status != "pending":
            return turn_response(db, conversation_id, reserved.sequence, True)
        body = outcome.body
        http = outcome.http_status
        if not current_citations(db, workspace_id, body.citations, settings):
            body = body.model_copy(
                update={
                    "answer": rag_service.INSUFFICIENT,
                    "status": "insufficient_evidence",
                    "reason": "evidence_changed",
                    "claims": [],
                    "citations": [],
                }
            )
            http = 200
        assistant.content = body.answer
        assistant.generation_status = (
            "failed"
            if body.status in {"provider_error", "retrieval_unavailable"}
            else "completed"
        )
        assistant.answer_status, assistant.reason = body.status, body.reason
        assistant.model_identifier = body.model_identifier
        assistant.usage = body.usage.model_dump(mode="json") if body.usage else None
        assistant.claims = [claim.model_dump(mode="json") for claim in body.claims]
        assistant.retrieved_evidence_count = body.retrieved_evidence_count
        assistant.request_id = body.request_id
        assistant.generation_http_status = http
        assistant.lease_expires_at = None
        for ordering, item in enumerate(body.citations):
            db.add(
                MessageCitation(
                    message_id=assistant.id,
                    document_id=item.document_id,
                    chunk_id=item.chunk_id,
                    original_document_id=item.document_id,
                    original_chunk_id=item.chunk_id,
                    citation_id=item.citation_id,
                    supporting_excerpt=item.supporting_excerpt,
                    filename=item.filename,
                    page_number=item.page_number,
                    section=item.section,
                    source_ref=item.source_ref,
                    char_start=item.char_start,
                    char_end=item.char_end,
                    ordering=ordering,
                    validation_metadata={
                        "method": "exact_quote_v1",
                        "validated_at": now.isoformat(),
                        "claim_ids": item.claim_ids,
                    },
                )
            )
        conversation.last_activity_at = conversation.updated_at = now
        db.flush()
        return turn_response(db, conversation_id, reserved.sequence, False)


def abandon(db, conversation_id, assistant_id):
    # Internal cleanup writes only a fixed failure marker; it never saves generated
    # content after revoked authorization, nor recreates a deleted conversation.
    with transaction(db):
        conversation = db.scalar(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .with_for_update()
        )
        if conversation:
            message = db.get(Message, assistant_id, populate_existing=True)
            if message and message.generation_status == "pending":
                fail(message, "generation_interrupted")


def submit(db, workspace_id, conversation_id, actor_id, data, settings):
    reserved = reserve(db, workspace_id, conversation_id, actor_id, data, settings)
    if isinstance(reserved, TurnResponse):
        return reserved
    try:
        outcome = rag_service.ask(
            db,
            workspace_id,
            actor_id,
            AskRequest.model_validate(data.model_dump(exclude={"idempotency_key"})),
            settings,
            history=reserved.history,
        )
        return finalize(
            db, workspace_id, conversation_id, actor_id, reserved, outcome, settings
        )
    except Exception as error:
        db.rollback()
        try:
            abandon(db, conversation_id, reserved.assistant_id)
        except Exception:  # noqa: BLE001 - cleanup cannot expose storage/provider errors
            db.rollback()
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(
            503, "Conversation generation temporarily unavailable"
        ) from None
