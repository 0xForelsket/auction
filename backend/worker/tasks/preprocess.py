from datetime import datetime, timezone

from worker.celery_app import celery_app
from app.config import settings
from app.db.session_sync import get_session
from app.models.document import Document
from app.services.storage import storage_client
from worker.ocr import decode_image, detect_rois, encode_png, preprocess_auction_image


@celery_app.task(bind=True, max_retries=3, queue="cpu_preprocess", time_limit=120, soft_time_limit=90)
def preprocess(self, document_id: str):
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            return {"status": "missing", "document_id": document_id}

        doc.status = "preprocessing"
        doc.processing_started_at = doc.processing_started_at or datetime.now(timezone.utc)
        doc.pipeline_version = doc.pipeline_version or settings.PIPELINE_VERSION
        session.commit()

        try:
            source_key = doc.original_path
            if not source_key:
                raise ValueError("Missing original_path")

            image_bytes = storage_client.download_bytes(source_key)
            image = decode_image(image_bytes)
            processed = preprocess_auction_image(image)

            rois = detect_rois(processed)
            doc.roi = {
                "header_bbox": list(rois.header_bbox),
                "sheet_bbox": list(rois.sheet_bbox),
                "photos_bbox": list(rois.photos_bbox) if rois.photos_bbox else None,
                "roi_version": rois.roi_version,
            }

            preprocessed_key = f"preprocessed/{doc.id}.png"
            storage_client.upload_bytes(preprocessed_key, encode_png(processed), "image/png")
            doc.preprocessed_path = preprocessed_key
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
