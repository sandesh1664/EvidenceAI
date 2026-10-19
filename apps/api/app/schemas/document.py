from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    uploaded_by: UUID
    original_filename: str
    mime_type: str | None
    file_size: int | None
    checksum_sha256: str
    processing_status: Literal["pending", "processing", "completed", "failed"]
    processing_error: str | None
    processing_attempts: int
    last_processed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator('processing_error', mode='before')
    @classmethod
    def safe_processing_error(cls, value):
        from app.core.document_errors import SAFE_PROCESSING_ERRORS
        if value is None or value in SAFE_PROCESSING_ERRORS:
            return value
        # Preserve legacy DB values but never expose arbitrary old exception strings.
        return 'Document processing failed'
