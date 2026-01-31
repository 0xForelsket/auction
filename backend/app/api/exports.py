from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db import get_db
from app.models.document import Document
from app.models.record import AuctionRecord
from app.services.export import stream_csv
from app.services.search import RecordFilters, apply_record_filters

router = APIRouter()


@router.get("/records.csv")
async def export_records(
    q: str | None = None,
    auction_date_from: date | None = None,
    auction_date_to: date | None = None,
    mileage_min: int | None = None,
    mileage_max: int | None = None,
    score_min: float | None = None,
    auction_venue: list[str] | None = None,
    source: str | None = None,
    needs_review: bool | None = None,
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
    result = await db.execute(query.order_by(AuctionRecord.created_at.desc()))
    records = result.scalars().all()

    headers = {"Content-Disposition": "attachment; filename=records.csv"}
    return StreamingResponse(stream_csv(records), media_type="text/csv", headers=headers)
