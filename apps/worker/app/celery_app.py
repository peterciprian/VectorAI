import os

from celery import Celery

celery_app = Celery(
    "vectoryai",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)


@celery_app.task(name="vectoryai.healthcheck")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "worker"}
