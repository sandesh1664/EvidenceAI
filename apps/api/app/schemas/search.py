from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    offset: int = Field(default=0, ge=0, le=1000, strict=True)
    query: str = Field(min_length=1,max_length=2000)
    limit: int = Field(default=10,ge=1,le=50,strict=True)
    document_ids: list[UUID] | None = Field(default=None,max_length=50)

    @field_validator('query')
    @classmethod
    def valid_query(cls,value):
        value = value.strip()
        if not value or '\x00' in value or len(value.encode('utf-8'))>6000:
            raise ValueError('Invalid search query')
        return value

    @field_validator('document_ids')
    @classmethod
    def unique_documents(cls,value):
        if value is not None and len(set(value)) != len(value):
            raise ValueError('Document filters must be unique')
        return value


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    excerpt: str
    page_number: int | None
    section: str | None
    source_ref: str
    similarity: float = Field(ge=-1,le=1)
    embedding_model: str


class IndexRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    force: bool = Field(default=False,strict=True)


class IndexStatus(BaseModel):
    ready_for_research: bool = False
    indexing_complete: bool = False
    research_blocker: str | None = None
    indexing_blocker: str | None = None
    document_id: UUID
    embedding_model: str
    dimensions: int
    state: Literal['not_indexed','queued','running','done','failed']
    generation: UUID | None
    attempts: int
    total_chunks: int
    indexed_chunks: int
    current_generation_chunks: int
    error: str | None
    last_attempt_at: datetime | None
