from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import rasterio.shutil
from affine import Affine
from rasterio.control import GroundControlPoint
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import calculate_default_transform, reproject

TARGET_CRS = "EPSG:23700"


def recommend_transform_method(gcp_count: int) -> str:
    if gcp_count < 3:
        raise ValueError("At least 3 GCPs are required")
    if gcp_count <= 5:
        return "affine"
    if gcp_count <= 9:
        return "polynomial"
    return "tps"


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
    residual_details = []
    for index, (point, residual, predicted_easting, predicted_northing) in enumerate(zip(gcps, residuals, predicted_eastings, predicted_northings, strict=True)):
        residual_details.append({
            "id": point.get("id", f"gcp_{index + 1}"),
            "residual_m": float(residual),
            "actual_map_x": float(eastings[index]),
            "actual_map_y": float(northings[index]),
            "predicted_map_x": float(predicted_easting),
            "predicted_map_y": float(predicted_northing),
        })
    transform = Affine(
        float(east_coefficients[1]),
        float(east_coefficients[2]),
        float(east_coefficients[0]),
        float(north_coefficients[1]),
        float(north_coefficients[2]),
        float(north_coefficients[0]),
    )
    return transform, residual_details, rmse


def _fit_model(gcps: list[dict[str, Any]], method: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    validate_gcps(gcps)
    pixels, eastings, northings = _coordinates(gcps)
    if method == "polynomial":
        if len(gcps) < 6:
            raise ValueError("Second-order polynomial transformation requires at least 6 GCPs")
        design = np.column_stack((np.ones(len(gcps)), pixels[:, 0], pixels[:, 1], pixels[:, 0] ** 2, pixels[:, 0] * pixels[:, 1], pixels[:, 1] ** 2))
        basis = design
    elif method == "tps":
        if len(gcps) < 10:
            raise ValueError("TPS transformation requires at least 10 GCPs")
        distances = np.linalg.norm(pixels[:, None, :] - pixels[None, :, :], axis=2)
        kernel = np.zeros_like(distances)
        nonzero = distances > 0
        kernel[nonzero] = distances[nonzero] ** 2 * np.log(distances[nonzero] ** 2)
        basis = np.block([[kernel, np.ones((len(gcps), 1)), pixels], [np.ones((1, len(gcps))), np.zeros((1, 3))]])
        eastings = np.concatenate((eastings, [0]))
        northings = np.concatenate((northings, [0]))
    else:
        raise ValueError(f"Unsupported transformation method: {method}")
    east_coefficients = np.linalg.lstsq(basis, eastings, rcond=None)[0]
    north_coefficients = np.linalg.lstsq(basis, northings, rcond=None)[0]
    predicted_eastings = basis @ east_coefficients
    predicted_northings = basis @ north_coefficients
    residuals = np.hypot(eastings - predicted_eastings, northings - predicted_northings)
    return pixels, east_coefficients, north_coefficients, float(np.sqrt(np.mean(residuals[:-1] ** 2)) if method == "tps" else np.sqrt(np.mean(residuals ** 2)))


def calculate_nonlinear(gcps: list[dict[str, Any]], method: str) -> tuple[list[dict[str, Any]], float]:
    pixels, east_coefficients, north_coefficients, rmse = _fit_model(gcps, method)
    source_pixels, eastings, northings = _coordinates(gcps)
    if method == "polynomial":
        basis = np.column_stack((np.ones(len(gcps)), source_pixels[:, 0], source_pixels[:, 1], source_pixels[:, 0] ** 2, source_pixels[:, 0] * source_pixels[:, 1], source_pixels[:, 1] ** 2))
    else:
        distances = np.linalg.norm(source_pixels[:, None, :] - source_pixels[None, :, :], axis=2)
        kernel = np.zeros_like(distances)
        nonzero = distances > 0
        kernel[nonzero] = distances[nonzero] ** 2 * np.log(distances[nonzero] ** 2)
        basis = np.block([[kernel, np.ones((len(gcps), 1)), source_pixels], [np.ones((1, len(gcps))), np.zeros((1, 3))]])
        basis = basis[:-1]
    residual_values = np.hypot(eastings - basis @ east_coefficients, northings - basis @ north_coefficients)
    residuals = [{"id": point.get("id", f"gcp_{index + 1}"), "residual_m": float(residual), "actual_map_x": float(eastings[index]), "actual_map_y": float(northings[index]), "predicted_map_x": float((basis @ east_coefficients)[index]), "predicted_map_y": float((basis @ north_coefficients)[index])} for index, (point, residual) in enumerate(zip(gcps, residual_values, strict=True))]
    return residuals, rmse


def georeference_raster(
    input_path: str,
    output_path: str,
    gcps: list[dict[str, Any]],
    target_crs: str = TARGET_CRS,
    method: str = "auto",
) -> dict[str, Any]:
    if target_crs != TARGET_CRS:
        raise ValueError(f"Only {TARGET_CRS} is supported for the initial affine georeferencer")

    selected_method = recommend_transform_method(len(gcps)) if method == "auto" else method
    if selected_method == "affine":
        transform, residuals, rmse = calculate_affine(gcps)
    else:
        residuals, rmse = calculate_nonlinear(gcps, selected_method)
        transform, _, _ = calculate_affine(gcps)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(".tmp.tif")
    with rasterio.open(input_path) as source:
        pixel_width, pixel_height = validate_gcps(gcps).values()
        warnings: list[str] = []
        if pixel_width < source.width * 0.25 or pixel_height < source.height * 0.25:
            warnings.append("GCPs cover less than 25% of the source raster extent")
        if max((item["residual_m"] for item in residuals), default=0) > 2:
            warnings.append("At least one GCP residual exceeds 2 meters")
        _, eastings, northings = _coordinates(gcps)
        if selected_method == "affine":
            source_bounds = rasterio.transform.array_bounds(source.height, source.width, transform)
            left, bottom, right, top = source_bounds
            destination_transform, destination_width, destination_height = calculate_default_transform(
                target_crs, target_crs, source.width, source.height,
                left=left, bottom=bottom, right=right, top=top,
                resolution=(abs(transform.a), abs(transform.e)),
            )
            control_points = None
        else:
            left, right = float(eastings.min()), float(eastings.max())
            bottom, top = float(northings.min()), float(northings.max())
            destination_width, destination_height = source.width, source.height
            destination_transform = from_origin(left, top, max((right - left) / source.width, 1e-9), max((top - bottom) / source.height, 1e-9))
            control_points = [GroundControlPoint(row=point["pixel_y"], col=point["pixel_x"], x=point["map_x"], y=point["map_y"]) for point in gcps]
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
        with rasterio.open(temporary_output, "w", **profile) as destination:
            for band_index in range(1, source.count + 1):
                source_band = source.read(band_index) if control_points is not None else rasterio.band(source, band_index)
                reproject(
                    source=source_band,
                    destination=rasterio.band(destination, band_index),
                    src_transform=transform if control_points is None else None,
                    gcps=control_points,
                    src_crs=target_crs,
                    dst_transform=destination_transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )
            if destination_width >= 32 and destination_height >= 32:
                overview_levels = [level for level in (2, 4, 8, 16) if destination_width // level >= 1 and destination_height // level >= 1]
                destination.build_overviews(overview_levels, Resampling.average)
                destination.update_tags(ns="rio_overview", resampling="average")
    rasterio.shutil.copy(
        temporary_output,
        output,
        driver="COG",
        compress="DEFLATE",
        blocksize=512,
        overview_resampling="AVERAGE",
    )
    temporary_output.unlink(missing_ok=True)

    return {
        "target_crs": target_crs,
        "transform_method": selected_method,
        "recommended_method": recommend_transform_method(len(gcps)),
        "transform": [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f],
        "rmse_m": rmse,
        "residuals": residuals,
        "warnings": warnings,
        "output_path": str(output),
        "driver": "COG",
    }


def write_georef_metadata(path: str, metadata: dict[str, Any]) -> None:
    metadata_path = Path(path)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
