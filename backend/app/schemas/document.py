from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    status: str
    original_path: str
    thumb_path: str | None
    preprocessed_path: str | None
    hash_sha256: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    processing_started_at: datetime | None
    processing_completed_at: datetime | None


class DocumentStatus(BaseModel):
    id: UUID
    status: str
    error_message: str | None = None
    needs_review: bool | None = None


class DocumentUploadResponse(BaseModel):
    status: str
    document_id: UUID | None = None
    existing_id: UUID | None = None
