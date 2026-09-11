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
    component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
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
            },
        })
    layer_directory = project_directory / "layers"
    layer_directory.mkdir(parents=True, exist_ok=True)
    output_path = layer_directory / f"{legend_item['id']}.geojson"
    collection = {"type": "FeatureCollection", "features": features, "crs": {"type": "name", "properties": {"name": "EPSG:23700"}}}
    output_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    return {"project_id": project_id, "layer_id": legend_item["id"], "geometry_type": "Point", "feature_count": len(features), "geojson_path": str(output_path)}