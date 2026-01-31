import json

from worker.celery_app import celery_app
from app.db.session_sync import get_session
from app.models.document import Document
from app.services.storage import storage_client
from worker.ocr import decode_image, detect_rois, extract_header, extract_sheet


@celery_app.task(bind=True, max_retries=2, queue="gpu_ocr", time_limit=480, soft_time_limit=420)
def ocr(self, document_id: str):
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            return {"status": "missing", "document_id": document_id}

        doc.status = "ocr"
        session.commit()

        try:
            if not doc.preprocessed_path:
                raise ValueError("Missing preprocessed_path")
            image_bytes = storage_client.download_bytes(doc.preprocessed_path)
            image = decode_image(image_bytes)

            if not doc.roi:
                rois = detect_rois(image)
                header_bbox = rois.header_bbox
                sheet_bbox = rois.sheet_bbox
            else:
                header_bbox = tuple(doc.roi.get("header_bbox"))
                sheet_bbox = tuple(doc.roi.get("sheet_bbox"))

            header_result = extract_header(image, header_bbox)
            sheet_result = extract_sheet(image, sheet_bbox)
            doc.model_version = doc.model_version or header_result.primary.engine

            ocr_results = {
                "header": {
                    "engine": header_result.primary.engine,
                    "tokens": [
                        {
                            "text": token.text,
                            "confidence": token.confidence,
                            "bbox": list(token.bbox),
                        }
                        for token in header_result.primary.tokens
                    ],
                    "bbox": list(header_bbox),
                    "table_cells": header_result.table_cells,
                    "table_cell_count": header_result.table_cell_count,
                    "method": header_result.method,
                },
                "sheet": {
                    "engine": sheet_result.engine,
                    "meta": sheet_result.meta,
                    "tokens": [
                        {
                            "text": token.text,
                            "confidence": token.confidence,
                            "bbox": list(token.bbox),
                        }
                        for token in sheet_result.tokens
                    ],
                    "bbox": list(sheet_bbox),
                },
            }
            if header_result.fallback:
                ocr_results["header"]["fallback"] = {
                    "engine": header_result.fallback.engine,
                    "tokens": [
                        {
                            "text": token.text,
                            "confidence": token.confidence,
                            "bbox": list(token.bbox),
                        }
                        for token in header_result.fallback.tokens
                    ],
                }

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
