from __future__ import annotations

from typing import Any

import cv2
import numpy as np
import pytesseract


def text_boxes(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    data = pytesseract.image_to_data(
        cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
        lang="hun+eng",
        config="--psm 11",
        output_type=pytesseract.Output.DICT,
    )
    boxes: list[tuple[int, int, int, int]] = []
    for left, top, width, height, text in zip(
        data["left"], data["top"], data["width"], data["height"], data["text"],
    ):
        if not str(text).strip() or int(width) <= 0 or int(height) <= 0:
            continue
        boxes.append((int(left), int(top), int(width), int(height)))
    return boxes


def inpaint_text_regions(
    image: np.ndarray,
    boxes: list[tuple[int, int, int, int]] | None = None,
    dilation: int = 3,
    radius: int = 3,
) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, int, int]]]:
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    detected_boxes = boxes if boxes is not None else text_boxes(image)
    for left, top, width, height in detected_boxes:
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(mask.shape[1], left + width)
        y2 = min(mask.shape[0], top + height)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255
    if dilation > 0:
        kernel_size = dilation * 2 + 1
        mask = cv2.dilate(mask, np.ones((kernel_size, kernel_size), np.uint8))
    cleaned = cv2.inpaint(image, mask, max(1, radius), cv2.INPAINT_TELEA) if np.any(mask) else image.copy()
    return cleaned, mask, detected_boxes