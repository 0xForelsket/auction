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
from worker.ocr.parsing import (
    build_record_fields,
    merge_fields,
    parse_header,
    parse_header_cells,
    parse_sheet,
    parse_mileage,
)


P0_FIELDS = {"lot_no", "auction_date", "auction_venue", "score", "final_bid_yen"}
P0_FIELD_CONF_MAP = {"final_bid_yen": "final_bid"}
P0_HEADER_KEYS = {"lot_no", "auction_date", "auction_venue", "score"}


@celery_app.task(bind=True, max_retries=2, queue="extract", time_limit=120, soft_time_limit=90)
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

        try:
            header_tokens = [
                OCRToken(
                    text=token["text"],
                    confidence=float(token.get("confidence", 0.0)),
                    bbox=tuple(token.get("bbox", [0, 0, 0, 0])),
                )
                for token in ocr_data.get("header", {}).get("tokens", [])
            ]
            fallback_tokens = [
                OCRToken(
                    text=token["text"],
                    confidence=float(token.get("confidence", 0.0)),
                    bbox=tuple(token.get("bbox", [0, 0, 0, 0])),
                )
                for token in ocr_data.get("header", {}).get("fallback", {}).get("tokens", [])
            ]
            sheet_tokens = [
                OCRToken(
                    text=token["text"],
                    confidence=float(token.get("confidence", 0.0)),
                    bbox=tuple(token.get("bbox", [0, 0, 0, 0])),
                )
                for token in ocr_data.get("sheet", {}).get("tokens", [])
            ]

            header_fields_line = parse_header(header_tokens)
            header_fields = header_fields_line
            table_cells = ocr_data.get("header", {}).get("table_cells") or {}
            table_cell_count = int(ocr_data.get("header", {}).get("table_cell_count") or 0)
            if table_cells and table_cell_count >= 8:
                header_fields_table = parse_header_cells(table_cells)
                header_fields = merge_fields(header_fields_table, header_fields_line)

            if _missing_p0(header_fields) and fallback_tokens:
                header_fields_fallback = parse_header(fallback_tokens)
                header_fields = merge_fields(header_fields_fallback, header_fields_line)

            sheet_fields = parse_sheet(sheet_tokens)
            record_data = build_record_fields(header_fields, sheet_fields)

            full_text = " ".join([token.text for token in header_tokens + sheet_tokens])
            record_data["full_text"] = full_text

            evidence = {}
            sheet_mileage_km = None
            sheet_mileage_raw = None
            if "mileage" in sheet_fields and sheet_fields["mileage"].value:
                sheet_mileage_raw = str(sheet_fields["mileage"].value)
                sheet_mileage_km, _, _ = parse_mileage(sheet_mileage_raw)
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

            record.evidence = _with_evidence_meta(
                evidence,
                header_engine=ocr_data.get("header", {}).get("engine"),
                sheet_engine=ocr_data.get("sheet", {}).get("engine"),
                sheet_mileage_km=sheet_mileage_km,
                sheet_mileage_raw=sheet_mileage_raw,
            )
            record.overall_confidence = compute_overall_confidence(header_fields)

            doc.status = "validating"
            session.commit()
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)
            doc.retry_count = (doc.retry_count or 0) + 1
            session.commit()
            raise self.retry(exc=exc, countdown=120)

    from worker.tasks.validate import validate

    validate.delay(document_id)
    return {"status": "queued", "document_id": document_id}


def compute_overall_confidence(header_fields: dict) -> float | None:
    confidences = [field.confidence for field in header_fields.values() if field.confidence]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def evaluate_review_policy(
    record: AuctionRecord, evidence: dict
) -> tuple[bool, str | None]:
    missing = []
    for field in P0_FIELDS:
        if getattr(record, field) is None:
            missing.append(field)
    if missing:
        return True, f"Missing P0 fields: {', '.join(missing)}"

    low_conf = []
    for field in P0_FIELDS:
        if field == "final_bid_yen":
            conf = max(
                _field_confidence(evidence, "final_bid"),
                _field_confidence(evidence, "bid_start"),
            )
        else:
            header_key = P0_FIELD_CONF_MAP.get(field, field)
            conf = _field_confidence(evidence, header_key)
        if conf < 0.9:
            low_conf.append(field)
    if low_conf:
        return True, f"Low confidence P0 fields: {', '.join(low_conf)}"

    invalid = _validate_record_values(record)
    if invalid:
        return True, invalid

    meta = (evidence or {}).get("_meta", {})
    sheet_mileage_km = meta.get("sheet_mileage_km")
    if record.mileage_km and sheet_mileage_km:
        if abs(record.mileage_km - sheet_mileage_km) > 1000:
            return True, "Mileage discrepancy"
    elif record.mileage_km and not sheet_mileage_km:
        if record.mileage_inference_conf and record.mileage_inference_conf < 0.9:
            return True, "Mileage requires sheet confirmation"

    return False, None


def build_evidence(document_id: str, image, header_fields: dict, sheet_fields: dict) -> dict:
    evidence = {}
    for source, fields in ("header", header_fields), ("sheet", sheet_fields):
        for key, field in fields.items():
            entry = {
                "value": field.value,
                "confidence": field.confidence,
                "source": source,
            }
            if field.bbox is not None:
                crop_key = f"evidence/{document_id}/{source}_{key}.png"
                crop = crop_image(image, field.bbox)
                storage_client.upload_bytes(crop_key, encode_png(crop), "image/png")
                entry["bbox"] = list(field.bbox)
                entry["crop_path"] = crop_key
            evidence[key] = entry
    return evidence


def _missing_p0(fields: dict[str, object]) -> bool:
    if any(key not in fields or not getattr(fields[key], "value", None) for key in P0_HEADER_KEYS):
        return True
    has_bid = False
    for key in ("final_bid", "bid_start"):
        if key in fields and getattr(fields[key], "value", None):
            has_bid = True
            break
    return not has_bid


def _field_confidence(evidence: dict, field: str) -> float:
    entry = (evidence or {}).get(field) or {}
    try:
        return float(entry.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _validate_record_values(record: AuctionRecord) -> str | None:
    if record.auction_date:
        if record.auction_date.year < 1990:
            return "Invalid auction_date"
        if record.auction_date.year > datetime.now(timezone.utc).year + 1:
            return "Auction date too far in future"
    if record.final_bid_yen is not None:
        if record.final_bid_yen <= 0 or record.final_bid_yen > 1_000_000_000:
            return "Invalid final_bid_yen"
    if record.score_numeric is not None:
        if record.score_numeric < 0 or record.score_numeric > 6:
            return "Invalid score"
    if record.lot_no:
        if not any(ch.isdigit() for ch in record.lot_no):
            return "Invalid lot_no"
    return None


def _with_evidence_meta(
    evidence: dict,
    *,
    header_engine: str | None,
    sheet_engine: str | None,
    sheet_mileage_km: int | None,
    sheet_mileage_raw: str | None,
) -> dict:
    meta = {
        "header_engine": header_engine,
        "sheet_engine": sheet_engine,
        "sheet_mileage_km": sheet_mileage_km,
        "sheet_mileage_raw": sheet_mileage_raw,
    }
    payload = dict(evidence or {})
    payload["_meta"] = meta
    return payload
