from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as redis


def _database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    return value.replace("postgresql+asyncpg://", "postgresql://") if value else None


async def update_job(job_id: str | None, project_id: str, status: str, stage: str, progress: float, error: str | None = None) -> None:
    if not job_id:
        return
    url = _database_url()
    event = {"job_id": job_id, "project_id": project_id, "status": status, "stage": stage, "progress_percent": progress}
    if error:
        event["error"] = error
    if url:
        connection = await asyncpg.connect(url)
        try:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, job_type TEXT NOT NULL, task_name TEXT, task_args JSONB, retry_count INTEGER NOT NULL DEFAULT 0, last_action TEXT,
                    status TEXT NOT NULL, stage TEXT NOT NULL, progress_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
                    error_details JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ
                )
            """)
            await connection.execute("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS task_name TEXT")
            await connection.execute("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS task_args JSONB")
            await connection.execute("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0")
            await connection.execute("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS last_action TEXT")
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS processing_job_events (
                    id BIGSERIAL PRIMARY KEY, job_id TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                    progress_percent DOUBLE PRECISION NOT NULL, action TEXT, detail JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await connection.execute(
                """UPDATE processing_jobs SET status=$2, stage=$3, progress_percent=$4,
                   error_details=$5::jsonb,
                   started_at=CASE WHEN $2='running' AND started_at IS NULL THEN NOW() ELSE started_at END,
                   finished_at=CASE WHEN $2 IN ('completed','failed','cancelled') THEN NOW() ELSE finished_at END
                   WHERE id=$1 AND NOT ($2 IN ('running','completed') AND status='cancelled')""",
                job_id, status, stage, progress, json.dumps({"message": error}) if error else None,
            )
            await connection.execute(
                "INSERT INTO processing_job_events (job_id, status, stage, progress_percent, action, detail) VALUES ($1, $2, $3, $4, $5, $6::jsonb)",
                job_id, status, stage, progress, "worker", json.dumps({"message": error}) if error else None,
            )
        finally:
            await connection.close()
    client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    try:
        await client.publish(f"vectoryai:project:{project_id}:jobs", json.dumps(event))
    finally:
        await client.aclose()


def update_job_sync(job_id: str | None, project_id: str, status: str, stage: str, progress: float, error: str | None = None) -> None:
    asyncio.run(update_job(job_id, project_id, status, stage, progress, error))


async def cleanup_jobs(retention_days: int = 30) -> int:
    url = _database_url()
    if not url:
        return 0
    connection = await asyncpg.connect(url)
    try:
        result = await connection.execute(
            "DELETE FROM processing_jobs WHERE status IN ('completed','failed','cancelled') AND finished_at < NOW() - ($1 * INTERVAL '1 day')",
            retention_days,
        )
        await connection.execute("DELETE FROM processing_job_events WHERE job_id NOT IN (SELECT id FROM processing_jobs)")
        return int(result.split()[-1])
    finally:
        await connection.close()


def cleanup_jobs_sync(retention_days: int = 30) -> int:
    return asyncio.run(cleanup_jobs(retention_days))