from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from shapely.geometry import Point

from .vectorizer import _pixel_transform


def _point_mask(image: np.ndarray, color_rgb: list[int], tolerance: int) -> np.ndarray:
    sample = np.uint8([[color_rgb[:3]]])
    sample_lab = cv2.cvtColor(sample, cv2.COLOR_RGB2LAB)[0, 0].astype(np.int16)
    image_lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.int16)
    distance = np.linalg.norm(image_lab - sample_lab, axis=2)
    mask = (distance <= max(1, tolerance * 2)).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)


def _template_centroids(
    image: np.ndarray,
    template_path: Path,
    threshold: float,
) -> list[tuple[float, float, float]]:
    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if template is None or template.size == 0:
        raise ValueError("Point symbol template could not be read")
    gray_image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    template_height, template_width = template.shape[:2]
    if template_height > gray_image.shape[0] or template_width > gray_image.shape[1]:
        return []
    template_mask = np.where(template < 245, 255, 0).astype(np.uint8)
    if not np.any(template_mask):
        raise ValueError("Point symbol template has no foreground pixels")
    scores = cv2.matchTemplate(gray_image, template, cv2.TM_SQDIFF_NORMED, mask=template_mask)
    detections: list[tuple[float, float, float]] = []
    suppression_radius = max(template_width, template_height) / 2
    kernel_size = max(3, int(suppression_radius * 2 + 1))
    if kernel_size % 2 == 0:
        kernel_size += 1
    local_minima = scores == cv2.erode(scores, np.ones((kernel_size, kernel_size), np.uint8))
    candidates = [
        (int(row), int(column), float(scores[row, column]))
        for row, column in np.argwhere((scores <= 1 - threshold) & local_minima)
    ]
    candidates.sort(key=lambda candidate: candidate[2])
    for row, column, score in candidates:
        center_x = float(column + template_width / 2)
        center_y = float(row + template_height / 2)
        if any((center_x - existing_x) ** 2 + (center_y - existing_y) ** 2 < suppression_radius**2 for existing_x, existing_y, _ in detections):
            continue
        detections.append((center_x, center_y, 1.0 - score))
    return detections


def vectorize_point_class(
    project_id: str,
    storage_root: str,
    legend_item: dict[str, Any],
    min_area_pixels: int = 4,
) -> dict[str, Any]:
    if legend_item.get("geometry_type") != "Point":
        raise ValueError("Only Point legend items can be sent to the point vectorizer")
    project_directory = Path(storage_root) / project_id
    raster_path = project_directory / "raster" / "master.jpg"
    if not raster_path.exists():
        raise FileNotFoundError("Ingested master raster is not ready")
    image = cv2.cvtColor(cv2.imread(str(raster_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = _point_mask(image, legend_item.get("color_rgb", [0, 0, 0]), int(legend_item.get("color_tolerance", 18)))
    transform = _pixel_transform(project_directory)
    component_count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    symbol_type = legend_item.get("symbol_type") or legend_item.get("code", "")
    label = legend_item.get("label") or legend_item.get("name", "")
    features: list[dict[str, Any]] = []
    for component_id in range(1, component_count):
        area = int(stats[component_id, cv2.CC_STAT_AREA])
        if area < min_area_pixels:
            continue
        pixel_x, pixel_y = centroids[component_id]
        map_x, map_y = transform * (float(pixel_x), float(pixel_y))
        point = Point(map_x, map_y)
        features.append({
            "type": "Feature",
            "geometry": json.loads(json.dumps(point.__geo_interface__)),
            "properties": {
                "legend_id": legend_item["id"],
                "code": legend_item.get("code", ""),
                "name": legend_item.get("name", ""),
                "symbol_type": symbol_type,
                "label": label,
                "geometry_type": "Point",
                "pixel_area": area,
                "detection_method": "color_component",
            },
        })
    template_path_value = legend_item.get("template_path")
    if template_path_value:
        project_root = project_directory.resolve()
        template_path = (project_directory / str(template_path_value)).resolve()
        try:
            template_path.relative_to(project_root)
        except ValueError as error:
            raise ValueError("Point symbol template must be inside the project directory") from error
        for pixel_x, pixel_y, confidence in _template_centroids(
            image,
            template_path,
            float(legend_item.get("template_threshold", 0.75)),
        ):
            if any((pixel_x - existing_x) ** 2 + (pixel_y - existing_y) ** 2 < 16 for existing_x, existing_y in centroids):
                continue
            map_x, map_y = transform * (pixel_x, pixel_y)
            point = Point(map_x, map_y)
            features.append({
                "type": "Feature",
                "geometry": json.loads(json.dumps(point.__geo_interface__)),
                "properties": {
                    "legend_id": legend_item["id"],
                    "code": legend_item.get("code", ""),
                    "name": legend_item.get("name", ""),
                    "symbol_type": symbol_type,
                    "label": label,
                    "geometry_type": "Point",
                    "detection_method": "template_match",
                    "confidence": confidence,
                },
            })
    layer_directory = project_directory / "layers"
    layer_directory.mkdir(parents=True, exist_ok=True)
    output_path = layer_directory / f"{legend_item['id']}.geojson"
    collection = {"type": "FeatureCollection", "features": features, "crs": {"type": "name", "properties": {"name": "EPSG:23700"}}}
    output_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    return {"project_id": project_id, "layer_id": legend_item["id"], "geometry_type": "Point", "feature_count": len(features), "geojson_path": str(output_path)}