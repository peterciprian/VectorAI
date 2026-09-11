from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import rasterio
from affine import Affine
from shapely.geometry import LineString
from shapely.validation import explain_validity
from skimage.morphology import skeletonize

from .vectorizer import _pixel_transform


def _line_mask(image: np.ndarray, color_rgb: list[int], tolerance: int) -> np.ndarray:
    sample = np.uint8([[color_rgb[:3]]])
    sample_lab = cv2.cvtColor(sample, cv2.COLOR_RGB2LAB)[0, 0].astype(np.int16)
    image_lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.int16)
    distance = np.linalg.norm(image_lab - sample_lab, axis=2)
    mask = (distance <= max(1, tolerance * 2)).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)


def _pixel_line_transform(project_directory: Path) -> Affine:
    return _pixel_transform(project_directory)


def vectorize_line_class(
    project_id: str,
    storage_root: str,
    legend_item: dict[str, Any],
    simplify_meters: float = 0.2,
) -> dict[str, Any]:
    if legend_item.get("geometry_type") != "LineString":
        raise ValueError("Only LineString legend items can be sent to the line vectorizer")
    project_directory = Path(storage_root) / project_id
    raster_path = project_directory / "raster" / "master.jpg"
    if not raster_path.exists():
        raise FileNotFoundError("Ingested master raster is not ready")
    image = cv2.cvtColor(cv2.imread(str(raster_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = _line_mask(image, legend_item.get("color_rgb", [0, 0, 0]), int(legend_item.get("color_tolerance", 18)))
    skeleton = skeletonize(mask > 0)
    transform = _pixel_line_transform(project_directory)
    features: list[dict[str, Any]] = []
    contours, _ = cv2.findContours(skeleton.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    for contour in contours:
        if len(contour) < 2:
            continue
        pixel_coordinates = contour[:, 0, :].astype(float)
        map_coordinates = [transform * (float(x), float(y)) for x, y in pixel_coordinates]
        line = LineString(map_coordinates).simplify(simplify_meters, preserve_topology=False)
        if line.is_empty or line.geom_type != "LineString" or line.length <= 0:
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(json.dumps(line.__geo_interface__)),
            "properties": {
                "legend_id": legend_item["id"],
                "code": legend_item.get("code", ""),
                "name": legend_item.get("name", ""),
                "geometry_type": "LineString",
                "length": line.length,
                "validity": explain_validity(line),
            },
        })
    layer_directory = project_directory / "layers"
    layer_directory.mkdir(parents=True, exist_ok=True)
    output_path = layer_directory / f"{legend_item['id']}.geojson"
    collection = {"type": "FeatureCollection", "features": features, "crs": {"type": "name", "properties": {"name": "EPSG:23700"}}}
    output_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    return {"project_id": project_id, "layer_id": legend_item["id"], "geometry_type": "LineString", "feature_count": len(features), "geojson_path": str(output_path)}
