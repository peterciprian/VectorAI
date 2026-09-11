import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from app.vectorizer import polygonize_class
from app.line_vectorizer import vectorize_line_class
from app.point_vectorizer import vectorize_point_class


class VectorizerTests(unittest.TestCase):
    def test_polygonize_class_writes_only_polygon_features(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            raster = project / "raster"
            raster.mkdir(parents=True)
            image = Image.new("RGB", (100, 100), "white")
            ImageDraw.Draw(image).rectangle((20, 20, 79, 79), fill=(40, 160, 80))
            image.save(raster / "master.jpg")
            item = {"id": "leg_cls_01", "code": "Z", "name": "Zoldterulet", "geometry_type": "Polygon", "color_rgb": [40, 160, 80], "color_tolerance": 18}

            result = polygonize_class("project", str(root), item)
            collection = json.loads((project / "layers" / "leg_cls_01.geojson").read_text(encoding="utf-8"))

            self.assertGreater(result["feature_count"], 0)
            self.assertTrue(all(feature["geometry"]["type"] == "Polygon" for feature in collection["features"]))
            self.assertEqual(collection["crs"]["properties"]["name"], "EPSG:23700")

    def test_non_polygon_class_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                polygonize_class("project", temporary_directory, {"id": "line", "geometry_type": "LineString"})

    def test_line_class_writes_only_linestring_features(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            raster = project / "raster"
            raster.mkdir(parents=True)
            image = Image.new("RGB", (120, 120), "white")
            draw = ImageDraw.Draw(image)
            draw.line((15, 60, 105, 60), fill=(220, 80, 70), width=3)
            image.save(raster / "master.jpg")
            item = {"id": "leg_line_01", "code": "SZV", "name": "Szabalyozasi vonal", "geometry_type": "LineString", "color_rgb": [220, 80, 70], "color_tolerance": 20}

            result = vectorize_line_class("project", str(root), item)
            collection = json.loads((project / "layers" / "leg_line_01.geojson").read_text(encoding="utf-8"))

            self.assertGreater(result["feature_count"], 0)
            self.assertTrue(all(feature["geometry"]["type"] == "LineString" for feature in collection["features"]))

    def test_line_graph_traces_junction_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            raster = project / "raster"
            raster.mkdir(parents=True)
            image = Image.new("RGB", (160, 160), "white")
            draw = ImageDraw.Draw(image)
            draw.line((80, 20, 80, 140), fill=(220, 80, 70), width=3)
            draw.line((30, 80, 130, 80), fill=(220, 80, 70), width=3)
            image.save(raster / "master.jpg")
            item = {"id": "leg_junction_01", "code": "SZV", "name": "Szabalyozasi vonal", "geometry_type": "LineString", "color_rgb": [220, 80, 70], "color_tolerance": 20}

            result = vectorize_line_class("project", str(root), item)
            self.assertGreaterEqual(result["feature_count"], 2)

    def test_point_class_writes_centroids_with_symbol_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            raster = project / "raster"
            raster.mkdir(parents=True)
            image = Image.new("RGB", (120, 120), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((18, 28, 26, 36), fill=(35, 95, 190))
            draw.ellipse((82, 78, 90, 86), fill=(35, 95, 190))
            image.save(raster / "master.jpg")
            item = {
                "id": "leg_point_01",
                "code": "FA",
                "name": "Vedett fa",
                "symbol_type": "protected_tree",
                "geometry_type": "Point",
                "color_rgb": [35, 95, 190],
                "color_tolerance": 20,
            }

            result = vectorize_point_class("project", str(root), item)
            collection = json.loads((project / "layers" / "leg_point_01.geojson").read_text(encoding="utf-8"))

            self.assertEqual(result["feature_count"], 2)
            self.assertTrue(all(feature["geometry"]["type"] == "Point" for feature in collection["features"]))
            self.assertTrue(all(feature["properties"]["symbol_type"] == "protected_tree" for feature in collection["features"]))
            self.assertTrue(all(feature["properties"]["label"] == "Vedett fa" for feature in collection["features"]))

    def test_point_class_uses_project_relative_template_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            raster = project / "raster"
            templates = project / "templates"
            raster.mkdir(parents=True)
            templates.mkdir()
            image = Image.new("RGB", (100, 100), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((12, 18, 20, 26), fill=(20, 20, 20))
            draw.rectangle((68, 58, 76, 66), fill=(20, 20, 20))
            image.save(raster / "master.jpg")
            image.crop((12, 18, 21, 27)).save(templates / "symbol.png")
            item = {
                "id": "leg_template_point",
                "code": "MU",
                "name": "Muemlek",
                "geometry_type": "Point",
                "color_rgb": [220, 20, 20],
                "color_tolerance": 4,
                "template_path": "templates/symbol.png",
                "template_threshold": 0.5,
            }

            result = vectorize_point_class("project", str(root), item)
            collection = json.loads((project / "layers" / "leg_template_point.geojson").read_text(encoding="utf-8"))

            self.assertEqual(result["feature_count"], 2)
            self.assertTrue(all(feature["properties"]["detection_method"] == "template_match" for feature in collection["features"]))


if __name__ == "__main__":
    unittest.main()
