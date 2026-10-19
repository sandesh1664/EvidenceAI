from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authorization import (workspace_access, require_manager, require_owner,
                                    require_consistent_ownership)
from app.models import Workspace, WorkspaceMember, Document
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.services.workspace_transaction import workspace_transaction


def create_workspace(db: Session, actor_id: UUID, data: WorkspaceCreate) -> Workspace:
    with workspace_transaction(db):
        workspace = Workspace(name=data.name, description=data.description, owner_id=actor_id)
        db.add(workspace)
        db.flush()
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=actor_id, role="owner"))
        db.flush()
    return workspace


def list_workspaces(db: Session, actor_id: UUID, limit: int, offset: int):
    return db.scalars(select(Workspace).join(WorkspaceMember).where(
        WorkspaceMember.user_id == actor_id).order_by(Workspace.created_at, Workspace.id)
        .limit(limit).offset(offset)).all()


def read_workspace(db: Session, workspace_id: UUID, actor_id: UUID):
    workspace, _ = workspace_access(db, workspace_id, actor_id)
    return workspace


def update_workspace(db: Session, workspace_id: UUID, actor_id: UUID, data: WorkspaceUpdate):
    with workspace_transaction(db):
        workspace, member = workspace_access(db, workspace_id, actor_id, lock=True)
        require_manager(workspace, member)
        require_consistent_ownership(db, workspace)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(workspace, field, value)
        db.flush()
    return workspace


def delete_workspace(db: Session, workspace_id: UUID, actor_id: UUID):
    with workspace_transaction(db):
        workspace, member = workspace_access(db, workspace_id, actor_id, lock=True)
        require_owner(workspace, member)
        require_consistent_ownership(db, workspace)
        other_member = db.scalar(select(WorkspaceMember.id).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id != actor_id).limit(1))
        document = db.scalar(select(Document.id).where(Document.workspace_id == workspace_id).limit(1))
        if other_member is not None or document is not None:
            raise HTTPException(409, "Workspace has other members or documents")
        # Only the mandatory owner membership is removed with an otherwise empty
        # workspace. RESTRICT FKs remain the final defense against dependent records.
        db.delete(member)
        db.flush()
        db.delete(workspace)
        db.flush()
