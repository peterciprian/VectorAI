import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

from app.georef import calculate_affine, georeference_raster


class GeoreferencingTests(unittest.TestCase):
    def test_affine_transform_returns_zero_rmse_for_exact_gcps(self) -> None:
        gcps = [
            {"id": "gcp_1", "pixel_x": 0, "pixel_y": 0, "map_x": 100, "map_y": 200},
            {"id": "gcp_2", "pixel_x": 10, "pixel_y": 0, "map_x": 120, "map_y": 200},
            {"id": "gcp_3", "pixel_x": 0, "pixel_y": 10, "map_x": 100, "map_y": 230},
        ]

        transform, residuals, rmse = calculate_affine(gcps)

        self.assertAlmostEqual(transform.c, 100)
        self.assertAlmostEqual(transform.a, 2)
        self.assertAlmostEqual(transform.b, 0)
        self.assertAlmostEqual(transform.f, 200)
        self.assertAlmostEqual(transform.d, 0)
        self.assertAlmostEqual(transform.e, 3)
        self.assertAlmostEqual(rmse, 0)
        self.assertTrue(all(abs(item["residual_m"]) < 1e-9 for item in residuals))

    def test_georeference_raster_writes_eov_geotiff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_path = root / "master.jpg"
            output_path = root / "georef" / "warped_eov.tif"
            with rasterio.open(
                source_path,
                "w",
                driver="GTiff",
                width=10,
                height=10,
                count=1,
                dtype="uint8",
                crs=None,
                transform=Affine.identity(),
            ) as source:
                source.write(np.zeros((1, 10, 10), dtype=np.uint8))

            metadata = georeference_raster(
                str(source_path),
                str(output_path),
                [
                    {"id": "gcp_1", "pixel_x": 0, "pixel_y": 0, "map_x": 100, "map_y": 200},
                    {"id": "gcp_2", "pixel_x": 10, "pixel_y": 0, "map_x": 120, "map_y": 200},
                    {"id": "gcp_3", "pixel_x": 0, "pixel_y": 10, "map_x": 100, "map_y": 230},
                ],
            )

            self.assertEqual(metadata["target_crs"], "EPSG:23700")
            self.assertEqual(metadata["driver"], "COG")
            self.assertTrue(output_path.exists())
            with rasterio.open(output_path) as warped:
                self.assertEqual(warped.crs.to_string(), "EPSG:23700")
                self.assertEqual(warped.driver, "GTiff")
                self.assertAlmostEqual(warped.transform.c, 100)
                self.assertAlmostEqual(warped.transform.f, 230)


if __name__ == "__main__":
    unittest.main()
