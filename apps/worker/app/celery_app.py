import os

from celery import Celery

from .ingestion import ingest_document
from .georef import georeference_raster, write_georef_metadata

celery_app = Celery(
    "vectoryai",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)


@celery_app.task(name="vectoryai.healthcheck")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "worker"}


@celery_app.task(name="vectoryai.ingest_document")
def ingest_document_task(
    project_id: str,
    source_path: str,
    page_number: int = 0,
    source_filename: str | None = None,
) -> dict[str, object]:
    return ingest_document(
        project_id=project_id,
        source_path=source_path,
        storage_root=os.getenv("STORAGE_ROOT", "/storage/projects"),
        page_number=page_number,
        source_filename=source_filename,
    )


@celery_app.task(name="vectoryai.warp_georef")
def warp_georef_task(project_id: str, gcps: list[dict[str, object]], storage_root: str, method: str = "auto") -> dict[str, object]:
    project_directory = os.path.join(storage_root, project_id)
    input_path = os.path.join(project_directory, "raster", "master.jpg")
    output_path = os.path.join(project_directory, "georef", "warped_eov.tif")
    metadata_path = os.path.join(project_directory, "georef", "metadata.json")
    try:
        metadata = georeference_raster(input_path, output_path, gcps, method=method)
        metadata["project_id"] = project_id
        metadata["status"] = "completed"
        write_georef_metadata(metadata_path, metadata)
        return metadata
    except Exception as error:
        write_georef_metadata(metadata_path, {"project_id": project_id, "status": "failed", "error": str(error)})
        raise
