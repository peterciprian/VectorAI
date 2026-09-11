from datetime import datetime, timezone
import os
import json
import shutil
import asyncio
import asyncpg
from pathlib import Path
from uuid import uuid4

from celery import Celery
import fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel, Field

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
storage_root = Path(os.getenv("STORAGE_ROOT", "/storage/projects"))
celery_client = Celery("vectoryai-api", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
allowed_suffixes = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
reference_suffixes = {".geojson", ".json", ".tif", ".tiff"}
max_upload_bytes = 200 * 1024 * 1024


class GroundControlPoint(BaseModel):
    id: str
    pixel_x: float
    pixel_y: float
    map_x: float = Field(description="EOV easting in meters")
    map_y: float = Field(description="EOV northing in meters")


class GeoreferenceRequest(BaseModel):
    transform_method: str = "auto"
    target_crs: str = "EPSG:23700"
    reference_id: str | None = None
    points: list[GroundControlPoint]


class LegendDetectRequest(BaseModel):
    bbox: list[int] | None = None


class LegendItem(BaseModel):
    id: str
    code: str
    name: str
    symbol_type: str | None = None
    label: str | None = None
    geometry_type: str
    color_rgb: list[int] = Field(min_length=3, max_length=3)
    color_tolerance: int = Field(ge=0, le=100)
    enabled: bool = True


class LegendUpdateRequest(BaseModel):
    items: list[LegendItem]


class PolygonVectorizeRequest(BaseModel):
    legend_item: LegendItem


async def _persist_legend_items(project_id: str, items: list[LegendItem]) -> None:
    database_url = _database_url()
    if not database_url:
        return
    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS legend_classes (
                id BIGSERIAL PRIMARY KEY,
                project_id TEXT NOT NULL,
                class_id TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                geometry_type TEXT NOT NULL,
                color_rgb JSONB NOT NULL,
                visual_signature JSONB,
                color_tolerance INTEGER NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                UNIQUE (project_id, class_id)
            )
        """)
        await connection.execute("ALTER TABLE legend_classes ADD COLUMN IF NOT EXISTS visual_signature JSONB")
        await connection.executemany(
                        """INSERT INTO legend_classes (project_id, class_id, code, name, geometry_type, color_rgb, visual_signature, color_tolerance, enabled)
                             VALUES ($1, $2, $3, $4, $5, $6::jsonb, NULL, $7, $8)
               ON CONFLICT (project_id, class_id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name,
                 geometry_type = EXCLUDED.geometry_type, color_rgb = EXCLUDED.color_rgb,
                                 color_tolerance = EXCLUDED.color_tolerance, enabled = EXCLUDED.enabled""",
            [(project_id, item.id, item.code, item.name, item.geometry_type, json.dumps(item.color_rgb), item.color_tolerance, item.enabled) for item in items],
        )
    finally:
        await connection.close()

app = FastAPI(title="VectoryAI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    return value.replace("postgresql+asyncpg://", "postgresql://") if value else None


async def _persist_gcps(project_id: str, request: GeoreferenceRequest, selected_method: str) -> None:
    database_url = _database_url()
    if not database_url:
        return
    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS gcps (
                id BIGSERIAL PRIMARY KEY,
                project_id TEXT NOT NULL,
                gcp_id TEXT NOT NULL,
                pixel_x DOUBLE PRECISION NOT NULL,
                pixel_y DOUBLE PRECISION NOT NULL,
                map_x DOUBLE PRECISION NOT NULL,
                map_y DOUBLE PRECISION NOT NULL,
                transform_method TEXT NOT NULL,
                target_crs TEXT NOT NULL,
                confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (project_id, gcp_id)
            )
        """)
        await connection.executemany(
            """INSERT INTO gcps (project_id, gcp_id, pixel_x, pixel_y, map_x, map_y, transform_method, target_crs)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               ON CONFLICT (project_id, gcp_id) DO UPDATE SET pixel_x = EXCLUDED.pixel_x, pixel_y = EXCLUDED.pixel_y,
                 map_x = EXCLUDED.map_x, map_y = EXCLUDED.map_y, transform_method = EXCLUDED.transform_method,
                 target_crs = EXCLUDED.target_crs, confirmed_at = NOW()""",
            [(project_id, point.id, point.pixel_x, point.pixel_y, point.map_x, point.map_y, selected_method, request.target_crs) for point in request.points],
        )
    finally:
        await connection.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api", "timestamp": datetime.now(timezone.utc).isoformat()}


def _validate_source(source_path: Path, suffix: str, page_number: int) -> int:
    if suffix == ".pdf":
        try:
            with fitz.open(source_path) as document:
                page_count = document.page_count
        except (fitz.FileDataError, OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail="The uploaded PDF is invalid or corrupted") from error
        if page_count == 0:
            raise HTTPException(status_code=422, detail="The uploaded PDF has no pages")
        if page_number < 0 or page_number >= page_count:
            raise HTTPException(status_code=422, detail=f"page_number must be between 0 and {page_count - 1}")
        return page_count

    try:
        with Image.open(source_path) as image:
            image.verify()
    except (OSError, SyntaxError, ValueError) as error:
        raise HTTPException(status_code=422, detail="The uploaded image is invalid or corrupted") from error
    if page_number != 0:
        raise HTTPException(status_code=422, detail="page_number is only valid for PDF uploads")
    return 1


@app.post("/api/v1/projects/upload", status_code=202)
async def upload_project(
    file: UploadFile = File(...),
    page_number: int = Form(0),
) -> dict[str, object]:
    original_name = Path(file.filename or "upload").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=415, detail="Supported formats are PDF, JPG, JPEG, PNG, TIF, and TIFF")

    project_id = f"project_{uuid4().hex}"
    project_directory = storage_root / project_id / "raw"
    project_directory.mkdir(parents=True, exist_ok=True)
    source_path = project_directory / f"source{suffix}"
    bytes_written = 0
    try:
        with source_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise HTTPException(status_code=413, detail="Maximum upload size is 200 MB")
                destination.write(chunk)
    except HTTPException:
        source_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    try:
        page_count = _validate_source(source_path, suffix, page_number)
        job = celery_client.send_task(
            "vectoryai.ingest_document",
            args=[project_id, str(source_path), page_number, original_name],
        )
    except HTTPException:
        source_path.unlink(missing_ok=True)
        shutil.rmtree(project_directory.parent, ignore_errors=True)
        raise
    except Exception as error:
        source_path.unlink(missing_ok=True)
        shutil.rmtree(project_directory.parent, ignore_errors=True)
        raise HTTPException(status_code=503, detail="The ingestion queue is unavailable") from error
    return {
        "project_id": project_id,
        "job_id": job.id,
        "status": "queued",
        "page_number": page_number,
        "page_count": page_count,
    }


@app.get("/api/v1/projects/{project_id}/ingestion")
def ingestion_status(project_id: str) -> dict[str, object]:
    project_directory = storage_root / project_id
    metadata_path = project_directory / "ingestion.json"
    if not metadata_path.exists():
        if (project_directory / "raw").exists():
            return {"project_id": project_id, "status": "processing"}
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project_id": project_id, "status": "completed", "metadata": json.loads(metadata_path.read_text(encoding="utf-8"))}


@app.get("/api/v1/projects/{project_id}/thumbnail")
def project_thumbnail(project_id: str) -> FileResponse:
    thumbnail_path = storage_root / project_id / "raster" / "thumbnail.jpg"
    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail is not ready")
    return FileResponse(thumbnail_path, media_type="image/jpeg")


@app.post("/api/v1/projects/{project_id}/georef", status_code=202)
def start_georeferencing(project_id: str, request: GeoreferenceRequest) -> dict[str, object]:
    master_path = storage_root / project_id / "raster" / "master.jpg"
    if not master_path.exists():
        raise HTTPException(status_code=404, detail="Ingested master raster is not ready")
    if request.target_crs != "EPSG:23700":
        raise HTTPException(status_code=422, detail="Only EPSG:23700 EOV is currently supported")
    if len(request.points) < 3:
        raise HTTPException(status_code=422, detail="Georeferencing requires at least 3 GCPs")
    if request.transform_method not in {"auto", "affine", "polynomial", "tps"}:
        raise HTTPException(status_code=422, detail="Transform method must be auto, affine, polynomial, or tps")
    selected_method = request.transform_method
    if selected_method == "auto":
        selected_method = "affine" if len(request.points) <= 5 else "polynomial" if len(request.points) <= 9 else "tps"
    if selected_method == "polynomial" and len(request.points) < 6:
        raise HTTPException(status_code=422, detail="Polynomial transformation requires at least 6 GCPs")
    if selected_method == "tps" and len(request.points) < 10:
        raise HTTPException(status_code=422, detail="TPS transformation requires at least 10 GCPs")

    try:
        import asyncio
        asyncio.run(_persist_gcps(project_id, request, selected_method))
    except Exception as error:
        raise HTTPException(status_code=503, detail="GCP persistence is unavailable") from error
    job = celery_client.send_task(
        "vectoryai.warp_georef",
        args=[project_id, [point.model_dump() for point in request.points], str(storage_root), selected_method],
    )
    return {"project_id": project_id, "job_id": job.id, "status": "queued", "target_crs": request.target_crs, "transform_method": selected_method}


@app.post("/api/v1/projects/{project_id}/georef/reference", status_code=201)
async def upload_reference_layer(
    project_id: str,
    file: UploadFile = File(...),
    crs: str = Form("EPSG:23700"),
) -> dict[str, object]:
    if crs != "EPSG:23700":
        raise HTTPException(status_code=422, detail="Reference layers must currently use EPSG:23700")
    original_name = Path(file.filename or "reference.geojson").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in reference_suffixes:
        raise HTTPException(status_code=415, detail="Reference layers must be GeoJSON, GeoTIFF, or COG files")
    project_directory = storage_root / project_id
    if not project_directory.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    reference_id = f"reference_{uuid4().hex}"
    reference_directory = project_directory / "reference"
    reference_directory.mkdir(parents=True, exist_ok=True)
    reference_path = reference_directory / f"{reference_id}{suffix}"
    try:
        content = await file.read()
        if len(content) > max_upload_bytes:
            raise HTTPException(status_code=413, detail="Maximum reference-layer size is 200 MB")
        if suffix in {".geojson", ".json"}:
            json.loads(content.decode("utf-8-sig"))
        reference_path.write_bytes(content)
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="Reference layer must be valid UTF-8 JSON") from error
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="Reference layer must contain valid GeoJSON") from error
    finally:
        await file.close()
    return {"reference_id": reference_id, "crs": crs, "filename": original_name, "format": suffix[1:], "url": f"/api/v1/projects/{project_id}/georef/reference/{reference_id}"}


@app.get("/api/v1/projects/{project_id}/georef/reference/{reference_id}")
def reference_layer(project_id: str, reference_id: str) -> FileResponse:
    safe_reference_id = Path(reference_id).name
    for suffix, media_type in ((".geojson", "application/geo+json"), (".json", "application/geo+json"), (".tif", "image/tiff"), (".tiff", "image/tiff")):
        reference_path = storage_root / project_id / "reference" / f"{safe_reference_id}{suffix}"
        if reference_path.exists():
            return FileResponse(reference_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Reference layer not found")


@app.get("/api/v1/projects/{project_id}/georef/status")
def georeference_status(project_id: str) -> dict[str, object]:
    metadata_path = storage_root / project_id / "georef" / "metadata.json"
    if not metadata_path.exists():
        if (storage_root / project_id / "raster" / "master.jpg").exists():
            return {"project_id": project_id, "status": "pending"}
        raise HTTPException(status_code=404, detail="Project not found")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") == "failed":
        return {"project_id": project_id, **metadata}
    return {"project_id": project_id, "status": "completed", **metadata, "cog_url": f"/api/v1/projects/{project_id}/georef/cog"}


@app.get("/api/v1/projects/{project_id}/georef/cog")
def georeferenced_raster(project_id: str) -> FileResponse:
    output_path = storage_root / project_id / "georef" / "warped_eov.tif"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Georeferenced raster is not ready")
    return FileResponse(output_path, media_type="image/tiff")


@app.post("/api/v1/projects/{project_id}/legend/detect", status_code=202)
def start_legend_detection(project_id: str, request: LegendDetectRequest) -> dict[str, object]:
    source_path = storage_root / project_id / "raster" / "master.jpg"
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Ingested master raster is not ready")
    if request.bbox and (len(request.bbox) != 4 or request.bbox[0] < 0 or request.bbox[1] < 0 or request.bbox[2] <= request.bbox[0] or request.bbox[3] <= request.bbox[1]):
        raise HTTPException(status_code=422, detail="bbox must be [xmin, ymin, xmax, ymax]")
    job = celery_client.send_task(
        "vectoryai.parse_legend",
        args=[project_id, str(source_path), str(storage_root), request.bbox],
    )
    return {"project_id": project_id, "job_id": job.id, "status": "queued"}


@app.get("/api/v1/projects/{project_id}/legend")
def legend_registry(project_id: str) -> dict[str, object]:
    registry_path = storage_root / project_id / "legend" / "registry.json"
    if not registry_path.exists():
        if (storage_root / project_id / "raster" / "master.jpg").exists():
            return {"project_id": project_id, "status": "pending", "items": []}
        raise HTTPException(status_code=404, detail="Project not found")
    return json.loads(registry_path.read_text(encoding="utf-8"))


@app.put("/api/v1/projects/{project_id}/legend")
def update_legend(project_id: str, request: LegendUpdateRequest) -> dict[str, object]:
    project_directory = storage_root / project_id
    registry_path = project_directory / "legend" / "registry.json"
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Legend registry not found")
    for item in request.items:
        if item.geometry_type not in {"Polygon", "LineString", "Point"}:
            raise HTTPException(status_code=422, detail="geometry_type must be Polygon, LineString, or Point")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["items"] = [item.model_dump() for item in request.items]
    registry["status"] = "reviewed"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        asyncio.run(_persist_legend_items(project_id, request.items))
    except Exception as error:
        raise HTTPException(status_code=503, detail="Legend database persistence is unavailable") from error
    return {"updated_count": len(request.items), "status": "reviewed"}


@app.post("/api/v1/projects/{project_id}/vectorize", status_code=202)
def start_polygon_vectorization(project_id: str, request: PolygonVectorizeRequest) -> dict[str, object]:
    if request.legend_item.geometry_type not in {"Polygon", "LineString", "Point"}:
        raise HTTPException(status_code=422, detail="The vectorizer accepts Polygon, LineString, or Point legend items")
    raster_path = storage_root / project_id / "raster" / "master.jpg"
    if not raster_path.exists():
        raise HTTPException(status_code=404, detail="Ingested master raster is not ready")
    task_name_by_geometry = {
        "Polygon": "vectoryai.vectorize_polygon",
        "LineString": "vectoryai.vectorize_line",
        "Point": "vectoryai.vectorize_point",
    }
    task_name = task_name_by_geometry[request.legend_item.geometry_type]
    job = celery_client.send_task(
        task_name,
        args=[project_id, request.legend_item.model_dump(), str(storage_root)],
    )
    return {"project_id": project_id, "job_id": job.id, "status": "queued", "layer_id": request.legend_item.id}


@app.get("/api/v1/projects/{project_id}/layers/{layer_id}/geojson")
def vector_layer_geojson(project_id: str, layer_id: str) -> FileResponse:
    safe_layer_id = Path(layer_id).name
    layer_path = storage_root / project_id / "layers" / f"{safe_layer_id}.geojson"
    if not layer_path.exists():
        raise HTTPException(status_code=404, detail="Vector layer is not ready")
    return FileResponse(layer_path, media_type="application/geo+json")


@app.get("/api/v1/projects/{project_id}/deepzoom")
def deepzoom_descriptor(project_id: str) -> FileResponse:
    descriptor_path = storage_root / project_id / "master.dzi"
    if not descriptor_path.exists():
        raise HTTPException(status_code=404, detail="DeepZoom descriptor is not ready")
    return FileResponse(descriptor_path, media_type="application/xml")


@app.get("/api/v1/projects/{project_id}/deepzoom/{level}/{tile_name}")
def deepzoom_tile(project_id: str, level: int, tile_name: str) -> FileResponse:
    safe_tile_name = Path(tile_name).name
    if level < 0 or safe_tile_name != tile_name or not safe_tile_name.endswith(".jpg"):
        raise HTTPException(status_code=404, detail="Tile not found")
    tile_path = storage_root / project_id / "master_files" / str(level) / safe_tile_name
    if not tile_path.exists():
        raise HTTPException(status_code=404, detail="Tile not found")
    return FileResponse(tile_path, media_type="image/jpeg")


@app.get("/api/v1/projects")
def list_projects() -> dict[str, list[object]]:
    return {"projects": []}
