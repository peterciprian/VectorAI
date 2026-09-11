from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg
import redis.asyncio as redis


def database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    return value.replace("postgresql+asyncpg://", "postgresql://") if value else None


async def ensure_jobs_table(connection: asyncpg.Connection) -> None:
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS processing_jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            task_name TEXT,
            task_args JSONB,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            progress_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
            error_details JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ
        )
    """)
    await connection.execute("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS task_name TEXT")
    await connection.execute("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS task_args JSONB")


async def create_job(project_id: str, job_id: str, job_type: str, task_name: str, task_args: list[object]) -> None:
    url = database_url()
    if not url:
        return
    connection = await asyncpg.connect(url)
    try:
        await ensure_jobs_table(connection)
        await connection.execute(
                """INSERT INTO processing_jobs (id, project_id, job_type, task_name, task_args, status, stage)
                    VALUES ($1, $2, $3, $4, $5::jsonb, 'queued', 'queued')
               ON CONFLICT (id) DO NOTHING""",
                job_id, project_id, job_type, task_name, json.dumps(task_args),
        )
    finally:
        await connection.close()


async def get_job(job_id: str) -> dict[str, Any] | None:
    url = database_url()
    if not url:
        return None
    connection = await asyncpg.connect(url)
    try:
        await ensure_jobs_table(connection)
        row = await connection.fetchrow("SELECT id, project_id, job_type, task_name, task_args, status, stage, progress_percent, error_details, created_at, started_at, finished_at FROM processing_jobs WHERE id = $1", job_id)
        return dict(row) if row else None
    finally:
        await connection.close()


async def set_job_state(job_id: str, status: str, stage: str, progress: float, error: str | None = None) -> dict[str, Any] | None:
    url = database_url()
    if not url:
        return None
    connection = await asyncpg.connect(url)
    try:
        await ensure_jobs_table(connection)
        await connection.execute(
            """UPDATE processing_jobs SET status=$2, stage=$3, progress_percent=$4, error_details=$5::jsonb,
               finished_at=CASE WHEN $2 IN ('cancelled','failed') THEN NOW() ELSE finished_at END WHERE id=$1""",
            job_id, status, stage, progress, json.dumps({"message": error}) if error else None,
        )
        row = await connection.fetchrow("SELECT id, project_id, job_type, task_name, task_args, status, stage, progress_percent, error_details, created_at, started_at, finished_at FROM processing_jobs WHERE id=$1", job_id)
        result = dict(row) if row else None
    finally:
        await connection.close()
    if result:
        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        try:
            await client.publish(f"vectoryai:project:{result['project_id']}:jobs", json.dumps({"job_id": job_id, "project_id": result["project_id"], "status": status, "stage": stage, "progress_percent": progress, "error": error}))
        finally:
            await client.close()
    return result


def serializable_job(job: dict[str, Any]) -> dict[str, Any]:
    result = dict(job)
    for key in ("created_at", "started_at", "finished_at"):
        if isinstance(result.get(key), datetime):
            result[key] = result[key].astimezone(timezone.utc).isoformat()
    return result


async def project_events(project_id: str):
    client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(f"vectoryai:project:{project_id}:jobs")
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
            if message and message.get("type") == "message":
                yield f"data: {message['data']}\n\n"
            else:
                yield ": keepalive\n\n"
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()
        await client.close()