from datetime import datetime, timedelta, timezone

from worker.celery_app import celery_app
from app.db.session_sync import get_session
from app.models.document import Document
from app.models.record import AuctionRecord


WATCHDOG_THRESHOLDS_SECONDS = {
    "preprocessing": 120,
    "ocr": 480,
    "extracting": 120,
    "validating": 120,
}


@celery_app.task(bind=True, queue="maintenance", time_limit=60, soft_time_limit=45)
def watchdog_stuck_documents(self):
    now = datetime.now(timezone.utc)
    with get_session() as session:
        for status, threshold in WATCHDOG_THRESHOLDS_SECONDS.items():
            cutoff = now - timedelta(seconds=threshold)
            docs = (
                session.query(Document)
                .filter(Document.status == status)
                .filter(Document.processing_started_at.isnot(None))
                .filter(Document.processing_started_at < cutoff)
                .all()
            )
            for doc in docs:
                doc.status = "review"
                doc.error_message = f"Stuck in {status}"
                doc.processing_completed_at = now
                record = (
                    session.query(AuctionRecord)
                    .filter(AuctionRecord.document_id == doc.id)
                    .one_or_none()
                )
                if record:
                    record.needs_review = True
                    record.review_reason = f"Stuck in {status}"
        session.commit()

    return {"status": "ok"}
