from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np


@dataclass
class OCRToken:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int]


def decode_image(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Failed to decode image")
    return image


def encode_png(image: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Failed to encode image")
    return encoded.tobytes()


def crop_image(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(image.shape[1], x1)
    y1 = min(image.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Invalid crop bbox")
    return image[y0:y1, x0:x1]


def scale_bbox(bbox: tuple[int, int, int, int], scale: float) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    return (
        int(x0 * scale),
        int(y0 * scale),
        int(x1 * scale),
        int(y1 * scale),
    )


def to_int_bbox(points: Iterable[Iterable[float]]) -> tuple[int, int, int, int]:
    xs = [int(p[0]) for p in points]
    ys = [int(p[1]) for p in points]
    return min(xs), min(ys), max(xs), max(ys)
