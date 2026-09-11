from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import fitz
import pyvips

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
TILE_SIZE = 512
TILE_OVERLAP = 64
TILE_STEP = TILE_SIZE - TILE_OVERLAP


def _render_pdf(source_path: Path, raster_path: Path, page_number: int) -> None:
    with fitz.open(source_path) as document:
        if not document.page_count:
            raise ValueError("PDF does not contain any pages")
        if page_number < 0 or page_number >= document.page_count:
            raise ValueError("Requested PDF page is outside the document")
        page = document.load_page(page_number)
        page.get_pixmap(dpi=300, alpha=False).save(raster_path)


def _load_image(source_path: Path, raster_path: Path, page_number: int) -> pyvips.Image:
    if source_path.suffix.lower() == ".pdf":
        _render_pdf(source_path, raster_path, page_number)
        return pyvips.Image.new_from_file(str(raster_path), access="random")

    if source_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError("Supported formats are PDF, JPG, JPEG, PNG, TIF, and TIFF")

    return pyvips.Image.new_from_file(str(source_path), access="random")


def _save_master(image: pyvips.Image, raster_path: Path) -> None:
    if not raster_path.exists():
        image.write_to_file(str(raster_path), Q=95)


def _write_processing_tiles(image: pyvips.Image, tiles_directory: Path) -> int:
    tiles_directory.mkdir(parents=True, exist_ok=True)
    tile_count = 0

    for top in range(0, image.height, TILE_STEP):
        for left in range(0, image.width, TILE_STEP):
            width = min(TILE_SIZE, image.width - left)
            height = min(TILE_SIZE, image.height - top)
            image.crop(left, top, width, height).write_to_file(
                str(tiles_directory / f"{tile_count:06d}.jpg"),
                Q=90,
            )
            tile_count += 1
            if left + width == image.width:
                break
        if top + height == image.height:
            break

    return tile_count


def _deepzoom_tile_count(width: int, height: int) -> tuple[int, int]:
    max_level = math.ceil(math.log2(max(width, height)))
    tile_count = 0
    for level in range(max_level + 1):
        scale = 2 ** (max_level - level)
        level_width = max(1, math.ceil(width / scale))
        level_height = max(1, math.ceil(height / scale))
        columns = max(1, math.ceil((level_width - TILE_OVERLAP) / TILE_STEP))
        rows = max(1, math.ceil((level_height - TILE_OVERLAP) / TILE_STEP))
        tile_count += columns * rows
    return max_level + 1, tile_count


def _write_deepzoom(image: pyvips.Image, project_directory: Path) -> tuple[int, int]:
    image.dzsave(
        str(project_directory / "master"),
        tile_size=TILE_SIZE,
        overlap=TILE_OVERLAP,
        suffix=".jpg[Q=90]",
    )
    return _deepzoom_tile_count(image.width, image.height)


def ingest_document(
    project_id: str,
    source_path: str,
    storage_root: str,
    page_number: int = 0,
    source_filename: str | None = None,
) -> dict[str, Any]:
    source = Path(source_path)
    storage_directory = Path(storage_root)
    project_directory = storage_directory / project_id
    raster_directory = project_directory / "raster"
    tiles_directory = project_directory / "tiles"
    raster_directory.mkdir(parents=True, exist_ok=True)

    raster_path = raster_directory / "master.jpg"
    image = _load_image(source, raster_path, page_number)
    _save_master(image, raster_path)
    thumbnail_path = raster_directory / "thumbnail.jpg"
    image.thumbnail_image(1600, height=1600).write_to_file(str(thumbnail_path), Q=85)
    tile_count = _write_processing_tiles(image, tiles_directory)
    deepzoom_levels, deepzoom_tile_count = _write_deepzoom(image, project_directory)

    metadata = {
        "project_id": project_id,
        "source_filename": source_filename or source.name,
        "source_format": source.suffix.lower().lstrip("."),
        "page_number": page_number,
        "width": image.width,
        "height": image.height,
        "dpi": 300 if source.suffix.lower() == ".pdf" else None,
        "tile_size": TILE_SIZE,
        "tile_overlap": TILE_OVERLAP,
        "tile_count": tile_count,
        "deepzoom_levels": deepzoom_levels,
        "deepzoom_tile_count": deepzoom_tile_count,
        "master_raster": str(raster_path.relative_to(storage_directory)),
        "thumbnail": str(thumbnail_path.relative_to(storage_directory)),
        "tiles_directory": str(tiles_directory.relative_to(storage_directory)),
        "deepzoom_descriptor": str((project_directory / "master.dzi").relative_to(storage_directory)),
        "deepzoom_tiles_directory": str((project_directory / "master_files").relative_to(storage_directory)),
    }
    (project_directory / "ingestion.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
