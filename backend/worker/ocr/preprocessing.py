from __future__ import annotations

import cv2
import numpy as np


UPSCALE_TARGET_HEIGHT = 1500


def preprocess_auction_image(image: np.ndarray) -> np.ndarray:
    """Preprocess USS WhatsApp screenshots for OCR.

    - Upscale to improve small text
    - Denoise JPEG artifacts
    - Sharpen
    - CLAHE on luminance channel
    """
    height, width = image.shape[:2]

    if height < UPSCALE_TARGET_HEIGHT:
        scale = UPSCALE_TARGET_HEIGHT / height
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    image = cv2.fastNlMeansDenoisingColored(image, h=6, hColor=6)

    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32)
    image = cv2.filter2D(image, -1, kernel)

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge([l_channel, a_channel, b_channel])
    image = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    return image
