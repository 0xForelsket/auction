import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )

    source: Mapped[str] = mapped_column(String(50), server_default=text("'upload'"))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    status: Mapped[str] = mapped_column(String(50), server_default=text("'queued'"))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    original_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumb_path: Mapped[str | None] = mapped_column(String(500))
    preprocessed_path: Mapped[str | None] = mapped_column(String(500))

    roi: Mapped[dict | None] = mapped_column(JSONB)

    hash_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    model_version: Mapped[str | None] = mapped_column(String(50))
    pipeline_version: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    uploaded_by_user = relationship("User", back_populates="documents")
    record = relationship("AuctionRecord", back_populates="document", uselist=False)
    whatsapp_meta = relationship("WhatsappMeta", back_populates="document")
