import os
import asyncio
import asyncpg

from celery import Celery

from .ingestion import ingest_document
from .georef import georeference_raster, write_georef_metadata
from .legend import parse_legend
from .vectorizer import polygonize_class
from .line_vectorizer import vectorize_line_class


async def _persist_legend_registry(project_id: str, registry: dict[str, object]) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return
    connection = await asyncpg.connect(database_url.replace("postgresql+asyncpg://", "postgresql://"))
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
        await connection.executemany(
            """INSERT INTO legend_classes (project_id, class_id, code, name, geometry_type, color_rgb, visual_signature, color_tolerance, enabled)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9)
               ON CONFLICT (project_id, class_id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name,
                 geometry_type = EXCLUDED.geometry_type, color_rgb = EXCLUDED.color_rgb,
                 visual_signature = EXCLUDED.visual_signature, color_tolerance = EXCLUDED.color_tolerance,
                 enabled = EXCLUDED.enabled""",
            [(project_id, item["id"], item["code"], item["name"], item["geometry_type"], json.dumps(item.get("color_rgb", [])), json.dumps(item.get("visual_signature")), item.get("color_tolerance", 18), item.get("enabled", True)) for item in registry.get("items", [])],
        )
    finally:
        await connection.close()

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


@celery_app.task(name="vectoryai.parse_legend")
def parse_legend_task(project_id: str, source_path: str, storage_root: str, bbox: list[int] | None = None) -> dict[str, object]:
    registry = parse_legend(project_id=project_id, source_path=source_path, storage_root=storage_root, bbox=bbox)
    asyncio.run(_persist_legend_registry(project_id, registry))
    return registry


@celery_app.task(name="vectoryai.vectorize_polygon")
def vectorize_polygon_task(project_id: str, legend_item: dict[str, object], storage_root: str) -> dict[str, object]:
    return polygonize_class(project_id=project_id, storage_root=storage_root, legend_item=legend_item)


@celery_app.task(name="vectoryai.vectorize_line")
def vectorize_line_task(project_id: str, legend_item: dict[str, object], storage_root: str) -> dict[str, object]:
    return vectorize_line_class(project_id=project_id, storage_root=storage_root, legend_item=legend_item)
