from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db import get_db
from app.models.document import Document
from app.models.record import AuctionRecord
from app.schemas.common import Page
from app.schemas.record import RecordListItem, RecordRead, RecordUpdate
from app.services.search import RecordFilters, apply_record_filters

router = APIRouter()


@router.get("", response_model=Page[RecordListItem])
async def list_records(
    q: str | None = None,
    auction_date_from: date | None = None,
    auction_date_to: date | None = None,
    mileage_min: int | None = None,
    mileage_max: int | None = None,
    score_min: float | None = None,
    auction_venue: list[str] | None = None,
    source: str | None = None,
    needs_review: bool | None = None,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    filters = RecordFilters(
        q=q,
        auction_date_from=auction_date_from,
        auction_date_to=auction_date_to,
        mileage_min=mileage_min,
        mileage_max=mileage_max,
        score_min=score_min,
        auction_venue=auction_venue,
        needs_review=needs_review,
    )

    query = select(AuctionRecord)
    if source:
        query = query.join(Document, AuctionRecord.document_id == Document.id)
        query = query.where(Document.source == source)
    query = apply_record_filters(query, filters)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))

    offset = (page - 1) * per_page
    result = await db.execute(
        query.order_by(AuctionRecord.created_at.desc()).offset(offset).limit(per_page)
    )
    items = result.scalars().all()
    return Page(items=items, page=page, per_page=per_page, total=total or 0)


@router.get("/{record_id}", response_model=RecordRead)
async def get_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(select(AuctionRecord).where(AuctionRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.patch("/{record_id}", response_model=RecordRead)
async def update_record(
    record_id: UUID,
    payload: RecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(select(AuctionRecord).where(AuctionRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(record, key, value)

    await db.commit()
    await db.refresh(record)
    return record
