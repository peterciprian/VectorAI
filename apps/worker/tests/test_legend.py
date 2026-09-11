import unittest

from app.legend import infer_class_code, infer_geometry_type


class LegendTests(unittest.TestCase):
    def test_geometry_rules_cover_polygon_line_and_point(self) -> None:
        self.assertEqual(infer_geometry_type("lakóterület", 80, 20), "Polygon")
        self.assertEqual(infer_geometry_type("szabályozási vonal", 120, 10), "LineString")
        self.assertEqual(infer_geometry_type("védett fa", 20, 20), "Point")

    def test_class_code_is_extracted_with_fallback(self) -> None:
        self.assertEqual(infer_class_code("Lk-1 kisvárosias lakóterület", 1), "Lk-1")
        self.assertEqual(infer_class_code("ismeretlen kategória", 4), "CLASS-04")


if __name__ == "__main__":
    unittest.main()
