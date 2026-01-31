from __future__ import annotations

from worker.ocr.image_utils import OCRToken, crop_image
from worker.ocr.ocr_engine import OCRResult, run_ocr


def extract_sheet(image, sheet_bbox) -> OCRResult:
    crop = crop_image(image, sheet_bbox)
    result = run_ocr(crop, lang="japan")
    offset_tokens = []
    x0, y0, _, _ = sheet_bbox
    for token in result.tokens:
        bx0, by0, bx1, by1 = token.bbox
        offset_tokens.append(
            OCRToken(
                text=token.text,
                confidence=token.confidence,
                bbox=(bx0 + x0, by0 + y0, bx1 + x0, by1 + y0),
            )
        )
    return OCRResult(engine=result.engine, tokens=offset_tokens)
