from datetime import datetime, timezone
import os
import json
import shutil
from pathlib import Path
from uuid import uuid4

from celery import Celery
import fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
storage_root = Path(os.getenv("STORAGE_ROOT", "/storage/projects"))
celery_client = Celery("vectoryai-api", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
allowed_suffixes = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
max_upload_bytes = 200 * 1024 * 1024

app = FastAPI(title="VectoryAI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
