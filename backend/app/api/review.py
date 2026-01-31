from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db import get_db
from app.models.override import Override
from app.models.record import AuctionRecord
from app.schemas.common import Page
from app.schemas.record import RecordListItem, RecordRead
from app.schemas.review import OverrideCreate, VerifyRequest

router = APIRouter()


@router.get("/queue", response_model=Page[RecordListItem])
async def review_queue(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    offset = (page - 1) * per_page
    query = select(AuctionRecord).where(AuctionRecord.needs_review.is_(True))
    total = await db.scalar(
        select(func.count()).select_from(AuctionRecord).where(AuctionRecord.needs_review.is_(True))
    )
    result = await db.execute(query.order_by(AuctionRecord.created_at.desc()).offset(offset).limit(per_page))
    items = result.scalars().all()
    return Page(items=items, page=page, per_page=per_page, total=total or 0)


@router.post("/{record_id}/override", response_model=RecordRead)
async def override_record(
    record_id: UUID,
    payload: OverrideCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(select(AuctionRecord).where(AuctionRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    allowed_fields = set(AuctionRecord.__table__.columns.keys())
    if payload.field_name not in allowed_fields:
        raise HTTPException(status_code=400, detail="Field cannot be overridden")

    old_value = getattr(record, payload.field_name)
    setattr(record, payload.field_name, payload.new_value)
    record.needs_review = True
    record.is_verified = False
    record.verified_by = None
    record.verified_at = None
    if payload.reason:
        record.review_reason = payload.reason

    override = Override(
        record_id=record.id,
        field_name=payload.field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=payload.new_value,
        reason=payload.reason,
        user_id=current_user.id,
    )
    db.add(override)
    await db.commit()
    await db.refresh(record)
    return record


@router.post("/{record_id}/verify", response_model=RecordRead)
async def verify_record(
    record_id: UUID,
    payload: VerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(select(AuctionRecord).where(AuctionRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    record.is_verified = payload.verified
    record.needs_review = not payload.verified
    record.verified_by = current_user.id
    record.verified_at = datetime.now(timezone.utc)
    if payload.verified:
        record.review_reason = None
    await db.commit()
    await db.refresh(record)
    return record
