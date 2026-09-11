from __future__ import annotations

import json
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

import shapefile


EOV_WKT = 'PROJCS["HD72 / EOV",GEOGCS["HD72",DATUM["Hungarian_Datum_1972",SPHEROID["GRS 1967",6378160,298.247167427,AUTHORITY["EPSG","7036"]],TOWGS84[52.17,-71.82,-14.9,0,0,0,0],AUTHORITY["EPSG","6237"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4237"]],PROJECTION["Hotine_Oblique_Mercator_Hungarian_Azimuthal_Centre"],PARAMETER["latitude_of_center",47.1443937222222],PARAMETER["longitude_of_center",19.0485717777778],PARAMETER["azimuth",90],PARAMETER["rectified_grid_angle",90],PARAMETER["scale_factor",0.99993],PARAMETER["false_easting",650000],PARAMETER["false_northing",200000],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","23700"]]'

GEOMETRY_TYPES = {"Polygon": shapefile.POLYGON, "LineString": shapefile.POLYLINE, "Point": shapefile.POINT}


def _safe_name(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", normalized).strip("_").upper()
    return (normalized or fallback)[:10]


def _field_names(features: list[dict[str, Any]]) -> list[tuple[str, str, int, int]]:
    names: list[str] = []
    for feature in features:
        for key in feature.get("properties", {}):
            candidate = _safe_name(str(key), "FIELD")
            if candidate not in names:
                names.append(candidate)
    if not names:
        names.append("VAI_ID")
    return [(name, "C", 254, 0) for name in names]


def _write_shape(writer: shapefile.Writer, geometry_type: str, geometry: dict[str, Any]) -> None:
    if geometry.get("type") != geometry_type:
        raise ValueError(f"Mixed or unexpected geometry: expected {geometry_type}, got {geometry.get('type')}")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        writer.point(*coordinates)
    elif geometry_type == "LineString":
        writer.line([coordinates])
    else:
        writer.poly(coordinates)


def export_project_shapefiles(project_id: str, storage_root: str) -> Path:
    project_directory = Path(storage_root) / project_id
    registry_path = project_directory / "legend" / "registry.json"
    if not registry_path.exists():
        raise FileNotFoundError("Legend registry is not ready")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    export_directory = project_directory / "exports" / "shapefile"
    export_directory.mkdir(parents=True, exist_ok=True)
    for existing in export_directory.iterdir():
        if existing.is_file():
            existing.unlink()
    exported_layers: list[str] = []
    for item in registry.get("items", []):
        if not item.get("enabled", True):
            continue
        layer_id = Path(str(item.get("id", ""))).name
        layer_path = project_directory / "layers" / f"{layer_id}.geojson"
        if not layer_path.exists():
            continue
        geometry_type = str(item.get("geometry_type", ""))
        if geometry_type not in GEOMETRY_TYPES:
            raise ValueError(f"Unsupported geometry type: {geometry_type}")
        collection = json.loads(layer_path.read_text(encoding="utf-8"))
        features = collection.get("features", [])
        for feature in features:
            if feature.get("geometry", {}).get("type") != geometry_type:
                raise ValueError(f"Mixed or unexpected geometry: expected {geometry_type}, got {feature.get('geometry', {}).get('type')}")
        base_name = _safe_name(str(item.get("code") or layer_id), "LAYER")
        writer = shapefile.Writer(str(export_directory / base_name), shapeType=GEOMETRY_TYPES[geometry_type], encoding="utf-8")
        fields = _field_names(features)
        for name, field_type, size, decimal in fields:
            writer.field(name, field_type, size=size, decimal=decimal)
        field_keys = [key for feature in features for key in feature.get("properties", {})]
        field_keys = list(dict.fromkeys(field_keys))
        for feature in features:
            _write_shape(writer, geometry_type, feature["geometry"])
            properties = feature.get("properties", {})
            values = [str(properties.get(key, ""))[:254] for key in field_keys]
            if not field_keys:
                values = [str(len(exported_layers) + 1)]
            writer.record(*values)
        writer.close()
        (export_directory / f"{base_name}.prj").write_text(EOV_WKT, encoding="utf-8")
        (export_directory / f"{base_name}.cpg").write_text("UTF-8\n", encoding="ascii")
        exported_layers.append(base_name)
    metadata = {"project_id": project_id, "crs": "EPSG:23700", "layers": exported_layers}
    (export_directory / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (export_directory / "README.txt").write_text("VectoryAI Shapefile export\nCRS: EPSG:23700 (Hungarian EOV)\n", encoding="utf-8")
    archive_path = project_directory / "exports" / f"export_project_{project_id}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in export_directory.iterdir():
            archive.write(path, path.name)
    return archive_path