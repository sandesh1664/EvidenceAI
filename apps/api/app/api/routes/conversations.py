from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationPage,
    ConversationResponse,
    ConversationUpdate,
    MessageCreate,
    MessagePage,
    TurnResponse,
)
from app.services import conversation_service as service

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/conversations", tags=["conversations"]
)
Actor = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]
Configuration = Annotated[Settings, Depends(get_settings)]


@router.post("", response_model=ConversationResponse, status_code=201)
def create(workspace_id: UUID, data: ConversationCreate, user: Actor, db: Database):
    return service.create(db, workspace_id, user.id, data)


@router.get("", response_model=ConversationPage)
def listing(
    workspace_id: UUID,
    user: Actor,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: UUID | None = None,
    include_archived: bool = False,
):
    return service.listing(db, workspace_id, user.id, limit, cursor, include_archived)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def read(workspace_id: UUID, conversation_id: UUID, user: Actor, db: Database):
    return service.read(db, workspace_id, conversation_id, user.id)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update(
    workspace_id: UUID,
    conversation_id: UUID,
    data: ConversationUpdate,
    user: Actor,
    db: Database,
):
    return service.update(db, workspace_id, conversation_id, user.id, data)


@router.delete("/{conversation_id}", status_code=204)
def remove(workspace_id: UUID, conversation_id: UUID, user: Actor, db: Database):
    service.remove(db, workspace_id, conversation_id, user.id)


@router.get("/{conversation_id}/messages", response_model=MessagePage)
def messages(
    workspace_id: UUID,
    conversation_id: UUID,
    user: Actor,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after_sequence: Annotated[int, Query(ge=0)] = 0,
):
    return service.messages(
        db, workspace_id, conversation_id, user.id, limit, after_sequence
    )


@router.post(
    "/{conversation_id}/messages", response_model=TurnResponse, status_code=201
)
def submit(
    workspace_id: UUID,
    conversation_id: UUID,
    data: MessageCreate,
    response: Response,
    user: Actor,
    db: Database,
    settings: Configuration,
):
    turn = service.submit(db, workspace_id, conversation_id, user.id, data, settings)
    response.status_code = (
        202
        if turn.assistant_message.generation_status == "pending"
        else 200
        if turn.replayed
        else 201
    )
    response.headers["X-Request-ID"] = str(turn.assistant_message.request_id)
    if response.status_code == 202:
        response.headers["Retry-After"] = "2"
    return turn
