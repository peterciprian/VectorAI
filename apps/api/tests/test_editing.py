import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.main import FeatureCollectionRequest, update_vector_layer


class EditingTests(unittest.TestCase):
    def _project(self, root: Path) -> Path:
        project = root / "project"
        (project / "legend").mkdir(parents=True)
        (project / "layers").mkdir()
        (project / "legend" / "registry.json").write_text(json.dumps({"items": [{"id": "line", "code": "L", "name": "Line", "geometry_type": "LineString", "enabled": True}]}), encoding="utf-8")
        (project / "layers" / "line.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
        return project

    def test_update_layer_replaces_geojson_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = self._project(root)
            request = FeatureCollectionRequest(type="FeatureCollection", features=[{"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1, 2], [5, 6]]}, "properties": {"label": "edited"}}])

            with patch("app.main.storage_root", root), patch("app.main._database_url", return_value=None):
                result = update_vector_layer("project", "line", request)

            self.assertEqual(result["updated_features"], 1)
            saved = json.loads((project / "layers" / "line.geojson").read_text(encoding="utf-8"))
            self.assertEqual(saved["features"][0]["properties"]["label"], "edited")

    def test_update_layer_rejects_mixed_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            request = FeatureCollectionRequest(type="FeatureCollection", features=[{"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 2]}, "properties": {}}])

            with patch("app.main.storage_root", root), self.assertRaises(HTTPException) as context:
                update_vector_layer("project", "line", request)

            self.assertEqual(context.exception.status_code, 422)