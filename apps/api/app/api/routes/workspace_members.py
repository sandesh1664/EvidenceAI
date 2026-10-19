from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.workspace import WorkspaceResponse
from app.schemas.workspace_member import MemberCreate, MemberUpdate, MemberResponse, OwnershipTransfer
from app.services import workspace_member_service

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspace members"])


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
def list_members(workspace_id: UUID, limit: int = Query(default=50, ge=1, le=100),
                 offset: int = Query(default=0, ge=0), user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return workspace_member_service.list_members(db, workspace_id, user.id, limit, offset)


@router.post("/{workspace_id}/members", response_model=MemberResponse, status_code=201)
def add_member(workspace_id: UUID, data: MemberCreate,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return workspace_member_service.add_member(db, workspace_id, user.id, data)


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberResponse)
def update_member(workspace_id: UUID, user_id: UUID, data: MemberUpdate,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return workspace_member_service.update_member(db, workspace_id, user.id, user_id, data)


@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
def remove_member(workspace_id: UUID, user_id: UUID,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    workspace_member_service.remove_member(db, workspace_id, user.id, user_id)


@router.post("/{workspace_id}/transfer-ownership", response_model=WorkspaceResponse)
def transfer_ownership(workspace_id: UUID, data: OwnershipTransfer,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return workspace_member_service.transfer_ownership(db, workspace_id, user.id, data)
