from __future__ import annotations

from dataclasses import dataclass
import json
import os
import shutil
from typing import List

import numpy as np

from worker.ocr.image_utils import OCRToken, to_int_bbox

_PADDLE_INSTANCE = None


def get_paddle_device() -> str:
    device = os.getenv("OCR_DEVICE")
    if device:
        return device

    use_gpu_env = os.getenv("OCR_USE_GPU")
    if use_gpu_env is not None:
        return "gpu" if use_gpu_env.lower() in {"1", "true", "yes", "y"} else "cpu"

    try:
        import paddle
    except Exception:
        return "cpu"

    try:
        if paddle.device.is_compiled_with_cuda():
            return "gpu"
    except Exception:
        return "cpu"
    return "cpu"


def _paddle_use_gpu() -> bool:
    return get_paddle_device().startswith("gpu")


@dataclass
class OCRResult:
    engine: str
    tokens: List[OCRToken]
    meta: dict | None = None


def run_ocr(
    image: np.ndarray,
    lang: str = "japan",
    engine_preference: list[str] | None = None,
) -> OCRResult:
    """Run OCR using the best available engine.

    Priority:
    - PaddleOCR (if installed)
    - Tesseract (if pytesseract + binary available)
    """
    order = engine_preference or ["paddle", "tesseract"]
    last_result: OCRResult | None = None
    for engine in order:
        try:
            if engine == "paddle":
                result = _run_paddle(image, lang=lang)
            elif engine == "tesseract":
                result = _run_tesseract(image, lang=lang)
            else:
                continue
            if result.tokens:
                return result
            if last_result is None:
                last_result = result
        except Exception:
            continue

    return last_result if last_result is not None else OCRResult(engine="none", tokens=[])


def _run_paddle(image: np.ndarray, lang: str) -> OCRResult:
    global _PADDLE_INSTANCE
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PaddleOCR not installed") from exc

    if _PADDLE_INSTANCE is None:
        _PADDLE_INSTANCE = PaddleOCR(
            use_angle_cls=True,
            lang="japan" if lang == "japan" else "en",
            use_gpu=_paddle_use_gpu(),
            show_log=False,
        )

    results = _PADDLE_INSTANCE.ocr(image, cls=True)

    tokens: list[OCRToken] = []
    for line in results or []:
        for box, (text, confidence) in line:
            bbox = to_int_bbox(box)
            tokens.append(OCRToken(text=text, confidence=float(confidence), bbox=bbox))

    return OCRResult(engine="paddle", tokens=tokens)


def _run_tesseract(image: np.ndarray, lang: str) -> OCRResult:
    if shutil.which("tesseract") is None:
        raise RuntimeError("tesseract binary not available")
    try:
        import pytesseract
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pytesseract not installed") from exc

    config = "--oem 1 --psm 6"
    language = "jpn+eng" if lang == "japan" else "eng"
    data = pytesseract.image_to_data(image, lang=language, config=config, output_type=pytesseract.Output.DICT)

    tokens: list[OCRToken] = []
    for i, text in enumerate(data.get("text", [])):
        text = (text or "").strip()
        if not text:
            continue
        conf = float(data.get("conf", [0])[i]) / 100.0
        x = int(data.get("left", [0])[i])
        y = int(data.get("top", [0])[i])
        w = int(data.get("width", [0])[i])
        h = int(data.get("height", [0])[i])
        tokens.append(OCRToken(text=text, confidence=conf, bbox=(x, y, x + w, y + h)))

    return OCRResult(engine="tesseract", tokens=tokens)


def result_to_json(result: OCRResult) -> str:
    return json.dumps(
        {
            "engine": result.engine,
            "meta": result.meta,
            "tokens": [
                {"text": token.text, "confidence": token.confidence, "bbox": list(token.bbox)}
                for token in result.tokens
            ],
        }
    )
