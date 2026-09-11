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