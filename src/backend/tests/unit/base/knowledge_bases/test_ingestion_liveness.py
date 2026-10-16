"""API ingestion runs must stay live while they run and end with a true status.

The orphan sweep fails every IN_PROGRESS job whose heartbeat is missing or
stale. An ingestion that never heartbeats looks orphaned to the first sweep
that runs while it is in flight: the Redis-fallback watchdog, or a sibling
worker's startup sweep. Run history then reports a live run as failed.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.api.utils import ingestion_run_service
from langflow.api.utils.kb_helpers import KBIngestionHelper
from langflow.services.database.models.jobs.model import JobStatus, JobType
from langflow.services.deps import get_job_service, get_settings_service


@contextmanager
def _storage_paused_mid_write():
    """Patch storage so ingestion blocks inside its first write until released."""
    write_started = asyncio.Event()
    release = asyncio.Event()

    async def slow_add_documents(_documents):
        write_started.set()
        await release.wait()

    backend = MagicMock()
    backend.add_documents = slow_add_documents
    backend.storage_size_bytes = AsyncMock(return_value=0)
    backend.teardown = AsyncMock()
    with (
        patch("langflow.api.utils.kb_helpers.backend_for_name", new=AsyncMock(return_value=backend)),
        patch(
            "langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics_via_backend",
            new=AsyncMock(),
        ),
    ):
        yield write_started, release


async def _start_ingestion(job_service, job_id, user):
    # Created the way the ingest routes create it.
    await job_service.create_job(
        job_id=job_id,
        flow_id=job_id,
        job_type=JobType.INGESTION,
        asset_type="knowledge_base",
        user_id=user.id,
        heartbeat=True,
    )
    return asyncio.create_task(
        job_service.execute_with_status(
            job_id,
            KBIngestionHelper.perform_ingestion,
            kb_name="live_api_kb",
            kb_path=None,
            files_data=[("notes.txt", b"a short note to ingest")],
            chunk_size=100,
            chunk_overlap=0,
            separator="\n",
            source_name="notes",
            current_user=user,
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
            task_job_id=job_id,
            job_service=job_service,
        )
    )


@pytest.mark.usefixtures("client")
async def test_live_api_ingestion_is_not_swept_as_orphaned(active_user, monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "background_heartbeat_interval_s", 0.1)
    job_service = get_job_service()
    job_id = uuid.uuid4()
    # A run whose worker died: the same sweep must still fail it.
    dead_job_id = uuid.uuid4()
    await job_service.create_job(
        job_id=dead_job_id, flow_id=dead_job_id, job_type=JobType.INGESTION, status=JobStatus.IN_PROGRESS
    )

    with _storage_paused_mid_write() as (write_started, release):
        task = await _start_ingestion(job_service, job_id, active_user)
        try:
            await asyncio.wait_for(write_started.wait(), timeout=10)
            # Outlive the lease and the insert-time heartbeat, so only the
            # run's own keep-alive keeps its job fresh.
            await asyncio.sleep(1.5)
            swept = await job_service.sweep_orphans(lease_ttl_s=1.0)
            mid_run = await ingestion_run_service.get_run(job_id, user_id=active_user.id)
        finally:
            release.set()
            await asyncio.wait_for(task, timeout=10)

    assert swept == [dead_job_id]
    assert mid_run.status == "running"
    run = await ingestion_run_service.get_run(job_id, user_id=active_user.id)
    assert run.status == "succeeded"
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.error is None


@pytest.mark.usefixtures("client")
async def test_interrupted_api_ingestion_reads_failed(active_user):
    """A shutdown that cancels a run must not leave it recorded as succeeded."""
    job_service = get_job_service()
    job_id = uuid.uuid4()

    with _storage_paused_mid_write() as (write_started, _release):
        task = await _start_ingestion(job_service, job_id, active_user)
        await asyncio.wait_for(write_started.wait(), timeout=10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run = await ingestion_run_service.get_run(job_id, user_id=active_user.id)
    assert run.status == "failed"
    assert "interrupted" in run.error_message
    assert (await job_service.get_job_by_job_id(job_id)).status == JobStatus.FAILED


async def test_ingest_route_inserts_its_job_heartbeated(client, logged_in_headers, active_user, monkeypatch, tmp_path):
    """The job is live from insert, before the background run starts its own heartbeat."""
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    name = "heartbeated_ingest"
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text
    task_service = MagicMock()
    task_service.fire_and_forget_task = AsyncMock()

    with patch("langflow.api.v1.knowledge_bases.get_task_service", return_value=task_service):
        response = await client.post(
            f"/api/v1/knowledge_bases/{name}/ingest",
            headers=logged_in_headers,
            files={"files": ("notes.txt", io.BytesIO(b"a short note"), "text/plain")},
        )

    assert response.status_code == 200, response.text
    job = await get_job_service().get_job_by_job_id(uuid.UUID(response.json()["id"]))
    assert job.user_id == active_user.id
    assert job.status == JobStatus.QUEUED
    assert job.job_metadata["heartbeat_at"]
    assert job.job_metadata["owner"]
