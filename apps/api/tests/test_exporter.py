import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.main import export_shapefile
from app.exporter import EOV_WKT, export_project_shapefiles


class ExporterTests(unittest.TestCase):
    def test_export_writes_strict_components_and_sanitized_utf8_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            (project / "legend").mkdir(parents=True)
            layers = project / "layers"
            layers.mkdir()
            (project / "legend" / "registry.json").write_text(json.dumps({"items": [{"id": "class_1", "code": "Védett fa", "name": "Védett fa", "geometry_type": "Point", "enabled": True}]}), encoding="utf-8")
            (layers / "class_1.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [650000, 230000]}, "properties": {"symbol_type": "protected_tree", "label": "Árvíz"}}]}), encoding="utf-8")

            archive_path = export_project_shapefiles("project", str(root))

            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
                self.assertTrue({"VEDETT_FA.shp", "VEDETT_FA.shx", "VEDETT_FA.dbf", "VEDETT_FA.prj", "VEDETT_FA.cpg", "metadata.json", "README.txt"}.issubset(names))
                self.assertEqual(archive.read("VEDETT_FA.prj").decode("utf-8"), EOV_WKT)
                self.assertEqual(archive.read("VEDETT_FA.cpg").decode("ascii").strip(), "UTF-8")

    def test_export_rejects_mixed_geometry_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            (project / "legend").mkdir(parents=True)
            (project / "layers").mkdir()
            (project / "legend" / "registry.json").write_text(json.dumps({"items": [{"id": "mixed", "code": "MIX", "name": "Mixed", "geometry_type": "Point", "enabled": True}]}), encoding="utf-8")
            (project / "layers" / "mixed.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 2]}, "properties": {}}, {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1, 2], [3, 4]]}, "properties": {}}]}), encoding="utf-8")

            with self.assertRaises(ValueError):
                export_project_shapefiles("project", str(root))

    def test_export_download_endpoint_returns_generated_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            (project / "legend").mkdir(parents=True)
            (project / "layers").mkdir()
            (project / "legend" / "registry.json").write_text(json.dumps({"items": [{"id": "points", "code": "PTS", "name": "Points", "geometry_type": "Point", "enabled": True}]}), encoding="utf-8")
            (project / "layers" / "points.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [650000, 230000]}, "properties": {"label": "Test"}}]}), encoding="utf-8")

            with patch("app.main.storage_root", root):
                response = export_shapefile("project")

            self.assertEqual(response.media_type, "application/zip")
            self.assertEqual(response.filename, "export_project_project.zip")
            self.assertTrue(Path(response.path).exists())

    def test_export_download_endpoint_blocks_invalid_topology(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            (project / "legend").mkdir(parents=True)
            layer = project / "layers"
            layer.mkdir()
            (project / "legend" / "registry.json").write_text(json.dumps({"items": [{"id": "zones", "code": "Z", "name": "Zones", "geometry_type": "Polygon", "enabled": True}]}), encoding="utf-8")
            (layer / "zones.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}, "properties": {}}, {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]}, "properties": {}}]}), encoding="utf-8")

            with patch("app.main.storage_root", root), self.assertRaises(HTTPException) as context:
                export_shapefile("project")

            self.assertEqual(context.exception.status_code, 422)