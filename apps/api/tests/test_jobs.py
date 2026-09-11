import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.jobs import serializable_job


class JobTests(unittest.TestCase):
    def test_serializable_job_formats_timestamps_and_retry_metadata(self) -> None:
        from datetime import datetime, timezone

        result = serializable_job({"id": "job-1", "status": "failed", "retry_count": 2, "created_at": datetime(2026, 9, 11, tzinfo=timezone.utc)})

        self.assertEqual(result["retry_count"], 2)
        self.assertEqual(result["created_at"], "2026-09-11T00:00:00+00:00")

    def test_cleanup_jobs_returns_deleted_count(self) -> None:
        connection = AsyncMock()
        connection.execute.return_value = "DELETE 3"

        with patch("app.jobs.database_url", return_value="postgresql://test"), patch("app.jobs.asyncpg.connect", new=AsyncMock(return_value=connection)):
            deleted = asyncio.run(__import__("app.jobs", fromlist=["cleanup_jobs"]).cleanup_jobs(30))

        self.assertEqual(deleted, 3)