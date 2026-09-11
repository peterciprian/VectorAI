from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from affine import Affine
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

TARGET_CRS = "EPSG:23700"


def _coordinates(gcps: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pixels = np.array([[point["pixel_x"], point["pixel_y"]] for point in gcps], dtype=float)
    eastings = np.array([point["map_x"] for point in gcps], dtype=float)
    northings = np.array([point["map_y"] for point in gcps], dtype=float)
    return pixels, eastings, northings


def validate_gcps(gcps: list[dict[str, Any]]) -> dict[str, Any]:
    if len(gcps) < 3:
        raise ValueError("Affine georeferencing requires at least 3 GCPs")

    pixels, eastings, northings = _coordinates(gcps)
    if not np.isfinite(pixels).all() or not np.isfinite(eastings).all() or not np.isfinite(northings).all():
        raise ValueError("GCP coordinates must be finite numbers")
    if len({(row[0], row[1]) for row in pixels}) != len(gcps):
        raise ValueError("GCP pixel coordinates must be unique")
    if np.linalg.matrix_rank(np.column_stack((np.ones(len(gcps)), pixels))) < 3:
        raise ValueError("GCP pixel coordinates must not be collinear")
    return {"pixel_width": float(pixels[:, 0].max() - pixels[:, 0].min()), "pixel_height": float(pixels[:, 1].max() - pixels[:, 1].min())}


def calculate_affine(gcps: list[dict[str, Any]]) -> tuple[Affine, list[dict[str, Any]], float]:
    validate_gcps(gcps)
    pixels, eastings, northings = _coordinates(gcps)
    design = np.column_stack((np.ones(len(gcps)), pixels))
    east_coefficients, *_ = np.linalg.lstsq(design, eastings, rcond=None)
    north_coefficients, *_ = np.linalg.lstsq(design, northings, rcond=None)
    predicted_eastings = design @ east_coefficients
    predicted_northings = design @ north_coefficients
    residuals = np.hypot(eastings - predicted_eastings, northings - predicted_northings)
    rmse = float(np.sqrt(np.mean(residuals**2)))
    residual_details = [
        {"id": point.get("id", f"gcp_{index + 1}"), "residual_m": float(residual)}
        for index, (point, residual) in enumerate(zip(gcps, residuals, strict=True))
    ]
    transform = Affine(
        float(east_coefficients[1]),
        float(east_coefficients[2]),
        float(east_coefficients[0]),
        float(north_coefficients[1]),
        float(north_coefficients[2]),
        float(north_coefficients[0]),
    )
    return transform, residual_details, rmse


def georeference_raster(
    input_path: str,
    output_path: str,
    gcps: list[dict[str, Any]],
    target_crs: str = TARGET_CRS,
) -> dict[str, Any]:
    if target_crs != TARGET_CRS:
        raise ValueError(f"Only {TARGET_CRS} is supported for the initial affine georeferencer")

    transform, residuals, rmse = calculate_affine(gcps)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(input_path) as source:
        source_bounds = rasterio.transform.array_bounds(source.height, source.width, transform)
        left, bottom, right, top = source_bounds
        destination_transform, destination_width, destination_height = calculate_default_transform(
            target_crs,
            target_crs,
            source.width,
            source.height,
            left=left,
            bottom=bottom,
            right=right,
            top=top,
            resolution=(abs(transform.a), abs(transform.e)),
        )
        profile = source.profile.copy()
        profile.update(
            driver="GTiff",
            crs=target_crs,
            transform=destination_transform,
            width=destination_width,
            height=destination_height,
            compress="deflate",
            tiled=destination_width >= 16 and destination_height >= 16,
            BIGTIFF="IF_SAFER",
        )
        if profile["tiled"]:
            profile.update(blockxsize=256, blockysize=256)
        with rasterio.open(output, "w", **profile) as destination:
            for band_index in range(1, source.count + 1):
                reproject(
                    source=rasterio.band(source, band_index),
                    destination=rasterio.band(destination, band_index),
                    src_transform=transform,
                    src_crs=target_crs,
                    dst_transform=destination_transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )
            if destination_width >= 32 and destination_height >= 32:
                overview_levels = [level for level in (2, 4, 8, 16) if destination_width // level >= 1 and destination_height // level >= 1]
                destination.build_overviews(overview_levels, Resampling.average)
                destination.update_tags(ns="rio_overview", resampling="average")

    return {
        "target_crs": target_crs,
        "transform_method": "affine",
        "transform": [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f],
        "rmse_m": rmse,
        "residuals": residuals,
        "output_path": str(output),
    }


def write_georef_metadata(path: str, metadata: dict[str, Any]) -> None:
    metadata_path = Path(path)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
