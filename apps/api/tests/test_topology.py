import json
import tempfile
import unittest
from pathlib import Path

from app.topology import clean_project_topology, validate_project_topology


class TopologyTests(unittest.TestCase):
    def test_validation_flags_polygon_overlap_and_sliver(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            layer = root / "project" / "layers"
            layer.mkdir(parents=True)
            collection = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}, "properties": {}},
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]}, "properties": {}},
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[5, 5], [5.5, 5], [5.5, 5.5], [5, 5.5], [5, 5]]]}, "properties": {}},
            ]}
            (layer / "zones.geojson").write_text(json.dumps(collection), encoding="utf-8")

            result = validate_project_topology(str(root), "project")

            self.assertFalse(result["valid"])
            self.assertEqual(result["checked_features"], 3)
            self.assertIn("overlap", {issue["kind"] for issue in result["issues"]})
            self.assertIn("sliver", {issue["kind"] for issue in result["issues"]})

    def test_clean_removes_sliver_and_revalidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            layer = root / "project" / "layers"
            layer.mkdir(parents=True)
            collection = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5], [0, 0]]]}, "properties": {}}]}
            (layer / "zones.geojson").write_text(json.dumps(collection), encoding="utf-8")

            result = clean_project_topology(str(root), "project")

            self.assertEqual(result["removed_slivers"], 1)
            self.assertTrue(result["validation"]["valid"])

    def test_clean_partitions_overlapping_polygons(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            layer = root / "project" / "layers"
            layer.mkdir(parents=True)
            collection = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}, "properties": {"rank": 1}},
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]}, "properties": {"rank": 2}},
            ]}
            (layer / "zones.geojson").write_text(json.dumps(collection), encoding="utf-8")

            result = clean_project_topology(str(root), "project", sliver_area=0.01)

            self.assertEqual(result["resolved_overlaps"], 1)
            self.assertTrue(result["validation"]["valid"])

    def test_clean_bridges_nearby_line_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            layer = root / "project" / "layers"
            layer.mkdir(parents=True)
            collection = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]}, "properties": {}},
                {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1.1, 0], [2, 0]]}, "properties": {}},
            ]}
            (layer / "roads.geojson").write_text(json.dumps(collection), encoding="utf-8")

            result = clean_project_topology(str(root), "project", snap_tolerance=0.2)
            saved = json.loads((layer / "roads.geojson").read_text(encoding="utf-8"))

            self.assertEqual(result["bridged_lines"], 1)
            self.assertEqual(len(saved["features"]), 1)

    def test_validation_flags_nearby_line_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            layer = root / "project" / "layers"
            layer.mkdir(parents=True)
            collection = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]}, "properties": {}},
                {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1.1, 0], [2, 0]]}, "properties": {}},
            ]}
            (layer / "roads.geojson").write_text(json.dumps(collection), encoding="utf-8")

            result = validate_project_topology(str(root), "project", gap_distance=0.2)

            self.assertIn("line_gap", {issue["kind"] for issue in result["issues"]})

    def test_cleaned_line_preserves_provenance_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            layer = root / "project" / "layers"
            layer.mkdir(parents=True)
            collection = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]}, "properties": {"code": "A"}},
                {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1.1, 0], [2, 0]]}, "properties": {"code": "B"}},
            ]}
            (layer / "roads.geojson").write_text(json.dumps(collection), encoding="utf-8")

            clean_project_topology(str(root), "project", snap_tolerance=0.2)
            saved = json.loads((layer / "roads.geojson").read_text(encoding="utf-8"))

            self.assertEqual(saved["features"][0]["properties"]["code"], "A")
            self.assertEqual(saved["features"][0]["properties"]["merged_feature_count"], 2)