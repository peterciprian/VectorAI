import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image

from app.ingestion import ingest_document


class IngestionTests(unittest.TestCase):
    def test_image_creates_master_thumbnail_tiles_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "plan.png"
            Image.new("RGB", (700, 700), "white").save(source)

            metadata = ingest_document("project_image", str(source), str(root / "projects"), source_filename="plan.png")
            project = root / "projects" / "project_image"

            self.assertEqual(metadata["source_filename"], "plan.png")
            self.assertEqual(metadata["tile_count"], 4)
            self.assertTrue((project / "raster" / "master.jpg").exists())
            self.assertTrue((project / "raster" / "thumbnail.jpg").exists())
            self.assertTrue((project / "tiles" / "000003.jpg").exists())
            self.assertTrue((project / "master.dzi").exists())
            self.assertGreater(metadata["deepzoom_levels"], 1)
            self.assertTrue((project / "ingestion.json").exists())

    def test_pdf_page_selection_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "plan.pdf"
            document = fitz.open()
            for color in ((1, 0, 0), (0, 1, 0)):
                page = document.new_page(width=32, height=32)
                page.draw_rect(fitz.Rect(0, 0, 32, 32), color=color, fill=color)
            document.save(source)
            document.close()

            metadata = ingest_document("project_pdf", str(source), str(root / "projects"), page_number=1)

            self.assertEqual(metadata["page_number"], 1)
            self.assertEqual(metadata["source_filename"], "plan.pdf")
            self.assertTrue((root / "projects" / "project_pdf" / "raster" / "master.jpg").exists())


if __name__ == "__main__":
    unittest.main()
