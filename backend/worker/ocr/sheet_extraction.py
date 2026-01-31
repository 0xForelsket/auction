from __future__ import annotations

import cv2
import numpy as np
import re

from worker.ocr.image_utils import OCRToken, crop_image
from worker.ocr.ocr_engine import OCRResult, run_ocr
from worker.ocr.preprocessing import preprocess_auction_image, binarize_image
from worker.ocr.vl_engine import run_vl_ocr


MIN_SHEET_TOKENS = 10


def extract_sheet(image, sheet_bbox) -> OCRResult:
    crop = crop_image(image, sheet_bbox)

    best_result = run_vl_ocr(crop)
    vl_tokens = best_result.tokens

    vl_low_signal = len(vl_tokens) >= MIN_SHEET_TOKENS and not _vl_has_value_signal(vl_tokens)
    if len(vl_tokens) < MIN_SHEET_TOKENS or vl_low_signal:
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
                    "vl_low_signal": vl_low_signal,
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
                    "vl_low_signal": vl_low_signal,
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
        tesseract_img = binarize_image(preprocess_auction_image(image))
        tesseract_result = run_ocr(
            tesseract_img, lang="japan", engine_preference=["tesseract"]
        )
        if len(tesseract_result.tokens) > len(best.tokens):
            best = tesseract_result
            best_rotation = 0
            tesseract_used = True
    return best, best_rotation, tesseract_used


def _run_with_rotations(image: np.ndarray) -> tuple[OCRResult, int]:
    prepped = preprocess_auction_image(image)
    best = run_ocr(prepped, lang="japan")
    best_rotation = 0
    if len(best.tokens) >= MIN_SHEET_TOKENS:
        return best, best_rotation

    for rotation in (90, 180, 270):
        rotated = _rotate_image(image, rotation)
        rotated_prepped = preprocess_auction_image(rotated)
        result = run_ocr(rotated_prepped, lang="japan")
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


def _vl_has_value_signal(tokens: list[OCRToken]) -> bool:
    if not tokens:
        return False
    value_like = 0
    for token in tokens:
        text = token.text or ""
        if re.search(r"\d", text):
            value_like += 1
        elif re.search(r"[A-Z]{2,}", text):
            value_like += 1
        elif len(text) >= 6:
            value_like += 1
        if re.search(r"[A-HJ-NPR-Z0-9]{8,17}", text):
            return True
    threshold = max(3, int(len(tokens) * 0.1))
    return value_like >= threshold
