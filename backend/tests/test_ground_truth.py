import csv
import os
import re
from datetime import date
from pathlib import Path

import pytest


RUN_GROUND_TRUTH = os.getenv("RUN_GROUND_TRUTH") == "1"
if not RUN_GROUND_TRUTH:
    pytest.skip(
        "Set RUN_GROUND_TRUTH=1 to run OCR ground-truth validation.",
        allow_module_level=True,
    )

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "1")
os.environ.setdefault("OCR_DEVICE", "gpu")

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "example_images" / "ground_truth.csv"
IMAGES_DIR = ROOT / "example_images"

from worker.ocr import decode_image, detect_rois, extract_header, extract_sheet
from worker.ocr.parsing import (
    build_record_fields,
    merge_fields,
    parse_header,
    parse_header_cells,
    parse_sheet,
)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        year, month, day = value.split("-")
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else None


def _norm_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value))


def _norm_alnum(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"[^0-9A-Za-z]", "", str(value).upper())


def _result_norm(value: str | None) -> str:
    if value is None:
        return ""
    if "落札" in value:
        return "sold"
    if "流札" in value:
        return "unsold"
    return value


def _load_rows() -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing ground truth CSV: {CSV_PATH}")
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _build_record(image_path: Path) -> dict:
    image = decode_image(image_path.read_bytes())
    rois = detect_rois(image)
    header = extract_header(image, rois.header_bbox)
    sheet = extract_sheet(image, rois.sheet_bbox)

    header_fields_line = parse_header(header.primary.tokens)
    header_fields = header_fields_line
    if header.table_cells and header.table_cell_count >= 8:
        header_fields_table = parse_header_cells(header.table_cells)
        header_fields = merge_fields(header_fields_table, header_fields_line)

    sheet_fields = parse_sheet(sheet.tokens)
    return build_record_fields(header_fields, sheet_fields)


def _expect_in(actual: str, expected: str) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    return expected in actual or actual in expected


@pytest.mark.parametrize("row", _load_rows(), ids=lambda row: row.get("filename", ""))
def test_ground_truth_row(row: dict[str, str]) -> None:
    filename = row.get("filename")
    assert filename, "Missing filename in ground truth row"

    image_path = IMAGES_DIR / filename
    assert image_path.exists(), f"Missing image: {image_path}"

    record = _build_record(image_path)

    mismatches: list[str] = []

    expected_date = _parse_date(row.get("auction_date"))
    if expected_date and record.get("auction_date") != expected_date:
        mismatches.append(f"auction_date expected {expected_date} got {record.get('auction_date')}")

    expected_venue = _norm_text(row.get("auction_venue"))
    actual_venue = _norm_text(record.get("auction_venue"))
    if expected_venue and not _expect_in(actual_venue, expected_venue):
        mismatches.append(f"auction_venue expected {row.get('auction_venue')} got {record.get('auction_venue')}")

    expected_round = _norm_text(row.get("auction_venue_round"))
    actual_round = _norm_text(record.get("auction_venue_round"))
    if expected_round and not _expect_in(actual_round, expected_round):
        mismatches.append(
            f"auction_venue_round expected {row.get('auction_venue_round')} got {record.get('auction_venue_round')}"
        )

    expected_lot = _norm_alnum(row.get("lot_no"))
    actual_lot = _norm_alnum(record.get("lot_no"))
    if expected_lot and expected_lot != actual_lot:
        mismatches.append(f"lot_no expected {row.get('lot_no')} got {record.get('lot_no')}")

    expected_year = _norm_text(row.get("model_year_reiwa"))
    actual_year = _norm_text(record.get("model_year_reiwa"))
    if expected_year and expected_year != actual_year:
        mismatches.append(
            f"model_year_reiwa expected {row.get('model_year_reiwa')} got {record.get('model_year_reiwa')}"
        )

    expected_make_model = _norm_text(row.get("make_model"))
    actual_make_model = _norm_text(record.get("make_model"))
    if expected_make_model and not _expect_in(actual_make_model, expected_make_model):
        mismatches.append(
            f"make_model expected {row.get('make_model')} got {record.get('make_model')}"
        )

    expected_grade = _norm_text(row.get("grade"))
    actual_grade = _norm_text(record.get("grade"))
    if expected_grade and not _expect_in(actual_grade, expected_grade):
        mismatches.append(f"grade expected {row.get('grade')} got {record.get('grade')}")

    expected_shift = _norm_text(row.get("shift"))
    actual_shift = _norm_text(record.get("transmission"))
    if expected_shift and expected_shift != actual_shift:
        mismatches.append(f"shift expected {row.get('shift')} got {record.get('transmission')}")

    expected_engine = _parse_int(row.get("engine_cc"))
    actual_engine = record.get("engine_cc")
    if expected_engine is not None and expected_engine != actual_engine:
        mismatches.append(f"engine_cc expected {expected_engine} got {actual_engine}")

    expected_mileage = _parse_int(row.get("mileage_km"))
    actual_mileage = record.get("mileage_km")
    if expected_mileage is not None:
        if actual_mileage is None or abs(actual_mileage - expected_mileage) > 1000:
            mismatches.append(
                f"mileage_km expected {expected_mileage} got {actual_mileage}"
            )

    expected_inspection = _norm_text(row.get("inspection"))
    actual_inspection = _norm_text(record.get("inspection_expiry_raw"))
    if expected_inspection and not _expect_in(actual_inspection, expected_inspection):
        mismatches.append(
            f"inspection expected {row.get('inspection')} got {record.get('inspection_expiry_raw')}"
        )

    expected_color = _norm_text(row.get("color"))
    actual_color = _norm_text(record.get("color"))
    if expected_color and not _expect_in(actual_color, expected_color):
        mismatches.append(f"color expected {row.get('color')} got {record.get('color')}")

    expected_model_code = _norm_alnum(row.get("model_code"))
    actual_model_code = _norm_alnum(record.get("model_code"))
    if expected_model_code and expected_model_code != actual_model_code:
        mismatches.append(
            f"model_code expected {row.get('model_code')} got {record.get('model_code')}"
        )

    expected_result = _result_norm(row.get("result"))
    actual_result = _result_norm(record.get("result"))
    if expected_result and expected_result != actual_result:
        mismatches.append(f"result expected {row.get('result')} got {record.get('result')}")

    expected_final = _parse_int(row.get("final_bid_yen"))
    actual_final = record.get("final_bid_yen")
    if expected_final is not None and expected_final != actual_final:
        mismatches.append(f"final_bid_yen expected {expected_final} got {actual_final}")

    expected_start = _parse_int(row.get("starting_bid_yen"))
    actual_start = record.get("starting_bid_yen")
    if expected_start is not None and expected_start != actual_start:
        mismatches.append(f"starting_bid_yen expected {expected_start} got {actual_start}")

    expected_score = _norm_text(row.get("score"))
    actual_score = _norm_text(record.get("score"))
    if expected_score and expected_score != actual_score:
        mismatches.append(f"score expected {row.get('score')} got {record.get('score')}")

    expected_chassis = _norm_alnum(row.get("chassis_no"))
    actual_chassis = _norm_alnum(record.get("chassis_no"))
    if expected_chassis and expected_chassis != actual_chassis:
        mismatches.append(
            f"chassis_no expected {row.get('chassis_no')} got {record.get('chassis_no')}"
        )

    expected_notes = _norm_text(row.get("notes_text"))
    actual_notes = _norm_text(record.get("notes_text"))
    if expected_notes and not _expect_in(actual_notes, expected_notes):
        mismatches.append(
            f"notes_text expected {row.get('notes_text')} got {record.get('notes_text')}"
        )

    if mismatches:
        pytest.fail("\n".join(mismatches))
