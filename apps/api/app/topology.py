from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import shape
from shapely.ops import snap, unary_union


def _layer_paths(project_directory: Path) -> list[Path]:
    return sorted((project_directory / "layers").glob("*.geojson"))


def _read_collection(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_project_topology(storage_root: str, project_id: str, sliver_area: float = 1.0) -> dict[str, Any]:
    project_directory = Path(storage_root) / project_id
    issues: list[dict[str, Any]] = []
    checked_features = 0
    for layer_path in _layer_paths(project_directory):
        collection = _read_collection(layer_path)
        features = collection.get("features", [])
        geometries = [shape(feature["geometry"]) for feature in features]
        checked_features += len(geometries)
        for index, geometry in enumerate(geometries):
            if not geometry.is_valid:
                issues.append({"layer_id": layer_path.stem, "feature_index": index, "kind": "invalid_geometry", "detail": geometry.geom_type})
            if geometry.geom_type == "Polygon" and geometry.area < sliver_area:
                issues.append({"layer_id": layer_path.stem, "feature_index": index, "kind": "sliver", "detail": f"area={geometry.area:.6f}"})
        for first_index, first in enumerate(geometries):
            if first.geom_type != "Polygon":
                continue
            for second_index in range(first_index + 1, len(geometries)):
                second = geometries[second_index]
                if second.geom_type == "Polygon":
                    overlap = first.intersection(second).area
                    if overlap > 0:
                        issues.append({"layer_id": layer_path.stem, "feature_index": first_index, "other_feature_index": second_index, "kind": "overlap", "detail": f"area={overlap:.6f}"})
    return {"project_id": project_id, "checked_features": checked_features, "issue_count": len(issues), "valid": not issues, "issues": issues}


def clean_project_topology(storage_root: str, project_id: str, sliver_area: float = 1.0, snap_tolerance: float = 0.2) -> dict[str, Any]:
    project_directory = Path(storage_root) / project_id
    cleaned_features = 0
    removed_slivers = 0
    repaired_invalid = 0
    for layer_path in _layer_paths(project_directory):
        collection = _read_collection(layer_path)
        source_features = collection.get("features", [])
        source_geometries = [shape(feature["geometry"]) for feature in source_features]
        output_features: list[dict[str, Any]] = []
        for feature, original_geometry in zip(source_features, source_geometries):
            other_geometries = [geometry for geometry in source_geometries if geometry is not original_geometry]
            geometry = snap(original_geometry, unary_union(other_geometries), snap_tolerance) if other_geometries else original_geometry
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
                repaired_invalid += 1
            if geometry.is_empty:
                continue
            if geometry.geom_type == "Polygon" and geometry.area < sliver_area:
                removed_slivers += 1
                continue
            feature["geometry"] = json.loads(json.dumps(geometry.__geo_interface__))
            output_features.append(feature)
            cleaned_features += 1
        collection["features"] = output_features
        layer_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    return {"project_id": project_id, "cleaned_features": cleaned_features, "removed_slivers": removed_slivers, "repaired_invalid": repaired_invalid, "validation": validate_project_topology(storage_root, project_id, sliver_area)}