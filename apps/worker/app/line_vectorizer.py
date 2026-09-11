from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from affine import Affine
from shapely.geometry import LineString
from shapely.validation import explain_validity
import networkx as nx
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


def _skeleton_graph(skeleton: np.ndarray) -> nx.Graph:
    graph = nx.Graph()
    pixels = [tuple(int(value) for value in point) for point in np.argwhere(skeleton)]
    pixel_set = set(pixels)
    for row, column in pixels:
        graph.add_node((row, column))
        for row_offset in (-1, 0, 1):
            for column_offset in (-1, 0, 1):
                neighbor = (row + row_offset, column + column_offset)
                if neighbor != (row, column) and neighbor in pixel_set:
                    graph.add_edge((row, column), neighbor, weight=1.4142 if row_offset and column_offset else 1.0)
    return graph


def _trace_paths(graph: nx.Graph, min_pixels: int = 8) -> list[list[tuple[int, int]]]:
    special_nodes = {node for node, degree in graph.degree() if degree != 2}
    used_edges: set[frozenset[tuple[int, int]]] = set()
    paths: list[list[tuple[int, int]]] = []

    def edge_key(first: tuple[int, int], second: tuple[int, int]) -> frozenset[tuple[int, int]]:
        return frozenset((first, second))

    def trace(first: tuple[int, int], second: tuple[int, int]) -> list[tuple[int, int]]:
        path = [first, second]
        previous, current = first, second
        used_edges.add(edge_key(previous, current))
        while current not in special_nodes:
            candidates = [node for node in graph.neighbors(current) if node != previous and edge_key(current, node) not in used_edges]
            if not candidates:
                break
            next_node = candidates[0]
            used_edges.add(edge_key(current, next_node))
            path.append(next_node)
            previous, current = current, next_node
        return path

    for node in special_nodes:
        for neighbor in graph.neighbors(node):
            if edge_key(node, neighbor) not in used_edges:
                path = trace(node, neighbor)
                if len(path) >= min_pixels:
                    paths.append(path)

    for first, second in graph.edges():
        if edge_key(first, second) in used_edges:
            continue
        path = trace(first, second)
        if len(path) >= min_pixels:
            paths.append(path)
    return paths


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
    graph = _skeleton_graph(skeleton)
    paths = _trace_paths(graph)
    transform = _pixel_line_transform(project_directory)
    features: list[dict[str, Any]] = []
    for path in paths:
        if len(path) < 2:
            continue
        map_coordinates = [transform * (float(column), float(row)) for row, column in path]
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
