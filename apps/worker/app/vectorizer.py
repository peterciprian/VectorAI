from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import rasterio
from affine import Affine
from rasterio.features import shapes
from shapely.geometry import shape
from shapely.validation import explain_validity


def _pixel_transform(project_directory: Path) -> Affine:
    metadata_path = project_directory / "georef" / "metadata.json"
    if not metadata_path.exists():
        return Affine.identity()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    values = metadata.get("transform")
    return Affine(*values) if values and len(values) == 6 else Affine.identity()


def _color_mask(image: np.ndarray, color_rgb: list[int], tolerance: int) -> np.ndarray:
    sample = np.uint8([[color_rgb[:3]]])
    sample_lab = cv2.cvtColor(sample, cv2.COLOR_RGB2LAB)[0, 0].astype(np.int16)
    image_lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.int16)
    distance = np.linalg.norm(image_lab - sample_lab, axis=2)
    mask = (distance <= max(1, tolerance * 2)).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def polygonize_class(
    project_id: str,
    storage_root: str,
    legend_item: dict[str, Any],
    min_area_pixels: float = 16,
    simplify_meters: float = 0.2,
) -> dict[str, Any]:
    if legend_item.get("geometry_type") != "Polygon":
        raise ValueError("Only Polygon legend items can be sent to the polygonizer")
    project_directory = Path(storage_root) / project_id
    raster_path = project_directory / "raster" / "master.jpg"
    if not raster_path.exists():
        raise FileNotFoundError("Ingested master raster is not ready")
    image = cv2.cvtColor(cv2.imread(str(raster_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = _color_mask(image, legend_item.get("color_rgb", [0, 0, 0]), int(legend_item.get("color_tolerance", 18)))
    transform = _pixel_transform(project_directory)
    features: list[dict[str, Any]] = []
    for geometry, value in shapes(mask, mask=mask > 0, transform=transform):
        polygon = shape(geometry)
        if polygon.area < min_area_pixels:
            continue
        polygon = polygon.simplify(simplify_meters, preserve_topology=True)
        if polygon.is_empty:
            continue
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty or polygon.geom_type != "Polygon":
            continue
        features.append({
            "type": "Feature",
            "geometry": json.loads(json.dumps(polygon.__geo_interface__)),
            "properties": {
                "legend_id": legend_item["id"],
                "code": legend_item.get("code", ""),
                "name": legend_item.get("name", ""),
                "geometry_type": "Polygon",
                "area": polygon.area,
                "validity": explain_validity(polygon),
            },
        })
    layer_id = legend_item["id"]
    layer_directory = project_directory / "layers"
    layer_directory.mkdir(parents=True, exist_ok=True)
    output_path = layer_directory / f"{layer_id}.geojson"
    collection = {"type": "FeatureCollection", "features": features, "crs": {"type": "name", "properties": {"name": "EPSG:23700"}}}
    output_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    return {"project_id": project_id, "layer_id": layer_id, "geometry_type": "Polygon", "feature_count": len(features), "geojson_path": str(output_path)}
