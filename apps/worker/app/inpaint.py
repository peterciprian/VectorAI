from __future__ import annotations

import cv2
import numpy as np
import pytesseract


def text_boxes(
    image: np.ndarray,
    min_confidence: float = 35.0,
    exclusion_zones: list[list[int]] | None = None,
    border_margin: int = 0,
) -> list[tuple[int, int, int, int, float]]:
    data = pytesseract.image_to_data(
        cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
        lang="hun+eng",
        config="--psm 11",
        output_type=pytesseract.Output.DICT,
    )
    boxes: list[tuple[int, int, int, int, float]] = []
    for left, top, width, height, confidence, text in zip(
        data["left"], data["top"], data["width"], data["height"], data["conf"], data["text"],
    ):
        if not str(text).strip() or int(width) <= 0 or int(height) <= 0 or float(confidence) < min_confidence:
            continue
        center_x = int(left) + int(width) / 2
        center_y = int(top) + int(height) / 2
        if border_margin and (center_x < border_margin or center_y < border_margin or center_x > image.shape[1] - border_margin or center_y > image.shape[0] - border_margin):
            continue
        if exclusion_zones and any(x1 <= center_x <= x2 and y1 <= center_y <= y2 for x1, y1, x2, y2 in exclusion_zones):
            continue
        boxes.append((int(left), int(top), int(width), int(height), float(confidence)))
    return boxes


def inpaint_text_regions(
    image: np.ndarray,
    boxes: list[tuple[int, ...]] | None = None,
    dilation: int = 3,
    radius: int = 3,
    min_confidence: float = 35.0,
    exclusion_zones: list[list[int]] | None = None,
    border_margin: int = 0,
    geometry_type: str = "Polygon",
) -> tuple[np.ndarray, np.ndarray, list[tuple[int, ...]]]:
    if geometry_type != "Polygon":
        return image.copy(), np.zeros(image.shape[:2], dtype=np.uint8), []
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    detected_boxes = boxes if boxes is not None else text_boxes(image, min_confidence, exclusion_zones, border_margin)
    for detected_box in detected_boxes:
        left, top, width, height = detected_box[:4]
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