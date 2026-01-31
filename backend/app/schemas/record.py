from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RecordBase(BaseModel):
    auction_date: date | None = None
    auction_venue: str | None = None
    auction_venue_round: str | None = None
    lot_no: str | None = None

    make: str | None = None
    model: str | None = None
    make_model: str | None = None
    grade: str | None = None
    model_code: str | None = None
    chassis_no: str | None = None
    year: int | None = None

    model_year_reiwa: str | None = None
    model_year_gregorian: int | None = None

    inspection_expiry_raw: str | None = None
    inspection_expiry_month: date | None = None

    engine_cc: int | None = None
    transmission: str | None = None

    mileage_km: int | None = None
    mileage_raw: str | None = None
    mileage_multiplier: int | None = None
    mileage_inference_conf: float | None = None

    score: str | None = None
    score_numeric: float | None = None
    color: str | None = None

    result: str | None = None
    starting_bid_yen: int | None = None
    final_bid_yen: int | None = None

    lane_type: str | None = None
    equipment_codes: str | None = None

    make_ja: str | None = None
    make_en: str | None = None
    model_ja: str | None = None
    model_en: str | None = None

    inspector_notes: dict | None = None
    damage_locations: list | None = None

    notes_text: str | None = None
    options_text: str | None = None
    full_text: str | None = None

    evidence: dict | None = None

    needs_review: bool | None = None
    review_reason: str | None = None
    is_verified: bool | None = None
    verified_by: UUID | None = None
    verified_at: datetime | None = None

    overall_confidence: float | None = None


class RecordRead(RecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    created_at: datetime
    updated_at: datetime


class RecordUpdate(RecordBase):
    pass


class RecordListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    lot_no: str | None = None
    auction_date: date | None = None
    auction_venue: str | None = None
    make_model: str | None = None
    score: str | None = None
    final_bid_yen: int | None = None
    needs_review: bool | None = None
    created_at: datetime
