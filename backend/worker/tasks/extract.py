from __future__ import annotations

import json
from datetime import datetime, timezone

from worker.celery_app import celery_app
from app.db.session_sync import get_session
from app.models.document import Document
from app.models.record import AuctionRecord
from app.services.storage import storage_client
from worker.ocr import OCRToken, decode_image, encode_png
from worker.ocr.image_utils import crop_image
from worker.ocr.parsing import build_record_fields, parse_header, parse_sheet


P0_FIELDS = {"lot_no", "auction_date", "auction_venue", "score", "final_bid_yen"}
P0_FIELD_CONF_MAP = {"final_bid_yen": "bid_start"}


@celery_app.task(bind=True, max_retries=2)
def extract(self, document_id: str):
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc:
            return {"status": "missing", "document_id": document_id}

        doc.status = "extracting"
        session.commit()

        try:
            ocr_key = f"ocr_raw/{document_id}.json"
            ocr_bytes = storage_client.download_bytes(ocr_key)
            ocr_data = json.loads(ocr_bytes.decode("utf-8"))
        except Exception:
            ocr_data = {"header": {"tokens": []}, "sheet": {"tokens": []}}

        header_tokens = [
            OCRToken(
                text=token["text"],
                confidence=float(token.get("confidence", 0.0)),
                bbox=tuple(token.get("bbox", [0, 0, 0, 0])),
            )
            for token in ocr_data.get("header", {}).get("tokens", [])
        ]
        sheet_tokens = [
            OCRToken(
                text=token["text"],
                confidence=float(token.get("confidence", 0.0)),
                bbox=tuple(token.get("bbox", [0, 0, 0, 0])),
            )
            for token in ocr_data.get("sheet", {}).get("tokens", [])
        ]

        header_fields = parse_header(header_tokens)
        sheet_fields = parse_sheet(sheet_tokens)
        record_data = build_record_fields(header_fields, sheet_fields)

        full_text = " ".join([token.text for token in header_tokens + sheet_tokens])
        record_data["full_text"] = full_text

        evidence = {}
        try:
            if doc.preprocessed_path:
                image_bytes = storage_client.download_bytes(doc.preprocessed_path)
                image = decode_image(image_bytes)
                evidence = build_evidence(document_id, image, header_fields, sheet_fields)
        except Exception:
            evidence = {}

        record = (
            session.query(AuctionRecord)
            .filter(AuctionRecord.document_id == doc.id)
            .one_or_none()
        )
        if not record:
            record = AuctionRecord(document_id=doc.id)
            session.add(record)

        for key, value in record_data.items():
            setattr(record, key, value)

        record.evidence = evidence
        record.overall_confidence = compute_overall_confidence(header_fields)

        needs_review, reason, mileage_conf = evaluate_review_policy(
            record, header_fields, sheet_fields
        )
        record.needs_review = needs_review
        record.review_reason = reason
        record.mileage_inference_conf = mileage_conf

        doc.status = "review" if needs_review else "done"
        doc.processing_completed_at = datetime.now(timezone.utc)
        session.commit()

    return {"status": "done", "document_id": document_id}


def compute_overall_confidence(header_fields: dict) -> float | None:
    confidences = [field.confidence for field in header_fields.values() if field.confidence]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def evaluate_review_policy(
    record: AuctionRecord, header_fields: dict, sheet_fields: dict
) -> tuple[bool, str | None, float | None]:
    missing = []
    for field in P0_FIELDS:
        if getattr(record, field) is None:
            missing.append(field)
    if missing:
        return True, f"Missing P0 fields: {', '.join(missing)}", None

    low_conf = []
    for field in P0_FIELDS:
        header_key = P0_FIELD_CONF_MAP.get(field, field)
        header_field = header_fields.get(header_key)
        if header_field and header_field.confidence < 0.9:
            low_conf.append(field)
    if low_conf:
        return True, f"Low confidence P0 fields: {', '.join(low_conf)}", None

    header_mileage = record.mileage_km
    sheet_mileage = None
    if "mileage" in sheet_fields:
        sheet_value = sheet_fields["mileage"].value
        if sheet_value:
            try:
                sheet_mileage = int("".join([c for c in sheet_value if c.isdigit()]))
            except ValueError:
                sheet_mileage = None

    if header_mileage and not sheet_mileage:
        return True, "Mileage requires sheet confirmation", 0.5
    if header_mileage and sheet_mileage:
        if abs(header_mileage - sheet_mileage) > 500:
            return True, "Mileage discrepancy", 0.4
        return False, None, 0.9

    if header_mileage:
        return False, None, 0.6

    return False, None, None


def build_evidence(document_id: str, image, header_fields: dict, sheet_fields: dict) -> dict:
    evidence = {}
    for source, fields in ("header", header_fields), ("sheet", sheet_fields):
        for key, field in fields.items():
            if field.bbox is None:
                continue
            crop_key = f"evidence/{document_id}/{source}_{key}.png"
            crop = crop_image(image, field.bbox)
            storage_client.upload_bytes(crop_key, encode_png(crop), "image/png")
            evidence[key] = {
                "value": field.value,
                "confidence": field.confidence,
                "bbox": list(field.bbox),
                "crop_path": crop_key,
                "source": source,
            }
    return evidence
