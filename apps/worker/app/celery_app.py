import os

from celery import Celery

from .ingestion import ingest_document

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
