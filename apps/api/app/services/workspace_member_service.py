from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authorization import (workspace_access, require_manager, require_owner,
                                    require_consistent_ownership, require_manageable_member)
from app.models import User, WorkspaceMember
from app.schemas.workspace_member import MemberCreate, MemberUpdate, OwnershipTransfer
from app.services.workspace_transaction import workspace_transaction


def member_record(db: Session, workspace_id: UUID, user_id: UUID):
    member = db.scalar(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
    ).execution_options(populate_existing=True))
    if member is None:
        raise HTTPException(404, "Member not found")
    return member


def eligible_user(db: Session, user_id: UUID):
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True),
                                       User.password_hash.is_not(None)).with_for_update(read=True)
                     .execution_options(populate_existing=True))
    if user is None:
        raise HTTPException(404, "Eligible user not found")
    return user


def list_members(db: Session, workspace_id: UUID, actor_id: UUID, limit: int, offset: int):
    workspace_access(db, workspace_id, actor_id)
    return db.scalars(select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
                      .order_by(WorkspaceMember.joined_at, WorkspaceMember.id).limit(limit).offset(offset)).all()


def add_member(db: Session, workspace_id: UUID, actor_id: UUID, data: MemberCreate):
    with workspace_transaction(db):
        workspace, actor = workspace_access(db, workspace_id, actor_id, lock=True)
        require_manager(workspace, actor)
        require_consistent_ownership(db, workspace)
        eligible_user(db, data.user_id)
        if db.scalar(select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == data.user_id)):
            raise HTTPException(409, "User is already a workspace member")
        member = WorkspaceMember(workspace_id=workspace_id, user_id=data.user_id, role=data.role)
        db.add(member)
        db.flush()
    return member


def update_member(db: Session, workspace_id: UUID, actor_id: UUID, user_id: UUID, data: MemberUpdate):
    with workspace_transaction(db):
        workspace, actor = workspace_access(db, workspace_id, actor_id, lock=True)
        require_manager(workspace, actor)
        require_consistent_ownership(db, workspace)
        member = member_record(db, workspace_id, user_id)
        require_manageable_member(actor, member)
        member.role = data.role
        db.flush()
    return member


def remove_member(db: Session, workspace_id: UUID, actor_id: UUID, user_id: UUID):
    with workspace_transaction(db):
        workspace, actor = workspace_access(db, workspace_id, actor_id, lock=True)
        require_manager(workspace, actor)
        require_consistent_ownership(db, workspace)
        member = member_record(db, workspace_id, user_id)
        require_manageable_member(actor, member)
        db.delete(member)
        db.flush()


def transfer_ownership(db: Session, workspace_id: UUID, actor_id: UUID, data: OwnershipTransfer):
    with workspace_transaction(db):
        workspace, actor = workspace_access(db, workspace_id, actor_id, lock=True)
        require_owner(workspace, actor)
        require_consistent_ownership(db, workspace)
        if data.new_owner_id == actor_id:
            raise HTTPException(409, "User already owns this workspace")
        target = member_record(db, workspace_id, data.new_owner_id)
        eligible_user(db, data.new_owner_id)
        # All three writes commit together while holding the workspace row lock.
        actor.role = "admin"
        target.role = "owner"
        workspace.owner_id = data.new_owner_id
        db.flush()
    return workspace
