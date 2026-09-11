from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageStat

POLYGON_KEYWORDS = ("övezet", "lakóterület", "gazdasági", "zöldterület", "beépítésre szánt", "vízfelület")
LINE_KEYWORDS = ("vonal", "szabályozási vonal", "építési vonal", "védőtávolság", "tengely", "határ")
POINT_KEYWORDS = ("fa", "műemlék", "kút", "magassági pont", "műtárgy", "jel")


def infer_geometry_type(text: str, swatch_width: int, swatch_height: int) -> str:
    normalized = text.lower()
    if any(keyword in normalized for keyword in POLYGON_KEYWORDS):
        return "Polygon"
    if any(keyword in normalized for keyword in LINE_KEYWORDS):
        return "LineString"
    if any(keyword in normalized for keyword in POINT_KEYWORDS):
        return "Point"
    if swatch_width > swatch_height * 3:
        return "LineString"
    if swatch_width < swatch_height * 1.5:
        return "Point"
    return "Polygon"


def infer_class_code(text: str, fallback_index: int) -> str:
    match = re.search(r"\b(?:[A-Za-zÁÉÍÓÖŐÚÜŰ]{1,4}[-/]?\d{1,3}|[A-Za-zÁÉÍÓÖŐÚÜŰ]{1,5})\b", text)
    return match.group(0) if match else f"CLASS-{fallback_index:02d}"


def detect_legend_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    # Use OCR density to find a text-rich lower/side region, with an editable fallback.
    data = pytesseract.image_to_data(image, lang="hun+eng", config="--psm 11", output_type=pytesseract.Output.DICT)
    boxes = [(int(x), int(y), int(w), int(h)) for x, y, w, h, text in zip(data["left"], data["top"], data["width"], data["height"], data["text"]) if text.strip() and int(y) > image.height * 0.35]
    if len(boxes) >= 3:
        left = max(0, min(box[0] for box in boxes) - 24)
        top = max(0, min(box[1] for box in boxes) - 24)
        right = min(image.width, max(box[0] + box[2] for box in boxes) + 24)
        bottom = min(image.height, max(box[1] + box[3] for box in boxes) + 24)
        if right > left and bottom > top:
            return (left, top, right, bottom)
    return (0, max(0, int(image.height * 0.65)), max(1, int(image.width * 0.55)), max(1, image.height))


def _row_bands(crop: Image.Image) -> list[tuple[int, int]]:
    if crop.width == 0 or crop.height == 0:
        return []
    grayscale = crop.convert("L")
    projection = []
    for y in range(grayscale.height):
        row = ImageStat.Stat(grayscale.crop((0, y, grayscale.width, y + 1))).mean[0]
        projection.append(255 - row)
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(projection + [0]):
        if value > 8 and start is None:
            start = index
        elif value <= 8 and start is not None:
            if index - start >= 4:
                bands.append((max(0, start - 3), min(crop.height, index + 3)))
            start = None
    return bands


def parse_legend(source_path: str, project_id: str, storage_root: str, bbox: list[int] | None = None) -> dict[str, Any]:
    source = Path(source_path)
    project_directory = Path(storage_root) / project_id
    legend_directory = project_directory / "legend"
    legend_directory.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGB")
    image_bbox = tuple(bbox) if bbox else detect_legend_bbox(image)
    crop = image.crop(image_bbox)
    rows = _row_bands(crop)
    classes: list[dict[str, Any]] = []
    for index, (top, bottom) in enumerate(rows, start=1):
        row = crop.crop((0, top, crop.width, bottom))
        ocr_text = pytesseract.image_to_string(row, lang="hun+eng", config="--psm 7").strip()
        if not ocr_text:
            continue
        swatch_width = max(1, min(row.width // 3, 160))
        swatch = row.crop((0, 0, swatch_width, row.height))
        rgb = np.array(swatch.convert("RGB"), dtype=np.uint8)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        signature = {
            "rgb": [round(channel) for channel in ImageStat.Stat(swatch).mean[:3]],
            "hsv": [round(float(value)) for value in hsv.reshape(-1, 3).mean(axis=0)],
            "lab": [round(float(value)) for value in lab.reshape(-1, 3).mean(axis=0)],
            "edge_density": round(float(np.count_nonzero(edges) / max(edges.size, 1)), 4),
        }
        classes.append({
            "id": f"leg_cls_{index:02d}",
            "code": infer_class_code(ocr_text, index),
            "name": ocr_text,
            "geometry_type": infer_geometry_type(ocr_text, swatch.width, swatch.height),
            "color_rgb": signature["rgb"],
            "visual_signature": signature,
            "color_tolerance": 18,
            "enabled": True,
            "row_bbox": [image_bbox[0], image_bbox[1] + top, image_bbox[2], image_bbox[1] + bottom],
        })
    result = {
        "project_id": project_id,
        "status": "completed",
        "legend_bbox": list(image_bbox),
        "legend_bbox_confidence": 0.35 if bbox is None else 1.0,
        "manual_review_required": bbox is None,
        "items": classes,
    }
    (legend_directory / "registry.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
