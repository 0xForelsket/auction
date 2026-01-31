import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
    Index,
    Computed,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuctionRecord(Base):
    __tablename__ = "auction_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    auction_date: Mapped[date | None] = mapped_column(Date)
    auction_venue: Mapped[str | None] = mapped_column(String(255))
    auction_venue_round: Mapped[str | None] = mapped_column(String(50))
    lot_no: Mapped[str | None] = mapped_column(String(100))

    make: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(255))
    make_model: Mapped[str | None] = mapped_column(String(255))
    grade: Mapped[str | None] = mapped_column(String(100))
    model_code: Mapped[str | None] = mapped_column(String(100))
    chassis_no: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int | None] = mapped_column(Integer)

    model_year_reiwa: Mapped[str | None] = mapped_column(String(10))
    model_year_gregorian: Mapped[int | None] = mapped_column(Integer)

    inspection_expiry_raw: Mapped[str | None] = mapped_column(Text)
    inspection_expiry_month: Mapped[date | None] = mapped_column(Date)

    engine_cc: Mapped[int | None] = mapped_column(Integer)
    transmission: Mapped[str | None] = mapped_column(String(20))

    mileage_km: Mapped[int | None] = mapped_column(Integer)
    mileage_raw: Mapped[str | None] = mapped_column(Text)
    mileage_multiplier: Mapped[int | None] = mapped_column(Integer)
    mileage_inference_conf: Mapped[float | None] = mapped_column(Numeric(3, 2))

    score: Mapped[str | None] = mapped_column(String(20))
    score_numeric: Mapped[float | None] = mapped_column(Numeric(3, 1))
    color: Mapped[str | None] = mapped_column(String(100))

    result: Mapped[str | None] = mapped_column(String(50))
    starting_bid_yen: Mapped[int | None] = mapped_column(Integer)
    final_bid_yen: Mapped[int | None] = mapped_column(Integer)

    starting_bid_man: Mapped[int | None] = mapped_column(
        Integer, Computed("starting_bid_yen / 10000", persisted=True)
    )
    final_bid_man: Mapped[int | None] = mapped_column(
        Integer, Computed("final_bid_yen / 10000", persisted=True)
    )

    lane_type: Mapped[str | None] = mapped_column(String(50))
    equipment_codes: Mapped[str | None] = mapped_column(Text)

    make_ja: Mapped[str | None] = mapped_column(String(100))
    make_en: Mapped[str | None] = mapped_column(String(100))
    model_ja: Mapped[str | None] = mapped_column(String(100))
    model_en: Mapped[str | None] = mapped_column(String(100))

    inspector_notes: Mapped[dict | None] = mapped_column(JSONB)
    damage_locations: Mapped[list | None] = mapped_column(JSONB)

    notes_text: Mapped[str | None] = mapped_column(Text)
    options_text: Mapped[str | None] = mapped_column(Text)
    full_text: Mapped[str | None] = mapped_column(Text)

    evidence: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    needs_review: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    review_reason: Mapped[str | None] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    overall_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))

    fts_vector_en: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', "
            "coalesce(lot_no, '') || ' ' || "
            "coalesce(auction_venue, '') || ' ' || "
            "coalesce(auction_venue_round, '') || ' ' || "
            "coalesce(make_model, '') || ' ' || "
            "coalesce(model_code, '') || ' ' || "
            "coalesce(chassis_no, '') || ' ' || "
            "coalesce(notes_text, '') || ' ' || "
            "coalesce(options_text, '') || ' ' || "
            "coalesce(full_text, '')"
            ")",
            persisted=True,
        ),
    )

    search_text: Mapped[str | None] = mapped_column(
        Text,
        Computed(
            "coalesce(lot_no, '') || ' ' || "
            "coalesce(auction_venue, '') || ' ' || "
            "coalesce(auction_venue_round, '') || ' ' || "
            "coalesce(make_model, '') || ' ' || "
            "coalesce(make_ja, '') || ' ' || "
            "coalesce(make_en, '') || ' ' || "
            "coalesce(model_ja, '') || ' ' || "
            "coalesce(model_en, '') || ' ' || "
            "coalesce(model_code, '') || ' ' || "
            "coalesce(chassis_no, '') || ' ' || "
            "coalesce(notes_text, '') || ' ' || "
            "coalesce(options_text, '')",
            persisted=True,
        ),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )

    document = relationship("Document", back_populates="record")
    overrides = relationship("Override", back_populates="record")

    __table_args__ = (
        Index("idx_records_document", "document_id"),
        Index("idx_records_auction_date", "auction_date"),
        Index("idx_records_auction_venue", "auction_venue"),
        Index("idx_records_lot", "lot_no"),
        Index("idx_records_make_model", "make_model"),
        Index("idx_records_model_code", "model_code"),
        Index("idx_records_chassis_no", "chassis_no"),
        Index("idx_records_mileage", "mileage_km"),
        Index("idx_records_score", "score_numeric"),
        Index("idx_records_price", "final_bid_yen"),
        Index(
            "idx_records_needs_review",
            "needs_review",
            postgresql_where=text("needs_review = true"),
        ),
        Index("idx_records_fts_en", "fts_vector_en", postgresql_using="gin"),
        Index(
            "idx_records_make_model_trgm",
            "make_model",
            postgresql_using="gin",
            postgresql_ops={"make_model": "gin_trgm_ops"},
        ),
        Index(
            "idx_records_model_code_trgm",
            "model_code",
            postgresql_using="gin",
            postgresql_ops={"model_code": "gin_trgm_ops"},
        ),
        Index(
            "idx_records_chassis_no_trgm",
            "chassis_no",
            postgresql_using="gin",
            postgresql_ops={"chassis_no": "gin_trgm_ops"},
        ),
        Index(
            "idx_records_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
        Index("idx_records_evidence", "evidence", postgresql_using="gin"),
    )
