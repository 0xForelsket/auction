from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class RoiResult:
    header_bbox: tuple[int, int, int, int]
    sheet_bbox: tuple[int, int, int, int]
    photos_bbox: tuple[int, int, int, int] | None
    roi_version: str = "v1"


def detect_rois(image: np.ndarray) -> RoiResult:
    height, width = image.shape[:2]

    header_bbox = detect_header_bbox(image)
    if header_bbox is None:
        header_bbox = fallback_header_bbox(width, height)

    header_x0, header_y0, header_x1, header_y1 = header_bbox
    left_width = int(width * 0.62)
    sheet_bbox = (0, header_y1, left_width, height)
    photos_bbox = (left_width, header_y1, width, height)

    if not _valid_header_bbox(header_bbox, width, height) or not _valid_sheet_bbox(
        sheet_bbox, width, height
    ):
        header_bbox = fallback_header_bbox(width, height)
        header_x0, header_y0, header_x1, header_y1 = header_bbox
        left_width = int(width * 0.62)
        sheet_bbox = (0, header_y1, left_width, height)
        photos_bbox = (left_width, header_y1, width, height)

    return RoiResult(header_bbox=header_bbox, sheet_bbox=sheet_bbox, photos_bbox=photos_bbox)


def detect_header_bbox(image: np.ndarray) -> tuple[int, int, int, int] | None:
    """Detect the blue header band in USS screenshots.

    Uses HSV thresholding for blue-ish ranges and picks the largest
    wide contour in the upper portion of the image.
    """
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lower = np.array([90, 50, 50])
    upper = np.array([140, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    candidates: list[tuple[int, int, int, int, float]] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if y > int(height * 0.45):
            continue
        if w < int(width * 0.3):
            continue
        aspect = w / max(h, 1)
        if aspect < 3:
            continue
        area = w * h
        candidates.append((x, y, x + w, y + h, area))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[4], reverse=True)
    x0, y0, x1, y1, _ = candidates[0]

    x1 = min(x1, int(width * 0.65))
    return int(x0), int(y0), int(x1), int(y1)


def fallback_header_bbox(width: int, height: int) -> tuple[int, int, int, int]:
    header_height = int(height * 0.22)
    header_width = int(width * 0.62)
    return 0, 0, header_width, header_height


def _valid_header_bbox(
    bbox: tuple[int, int, int, int], width: int, height: int
) -> bool:
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        return False
    if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
        return False
    ratio = (y1 - y0) / max(height, 1)
    return 0.06 <= ratio <= 0.25


def _valid_sheet_bbox(
    bbox: tuple[int, int, int, int], width: int, height: int
) -> bool:
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        return False
    if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
        return False
    ratio = (x1 - x0) / max(width, 1)
    return 0.45 <= ratio <= 0.8
