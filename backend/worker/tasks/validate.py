from datetime import datetime, timezone

from worker.celery_app import celery_app
from app.db.session_sync import get_session
from app.models.document import Document
from app.models.record import AuctionRecord
from worker.tasks.extract import evaluate_review_policy


@celery_app.task(bind=True, max_retries=2, queue="validate", time_limit=60, soft_time_limit=45)
def validate(self, document_id: str):
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            return {"status": "missing", "document_id": document_id}

        record = (
            session.query(AuctionRecord)
            .filter(AuctionRecord.document_id == doc.id)
            .one_or_none()
        )
        if not record:
            doc.status = "failed"
            doc.error_message = "Missing record for validation"
            session.commit()
            return {"status": "missing_record", "document_id": document_id}

        try:
            evidence = record.evidence or {}
            needs_review, reason = evaluate_review_policy(record, evidence)
            record.needs_review = needs_review
            record.review_reason = reason
            doc.status = "review" if needs_review else "done"
            doc.processing_completed_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)
            doc.retry_count = (doc.retry_count or 0) + 1
            session.commit()
            raise self.retry(exc=exc, countdown=60)

    return {"status": "done", "document_id": document_id}
