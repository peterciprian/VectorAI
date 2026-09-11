import unittest
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from app.legend import infer_class_code, infer_geometry_type, parse_legend


class LegendTests(unittest.TestCase):
    def test_geometry_rules_cover_polygon_line_and_point(self) -> None:
        self.assertEqual(infer_geometry_type("lakóterület", 80, 20), "Polygon")
        self.assertEqual(infer_geometry_type("szabályozási vonal", 120, 10), "LineString")
        self.assertEqual(infer_geometry_type("védett fa", 20, 20), "Point")

    def test_class_code_is_extracted_with_fallback(self) -> None:
        self.assertEqual(infer_class_code("Lk-1 kisvárosias lakóterület", 1), "Lk-1")
        self.assertEqual(infer_class_code("ismeretlen kategória", 4), "CLASS-04")

    def test_generated_municipal_legend_fixture_produces_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "municipal_plan.png"
            image = Image.new("RGB", (800, 500), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((40, 340, 760, 470), outline="black", width=2)
            rows = [("Lk-1 lakóterület", "#88bb77"), ("Szabályozási vonal", "#dd6655"), ("Védett fa", "#5577aa")]
            for index, (label, color) in enumerate(rows):
                top = 355 + index * 35
                draw.rectangle((60, top, 110, top + 22), fill=color)
                draw.text((130, top + 2), label, fill="black")
            image.save(source)

            registry = parse_legend(str(source), "fixture_project", str(root / "projects"), [30, 330, 770, 480])

            self.assertEqual(registry["project_id"], "fixture_project")
            self.assertEqual(registry["legend_bbox"], [30, 330, 770, 480])
            self.assertIn("items", registry)
            self.assertTrue((root / "projects" / "fixture_project" / "legend" / "registry.json").exists())


if __name__ == "__main__":
    unittest.main()
