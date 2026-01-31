from datetime import datetime, timezone
from pathlib import Path

from worker.celery_app import celery_app
from app.db.session_sync import get_session
from app.models.document import Document
from app.services.storage import storage_client


@celery_app.task(bind=True, max_retries=3)
def preprocess(self, document_id: str):
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            return {"status": "missing", "document_id": document_id}

        doc.status = "preprocessing"
        doc.processing_started_at = doc.processing_started_at or datetime.now(timezone.utc)
        session.commit()

        try:
            source_key = doc.original_path
            if not source_key:
                raise ValueError("Missing original_path")
            ext = Path(source_key).suffix or ".jpg"
            dest_key = f"preprocessed/{doc.id}{ext}"
            storage_client.copy_object(source_key, dest_key)
            doc.preprocessed_path = dest_key
            doc.status = "ocr"
            session.commit()
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)
            doc.retry_count = (doc.retry_count or 0) + 1
            session.commit()
            raise self.retry(exc=exc, countdown=60)

    from worker.tasks.ocr import ocr

    ocr.delay(document_id)
    return {"status": "queued", "document_id": document_id}
