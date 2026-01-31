from datetime import date
from typing import Iterable

from sqlalchemy import Select, func, or_

from app.models.record import AuctionRecord


class RecordFilters:
    def __init__(
        self,
        q: str | None = None,
        auction_date_from: date | None = None,
        auction_date_to: date | None = None,
        mileage_min: int | None = None,
        mileage_max: int | None = None,
        score_min: float | None = None,
        auction_venue: Iterable[str] | None = None,
        needs_review: bool | None = None,
    ) -> None:
        self.q = q
        self.auction_date_from = auction_date_from
        self.auction_date_to = auction_date_to
        self.mileage_min = mileage_min
        self.mileage_max = mileage_max
        self.score_min = score_min
        self.auction_venue = list(auction_venue) if auction_venue else None
        self.needs_review = needs_review


def apply_record_filters(query: Select, filters: RecordFilters) -> Select:
    if filters.q:
        ts_query = func.plainto_tsquery("english", filters.q)
        query = query.where(
            or_(
                AuctionRecord.fts_vector_en.op("@@")(ts_query),
                AuctionRecord.search_text.ilike(f"%{filters.q}%"),
            )
        )
    if filters.auction_date_from:
        query = query.where(AuctionRecord.auction_date >= filters.auction_date_from)
    if filters.auction_date_to:
        query = query.where(AuctionRecord.auction_date <= filters.auction_date_to)
    if filters.mileage_min is not None:
        query = query.where(AuctionRecord.mileage_km >= filters.mileage_min)
    if filters.mileage_max is not None:
        query = query.where(AuctionRecord.mileage_km <= filters.mileage_max)
    if filters.score_min is not None:
        query = query.where(AuctionRecord.score_numeric >= filters.score_min)
    if filters.auction_venue:
        query = query.where(AuctionRecord.auction_venue.in_(filters.auction_venue))
    if filters.needs_review is not None:
        query = query.where(AuctionRecord.needs_review == filters.needs_review)
    return query
