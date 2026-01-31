from datetime import datetime, timezone

from worker.celery_app import celery_app
from app.db.session_sync import get_session
from app.models.document import Document
from app.models.record import AuctionRecord


@celery_app.task(bind=True, max_retries=2)
def extract(self, document_id: str):
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            return {"status": "missing", "document_id": document_id}

        doc.status = "extracting"
        session.commit()

        try:
            record = (
                session.query(AuctionRecord)
                .filter(AuctionRecord.document_id == doc.id)
                .one_or_none()
            )
            if not record:
                record = AuctionRecord(
                    document_id=doc.id,
                    needs_review=True,
                    review_reason="OCR not configured",
                )
                session.add(record)
            else:
                record.needs_review = True
                record.review_reason = "OCR not configured"

            doc.status = "review" if record.needs_review else "done"
            doc.processing_completed_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)
            doc.retry_count = (doc.retry_count or 0) + 1
            session.commit()
            raise self.retry(exc=exc, countdown=120)

    return {"status": "done", "document_id": document_id}
