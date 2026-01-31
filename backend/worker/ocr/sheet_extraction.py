from __future__ import annotations

import cv2
import numpy as np

from worker.ocr.image_utils import OCRToken, crop_image
from worker.ocr.ocr_engine import OCRResult, run_ocr


MIN_SHEET_TOKENS = 10
_VL_INSTANCE = None


def extract_sheet(image, sheet_bbox) -> OCRResult:
    crop = crop_image(image, sheet_bbox)

    vl_tokens, vl_meta = _run_paddle_vl(crop)
    best_result = OCRResult(engine="paddleocr-vl-1.5", tokens=vl_tokens, meta=vl_meta)

    if len(vl_tokens) < MIN_SHEET_TOKENS:
        best_result, best_rotation, tesseract_used = _run_with_fallbacks(crop)
        if best_rotation:
            tokens = _map_tokens_from_rotated(
                best_result.tokens, best_rotation, crop.shape[:2]
            )
            meta = dict(best_result.meta or {})
            meta.update(
                {
                    "rotation": best_rotation,
                    "fallback": "line_ocr",
                    "vl_tokens": len(vl_tokens),
                    "vl_engine": "paddleocr-vl-1.5",
                }
            )
            best_result = OCRResult(
                engine=best_result.engine,
                tokens=tokens,
                meta=meta,
            )
        else:
            meta = dict(best_result.meta or {})
            meta.update(
                {
                    "fallback": "line_ocr",
                    "vl_tokens": len(vl_tokens),
                    "vl_engine": "paddleocr-vl-1.5",
                }
            )
            if tesseract_used:
                meta["fallback_engine"] = "tesseract"
            best_result = OCRResult(
                engine=best_result.engine,
                tokens=best_result.tokens,
                meta=meta,
            )

    offset_tokens = []
    x0, y0, _, _ = sheet_bbox
    for token in best_result.tokens:
        bx0, by0, bx1, by1 = token.bbox
        offset_tokens.append(
            OCRToken(
                text=token.text,
                confidence=token.confidence,
                bbox=(bx0 + x0, by0 + y0, bx1 + x0, by1 + y0),
            )
        )
    meta = best_result.meta or {}
    meta["token_count"] = len(offset_tokens)
    return OCRResult(engine=best_result.engine, tokens=offset_tokens, meta=meta)

def _run_with_fallbacks(image: np.ndarray) -> tuple[OCRResult, int, bool]:
    best, best_rotation = _run_with_rotations(image)
    tesseract_used = False
    if len(best.tokens) < MIN_SHEET_TOKENS:
        tesseract_result = run_ocr(image, lang="japan", engine_preference=["tesseract"])
        if len(tesseract_result.tokens) > len(best.tokens):
            best = tesseract_result
            best_rotation = 0
            tesseract_used = True
    return best, best_rotation, tesseract_used


def _run_with_rotations(image: np.ndarray) -> tuple[OCRResult, int]:
    best = run_ocr(image, lang="japan")
    best_rotation = 0
    if len(best.tokens) >= MIN_SHEET_TOKENS:
        return best, best_rotation

    for rotation in (90, 180, 270):
        rotated = _rotate_image(image, rotation)
        result = run_ocr(rotated, lang="japan")
        if len(result.tokens) > len(best.tokens):
            best = result
            best_rotation = rotation

    return best, best_rotation


def _rotate_image(image: np.ndarray, rotation: int) -> np.ndarray:
    if rotation == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def _map_tokens_from_rotated(
    tokens: list[OCRToken], rotation: int, original_shape: tuple[int, int]
) -> list[OCRToken]:
    height, width = original_shape
    mapped: list[OCRToken] = []
    for token in tokens:
        mapped_bbox = _map_bbox_from_rotated(token.bbox, rotation, width, height)
        mapped.append(
            OCRToken(
                text=token.text,
                confidence=token.confidence,
                bbox=mapped_bbox,
            )
        )
    return mapped


def _map_bbox_from_rotated(
    bbox: tuple[int, int, int, int], rotation: int, width: int, height: int
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    mapped = [_map_point_from_rotated(x, y, rotation, width, height) for x, y in corners]
    xs = [p[0] for p in mapped]
    ys = [p[1] for p in mapped]
    return (min(xs), min(ys), max(xs), max(ys))


def _map_point_from_rotated(
    x: int, y: int, rotation: int, width: int, height: int
) -> tuple[int, int]:
    if rotation == 90:
        return (y, height - 1 - x)
    if rotation == 180:
        return (width - 1 - x, height - 1 - y)
    if rotation == 270:
        return (width - 1 - y, x)
    return (x, y)


def _run_paddle_vl(image: np.ndarray) -> tuple[list[OCRToken], dict]:
    vl = _get_vl_instance()
    results = vl.predict([image])
    if not results:
        return [], {"pipeline": "PaddleOCR-VL-1.5", "block_count": 0}

    result = results[0]
    tokens = _tokens_from_vl_result(result)
    return tokens, {"pipeline": "PaddleOCR-VL-1.5", "block_count": len(tokens)}


def _get_vl_instance():
    global _VL_INSTANCE
    if _VL_INSTANCE is None:
        try:
            from paddleocr import PaddleOCRVL
        except Exception as exc:  # pragma: no cover - required dependency
            raise RuntimeError("PaddleOCRVL dependency missing") from exc
        _VL_INSTANCE = PaddleOCRVL(pipeline_version="v1.5")
    return _VL_INSTANCE


def _tokens_from_vl_result(result) -> list[OCRToken]:
    blocks = result.get("parsing_res_list") or []
    tokens: list[OCRToken] = []
    for block in blocks:
        if isinstance(block, dict):
            label = block.get("block_label")
            content = block.get("block_content")
            bbox = block.get("block_bbox")
            polygon = block.get("block_polygon_points")
        else:
            label = getattr(block, "label", None)
            content = getattr(block, "content", None)
            bbox = getattr(block, "bbox", None)
            polygon = getattr(block, "polygon_points", None)

        if label in {"image", "chart", "header_image", "footer_image"}:
            continue
        if not content:
            continue
        bbox_tuple = _coerce_bbox(bbox, polygon)
        if bbox_tuple is None:
            continue
        for line in str(content).splitlines():
            line = line.strip()
            if not line:
                continue
            tokens.append(OCRToken(text=line, confidence=0.85, bbox=bbox_tuple))
    return tokens


def _coerce_bbox(
    bbox: list | tuple | None, polygon: list | tuple | None
) -> tuple[int, int, int, int] | None:
    if bbox and len(bbox) == 4:
        return (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
    if polygon:
        xs = [int(p[0]) for p in polygon]
        ys = [int(p[1]) for p in polygon]
        return (min(xs), min(ys), max(xs), max(ys))
    return None
