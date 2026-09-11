from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon, shape
from shapely.ops import linemerge, snap, unary_union


def _layer_paths(project_directory: Path) -> list[Path]:
    return sorted((project_directory / "layers").glob("*.geojson"))


def _read_collection(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _polygon_parts(geometry: Any) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return [part for part in geometry.geoms if isinstance(part, Polygon)]
    return []


def _line_endpoints(geometry: LineString) -> list[tuple[float, float]]:
    return [tuple(geometry.coords[0]), tuple(geometry.coords[-1])]


def _bridge_lines(geometries: list[LineString], tolerance: float) -> tuple[list[LineString], int]:
    if len(geometries) < 2:
        return geometries, 0
    lines = list(geometries)
    bridges = 0
    while True:
        best: tuple[int, int, tuple[float, float], tuple[float, float], float] | None = None
        for first_index, first in enumerate(lines):
            for second_index in range(first_index + 1, len(lines)):
                second = lines[second_index]
                for first_point in _line_endpoints(first):
                    for second_point in _line_endpoints(second):
                        distance = LineString([first_point, second_point]).length
                        if distance <= tolerance and (best is None or distance < best[-1]):
                            best = (first_index, second_index, first_point, second_point, distance)
        if best is None:
            break
        first_index, second_index, first_point, second_point, _ = best
        merged = linemerge(unary_union([lines[first_index], lines[second_index], LineString([first_point, second_point])]))
        replacements = list(merged.geoms) if isinstance(merged, MultiLineString) else [merged]
        lines = [line for index, line in enumerate(lines) if index not in {first_index, second_index}] + [line for line in replacements if isinstance(line, LineString)]
        bridges += 1
    return lines, bridges


def validate_project_topology(storage_root: str, project_id: str, sliver_area: float = 1.0, gap_distance: float = 0.2) -> dict[str, Any]:
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
            if first.geom_type == "LineString":
                for second_index in range(first_index + 1, len(geometries)):
                    second = geometries[second_index]
                    if second.geom_type != "LineString":
                        continue
                    endpoint_distance = min(LineString([first.coords[0], second.coords[0]]).length, LineString([first.coords[0], second.coords[-1]]).length, LineString([first.coords[-1], second.coords[0]]).length, LineString([first.coords[-1], second.coords[-1]]).length)
                    if 0 < endpoint_distance <= gap_distance:
                        issues.append({"layer_id": layer_path.stem, "feature_index": first_index, "other_feature_index": second_index, "kind": "line_gap", "detail": f"distance={endpoint_distance:.6f}"})
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
    resolved_overlaps = 0
    bridged_lines = 0
    for layer_path in _layer_paths(project_directory):
        collection = _read_collection(layer_path)
        source_features = collection.get("features", [])
        source_geometries = [shape(feature["geometry"]) for feature in source_features]
        output_features: list[dict[str, Any]] = []
        polygon_occupied = None
        line_geometries: list[LineString] = []
        line_properties: list[dict[str, Any]] = []
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
            if geometry.geom_type == "Polygon":
                if polygon_occupied is not None:
                    difference = geometry.difference(polygon_occupied)
                    if difference.area < geometry.area:
                        resolved_overlaps += 1
                    geometry = difference
                if not geometry.is_empty:
                    polygon_occupied = geometry if polygon_occupied is None else unary_union([polygon_occupied, geometry])
                    for part in _polygon_parts(geometry):
                        part_feature = dict(feature)
                        part_feature["geometry"] = json.loads(json.dumps(part.__geo_interface__))
                        output_features.append(part_feature)
                        cleaned_features += 1
            elif geometry.geom_type == "LineString":
                line_geometries.append(geometry)
                line_properties.append(feature.get("properties", {}))
            else:
                feature["geometry"] = json.loads(json.dumps(geometry.__geo_interface__))
                output_features.append(feature)
                cleaned_features += 1
        if line_geometries:
            merged_lines, bridges = _bridge_lines(line_geometries, snap_tolerance)
            bridged_lines += bridges
            for line in merged_lines:
                line_feature = {"type": "Feature", "geometry": json.loads(json.dumps(line.__geo_interface__)), "properties": line_properties[0] if line_properties else {}}
                output_features.append(line_feature)
                cleaned_features += 1
        collection["features"] = output_features
        layer_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    return {"project_id": project_id, "cleaned_features": cleaned_features, "removed_slivers": removed_slivers, "repaired_invalid": repaired_invalid, "resolved_overlaps": resolved_overlaps, "bridged_lines": bridged_lines, "validation": validate_project_topology(storage_root, project_id, sliver_area)}