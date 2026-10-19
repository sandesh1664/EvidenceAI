from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse
from app.services import workspace_service

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.post("/", response_model=WorkspaceResponse, status_code=201)
def create_workspace(data: WorkspaceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return workspace_service.create_workspace(db, user.id, data)


@router.get("/", response_model=list[WorkspaceResponse])
def list_workspaces(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return workspace_service.list_workspaces(db, user.id, limit, offset)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def read_workspace(workspace_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return workspace_service.read_workspace(db, workspace_id, user.id)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(workspace_id: UUID, data: WorkspaceUpdate,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return workspace_service.update_workspace(db, workspace_id, user.id, data)


@router.delete("/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    workspace_service.delete_workspace(db, workspace_id, user.id)
