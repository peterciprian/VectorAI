import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from app.vectorizer import polygonize_class
from app.line_vectorizer import vectorize_line_class


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


if __name__ == "__main__":
    unittest.main()
