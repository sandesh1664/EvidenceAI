"""Workspace access policy; mutations lock before checking current membership."""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Workspace, WorkspaceMember


NOT_FOUND = "Workspace not found"


def workspace_access(db: Session, workspace_id: UUID, actor_id: UUID, *, lock: bool = False):
    if not lock:
        row = db.execute(select(Workspace, WorkspaceMember).join(
            WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id).where(
            Workspace.id == workspace_id, WorkspaceMember.user_id == actor_id
        ).execution_options(populate_existing=True)).first()
        if row is None:
            raise HTTPException(404, NOT_FOUND)
        return row

    # Lock the workspace FIRST, then load membership in a fresh READ COMMITTED
    # statement. A waiter must not authorize using membership cached before a transfer.
    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id)
                          .with_for_update().execution_options(populate_existing=True))
    if workspace is None:
        raise HTTPException(404, NOT_FOUND)
    member = db.scalar(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == actor_id
    ).execution_options(populate_existing=True))
    if member is None:
        raise HTTPException(404, NOT_FOUND)
    return workspace, member


def require_owner(workspace: Workspace, member: WorkspaceMember):
    if member.user_id != workspace.owner_id or member.role != "owner":
        raise HTTPException(403, "Owner permission required")


def require_manager(workspace: Workspace, member: WorkspaceMember):
    if member.role == "admin":
        return
    require_owner(workspace, member)


def require_consistent_ownership(db: Session, workspace: Workspace):
    owners = db.scalars(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.role == "owner"
    ).execution_options(populate_existing=True)).all()
    if len(owners) != 1 or owners[0].user_id != workspace.owner_id:
        # Legacy/direct-SQL inconsistencies are never silently repaired or promoted.
        raise HTTPException(409, "Workspace ownership is inconsistent")


def require_manageable_member(actor: WorkspaceMember, target: WorkspaceMember):
    if target.role == "owner":
        raise HTTPException(409, "Use ownership transfer to change the owner")
    if actor.role == "admin" and target.role != "member":
        raise HTTPException(403, "Admins can only change or remove ordinary members")
