import csv
from io import StringIO
from typing import Iterable

from app.models.record import AuctionRecord


CSV_FIELDS = [
    "id",
    "document_id",
    "auction_date",
    "auction_venue",
    "lot_no",
    "make_model",
    "model_code",
    "chassis_no",
    "year",
    "mileage_km",
    "score",
    "final_bid_yen",
    "needs_review",
]


def stream_csv(records: Iterable[AuctionRecord]):
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for record in records:
        writer.writerow({field: getattr(record, field) for field in CSV_FIELDS})
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
