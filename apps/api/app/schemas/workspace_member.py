from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    role: Literal["admin", "member"] = "member"


class MemberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "member"]


class OwnershipTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_owner_id: UUID


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: Literal["owner", "admin", "member"]
    joined_at: datetime
