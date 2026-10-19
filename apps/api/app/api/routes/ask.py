from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.ask import AskRequest, AskResponse
from app.services.rag_service import ask

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}", tags=["question answering"]
)


@router.post("/ask", response_model=AskResponse)
def ask_question(
    workspace_id: UUID,
    data: AskRequest,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    result = ask(db, workspace_id, user.id, data, settings)
    response.status_code = result.http_status
    response.headers["X-Request-ID"] = str(result.body.request_id)
    if result.http_status == 429:
        response.headers["Retry-After"] = "1"
    return result.body
