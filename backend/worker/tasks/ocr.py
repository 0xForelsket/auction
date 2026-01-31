import json

from worker.celery_app import celery_app
from app.db.session_sync import get_session
from app.models.document import Document
from app.services.storage import storage_client


@celery_app.task(bind=True, max_retries=2)
def ocr(self, document_id: str):
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            return {"status": "missing", "document_id": document_id}

        doc.status = "ocr"
        session.commit()

        try:
            ocr_results = {"header": {}, "sheet": {}, "note": "OCR not configured"}
            key = f"ocr_raw/{document_id}.json"
            storage_client.upload_bytes(key, json.dumps(ocr_results).encode("utf-8"), "application/json")
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)
            doc.retry_count = (doc.retry_count or 0) + 1
            session.commit()
            raise self.retry(exc=exc, countdown=120)

    from worker.tasks.extract import extract

    extract.delay(document_id)
    return {"status": "queued", "document_id": document_id}
