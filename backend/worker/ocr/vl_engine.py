from __future__ import annotations

import os
import html as html_lib
import re
from typing import Iterable

import cv2
import numpy as np

from worker.ocr.image_utils import OCRToken, to_int_bbox
from worker.ocr.ocr_engine import OCRResult, get_paddle_device

_VL_INSTANCE = None


def _patch_paddle_tensor_int() -> None:
    try:
        import paddle
    except Exception:
        return

    tensor_cls = getattr(paddle, "Tensor", None)
    if tensor_cls is None:
        return

    current_int = getattr(tensor_cls, "__int__", None)
    if current_int is None or getattr(current_int, "_auction_patch", False):
        return

    original_int = current_int

    def _patched_int(self):
        try:
            return original_int(self)
        except Exception:
            try:
                arr = self.numpy()
            except Exception:
                raise
            if getattr(arr, "size", 0) == 1:
                return int(arr.reshape(-1)[0])
            raise

    _patched_int._auction_patch = True
    tensor_cls.__int__ = _patched_int


def _get_vl_instance():
    global _VL_INSTANCE
    if _VL_INSTANCE is None:
        try:
            from paddleocr import PaddleOCRVL
        except Exception as exc:  # pragma: no cover - required dependency
            raise RuntimeError("PaddleOCRVL dependency missing") from exc
        _VL_INSTANCE = PaddleOCRVL(
            pipeline_version="v1.5",
            device=get_paddle_device(),
        )
    return _VL_INSTANCE


def run_vl_ocr(image: np.ndarray) -> OCRResult:
    _patch_paddle_tensor_int()
    vl = _get_vl_instance()
    predict_kwargs = {"use_queues": False, "use_ocr_for_image_block": True}

    max_new_tokens = os.getenv("PADDLEOCR_VL_MAX_NEW_TOKENS")
    if max_new_tokens:
        try:
            predict_kwargs["max_new_tokens"] = int(max_new_tokens)
        except ValueError:
            pass
    else:
        predict_kwargs["max_new_tokens"] = 128

    min_pixels = os.getenv("PADDLEOCR_VL_MIN_PIXELS")
    if min_pixels:
        try:
            predict_kwargs["min_pixels"] = int(min_pixels)
        except ValueError:
            pass

    max_pixels = os.getenv("PADDLEOCR_VL_MAX_PIXELS")
    if max_pixels:
        try:
            predict_kwargs["max_pixels"] = int(max_pixels)
        except ValueError:
            pass
    else:
        predict_kwargs["max_pixels"] = 400000

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    try:
        results = vl.predict([rgb_image], **predict_kwargs)
    except Exception as exc:
        return OCRResult(
            engine="paddleocr-vl-1.5",
            tokens=[],
            meta={"pipeline": "PaddleOCR-VL-1.5", "block_count": 0, "error": str(exc)},
        )

    if not results:
        return OCRResult(
            engine="paddleocr-vl-1.5",
            tokens=[],
            meta={"pipeline": "PaddleOCR-VL-1.5", "block_count": 0},
        )

    result = results[0]
    tokens, table_meta = _tokens_from_vl_result(result)
    block_count = _vl_block_count(result)
    meta = {"pipeline": "PaddleOCR-VL-1.5", "block_count": block_count}
    if table_meta:
        meta.update(table_meta)
    return OCRResult(
        engine="paddleocr-vl-1.5",
        tokens=tokens,
        meta=meta,
    )


def _vl_block_count(result) -> int:
    if hasattr(result, "get"):
        blocks = result.get("parsing_res_list") or []
    else:
        blocks = getattr(result, "parsing_res_list", None) or []
    return len(blocks)


def _tokens_from_vl_result(result) -> tuple[list[OCRToken], dict]:
    if hasattr(result, "get"):
        blocks = result.get("parsing_res_list") or []
    else:
        blocks = getattr(result, "parsing_res_list", None) or []
    tokens: list[OCRToken] = []
    table_cells: dict[str, str] = {}
    table_cell_count = 0
    for block in blocks:
        if isinstance(block, dict):
            label = block.get("block_label") or block.get("label")
            content = block.get("block_content") or block.get("content")
            bbox = block.get("block_bbox") or block.get("bbox")
            polygon = block.get("block_polygon_points") or block.get("polygon_points")
        else:
            label = getattr(block, "label", None)
            content = getattr(block, "content", None)
            bbox = getattr(block, "bbox", None)
            polygon = getattr(block, "polygon_points", None)

        if label in {"chart", "header_image", "footer_image"}:
            continue
        if label == "image" and not content:
            continue
        if not content:
            continue

        content_text = str(content)
        bbox_tuple = _coerce_bbox(bbox, polygon)
        if isinstance(content, str) and _looks_like_table(content_text):
            rows = _parse_table_html(content_text)
            cells, cell_count, header_value_mode = _cells_from_rows(rows)
            if cells:
                table_cells.update(cells)
            table_cell_count += cell_count
            if bbox_tuple is not None and rows:
                tokens.extend(
                    _tokens_from_table_rows(rows, bbox_tuple, header_value_mode)
                )
            continue

        if bbox_tuple is None:
            continue
        x0, y0, x1, y1 = bbox_tuple
        width = max(x1 - x0, 1)
        for line in content_text.splitlines():
            line = line.strip()
            if not line:
                continue
            normalized = line.replace("　", " ")
            parts = [part for part in normalized.split() if part]
            if len(parts) > 1:
                step = width / len(parts)
                for idx, part in enumerate(parts):
                    part_x0 = int(x0 + idx * step)
                    part_x1 = int(x0 + (idx + 1) * step)
                    tokens.append(
                        OCRToken(
                            text=part,
                            confidence=0.85,
                            bbox=(part_x0, y0, part_x1, y1),
                        )
                    )
            else:
                tokens.append(OCRToken(text=line, confidence=0.85, bbox=bbox_tuple))
    meta: dict[str, object] = {}
    if table_cells:
        meta["table_cells"] = table_cells
    if table_cell_count:
        meta["table_cell_count"] = table_cell_count
    return tokens, meta


_LABEL_HINTS = (
    "開催日",
    "出品番号",
    "会場",
    "開催回",
    "年式",
    "車種名",
    "グレード",
    "シフト",
    "排気量",
    "走行",
    "車検",
    "色",
    "型式",
    "セリ結果",
    "応札",
    "スタート",
    "評価点",
)


def _looks_like_table(content: str) -> bool:
    return "<table" in content.lower()


def _parse_table_html(html_text: str) -> list[list[str]]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, flags=re.IGNORECASE | re.DOTALL)
    parsed_rows: list[list[str]] = []
    for row in rows:
        cells = re.findall(
            r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.IGNORECASE | re.DOTALL
        )
        cleaned = []
        for cell in cells:
            text = re.sub(r"<[^>]+>", "", cell)
            text = html_lib.unescape(text).strip()
            cleaned.append(text)
        if cleaned:
            parsed_rows.append(cleaned)
    return parsed_rows


def _row_has_label(row: list[str]) -> bool:
    joined = "".join(row)
    return any(hint in joined for hint in _LABEL_HINTS)


def _cells_from_rows(rows: list[list[str]]) -> tuple[dict[str, str], int, bool]:
    cells: dict[str, str] = {}
    count = 0
    if len(rows) >= 2 and _row_has_label(rows[0]):
        header = rows[0]
        values = rows[1]
        count = len(header) + len(values)
        for label, value in zip(header, values):
            label = label.strip()
            value = value.strip()
            if label:
                cells[label] = value
        return cells, count, True

    for row in rows:
        count += len(row)
        if len(row) < 2:
            continue
        for idx in range(0, len(row) - 1, 2):
            label = row[idx].strip()
            value = row[idx + 1].strip()
            if label:
                cells[label] = value
    return cells, count, False


def _tokens_from_table_rows(
    rows: list[list[str]], bbox: tuple[int, int, int, int], header_value_mode: bool
) -> list[OCRToken]:
    tokens: list[OCRToken] = []
    if not rows:
        return tokens
    x0, y0, x1, y1 = bbox
    row_count = max(len(rows), 1)
    row_height = (y1 - y0) / row_count

    if header_value_mode and len(rows) >= 2:
        header = rows[0]
        values = rows[1]
        col_count = max(len(header), len(values), 1)
        col_width = (x1 - x0) / col_count
        for idx in range(col_count):
            label = header[idx].strip() if idx < len(header) else ""
            value = values[idx].strip() if idx < len(values) else ""
            combined = f"{label} {value}".strip()
            if not combined:
                continue
            cx0 = int(x0 + idx * col_width)
            cx1 = int(x0 + (idx + 1) * col_width)
            cy0 = int(y0)
            cy1 = int(y0 + min(2, row_count) * row_height)
            tokens.append(
                OCRToken(text=combined, confidence=0.85, bbox=(cx0, cy0, cx1, cy1))
            )
        return tokens

    for row_index, row in enumerate(rows):
        cy0 = int(y0 + row_index * row_height)
        cy1 = int(y0 + (row_index + 1) * row_height)
        row_cols = max(len(row), 1)
        row_col_width = (x1 - x0) / row_cols
        for col_index, cell in enumerate(row):
            text = cell.strip()
            if not text:
                continue
            cx0 = int(x0 + col_index * row_col_width)
            cx1 = int(x0 + (col_index + 1) * row_col_width)
            tokens.append(OCRToken(text=text, confidence=0.85, bbox=(cx0, cy0, cx1, cy1)))
    return tokens


def _coerce_bbox(
    bbox: list | tuple | None, polygon: Iterable[Iterable[float]] | None
) -> tuple[int, int, int, int] | None:
    if bbox and len(bbox) == 4:
        return (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
    if polygon:
        try:
            return to_int_bbox(polygon)
        except Exception:
            return None
    return None
