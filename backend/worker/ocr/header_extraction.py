from __future__ import annotations

from dataclasses import dataclass
import html as html_lib
import re

from worker.ocr.image_utils import OCRToken, crop_image
from worker.ocr.ocr_engine import OCRResult, run_ocr
from worker.ocr.vl_engine import run_vl_ocr
from worker.ocr.preprocessing import binarize_image


@dataclass
class HeaderExtraction:
    primary: OCRResult
    fallback: OCRResult | None
    table_cells: dict[str, str] | None
    table_cell_count: int
    method: str


def extract_header(image, header_bbox) -> HeaderExtraction:
    crop = crop_image(image, header_bbox)

    primary = run_vl_ocr(crop)
    table_cells = {}
    table_cell_count = 0
    method = "vl"
    if primary.meta:
        table_cells = primary.meta.get("table_cells") or {}
        table_cell_count = int(primary.meta.get("table_cell_count") or 0)
    if not table_cells:
        table_cells, table_cell_count = _extract_table_cells(crop)
        if table_cells:
            method = "ppstructure"
    fallback = None
    if not primary.tokens:
        try:
            fallback = run_ocr(
                binarize_image(crop),
                lang="japan",
                engine_preference=["paddle", "tesseract"],
            )
        except Exception:
            fallback = None

    primary = _offset_result(primary, header_bbox)
    if fallback:
        fallback = _offset_result(fallback, header_bbox)

    return HeaderExtraction(
        primary=primary,
        fallback=fallback,
        table_cells=table_cells or None,
        table_cell_count=table_cell_count,
        method=method,
    )


def _offset_result(result: OCRResult, header_bbox) -> OCRResult:
    offset_tokens = []
    x0, y0, _, _ = header_bbox
    for token in result.tokens:
        bx0, by0, bx1, by1 = token.bbox
        offset_tokens.append(
            OCRToken(
                text=token.text,
                confidence=token.confidence,
                bbox=(bx0 + x0, by0 + y0, bx1 + x0, by1 + y0),
            )
        )
    return OCRResult(engine=result.engine, tokens=offset_tokens, meta=result.meta)


def _extract_table_cells(image) -> tuple[dict[str, str], int]:
    # Disabled by default: PPStructureV3 is heavyweight and not required for VL-first OCR.
    return {}, 0


def _parse_table_html(html_text: str) -> list[list[str]]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, flags=re.IGNORECASE | re.DOTALL)
    parsed_rows: list[list[str]] = []
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.IGNORECASE | re.DOTALL)
        cleaned = []
        for cell in cells:
            text = re.sub(r"<[^>]+>", "", cell)
            text = html_lib.unescape(text).strip()
            cleaned.append(text)
        if cleaned:
            parsed_rows.append(cleaned)
    return parsed_rows


def _cells_from_rows(rows: list[list[str]]) -> tuple[dict[str, str], int]:
    cells: dict[str, str] = {}
    count = 0
    for row in rows:
        count += len(row)
        if len(row) < 2:
            continue
        for idx in range(0, len(row) - 1, 2):
            label = row[idx].strip()
            value = row[idx + 1].strip()
            if label:
                cells[label] = value
    return cells, count
