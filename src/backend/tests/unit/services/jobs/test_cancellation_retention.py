"""Canceled jobs retain their history for a full window after cancellation."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.api.utils.kb_helpers import KBIngestionHelper
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType, SignalType
from langflow.services.deps import get_job_service, get_settings_service, session_scope
from langflow.services.memory_base.ingestion import cancel_active_jobs
from sqlmodel import update


@pytest.mark.parametrize("cancel_path", ["workflow", "knowledge_base", "memory_base"])
@pytest.mark.parametrize("initial_status", [JobStatus.QUEUED, JobStatus.IN_PROGRESS])
async def test_cancellation_starts_a_full_retention_window(
    cancel_path, initial_status, client, active_user, logged_in_headers, tmp_path, monkeypatch
):
    """An old run canceled today survives a sweep, then expires with its history."""
    service = get_job_service()
    job_id, asset_id = uuid4(), uuid4()
    old = datetime.now(timezone.utc) - timedelta(days=90)
    if cancel_path == "knowledge_base":
        monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
        kb_name = f"retention_{uuid4().hex}"
        record = await knowledge_base_service.create_record(user_id=active_user.id, name=kb_name)
        asset_id = record.id
        # Storage cleanup is independent of the real job update and purge below.
        monkeypatch.setattr(KBIngestionHelper, "cleanup_chroma_chunks_by_job", AsyncMock())

    async with session_scope() as session:
        session.add(
            Job(
                job_id=job_id,
                flow_id=uuid4(),
                user_id=active_user.id,
                status=initial_status,
                type=JobType.WORKFLOW if cancel_path == "workflow" else JobType.INGESTION,
                asset_id=asset_id,
                asset_type=cancel_path,
                created_timestamp=old,
                job_metadata={"request": {"mode": "background"}} if cancel_path == "workflow" else {},
            )
        )
    await service.append_event(job_id, "run_started", {})
    await service.save_checkpoint(job_id, "graph", "{}")

    if cancel_path == "workflow":
        response = await client.post("api/v2/workflows/stop", json={"job_id": str(job_id)}, headers=logged_in_headers)
        assert response.status_code == 200, response.text
    elif cancel_path == "knowledge_base":
        response = await client.post(f"api/v1/knowledge_bases/{kb_name}/cancel", headers=logged_in_headers)
        assert response.status_code == 200, response.text
    else:
        async with session_scope() as session:
            await cancel_active_jobs(memory_base_id=asset_id, db=session)

    # Keep an unconsumed signal alongside the event and checkpoint to cover all
    # child tables removed by retention, independently of the cancellation backend.
    await service.write_signal(job_id, SignalType.STOP)
    await service.purge_terminal_jobs(older_than_days=30, limit=100)

    job = await service.get_job_by_job_id(job_id)
    assert job is not None
    assert job.status == JobStatus.CANCELLED
    assert job.finished_timestamp is not None
    assert len(await service.read_events(job_id)) == 1
    assert await service.unconsumed_signals(job_id)
    assert await service.load_checkpoint(job_id, "graph") is not None

    async with session_scope() as session:
        await session.exec(update(Job).where(Job.job_id == job_id).values(finished_timestamp=old))
    await service.purge_terminal_jobs(older_than_days=30, limit=100)

    assert await service.get_job_by_job_id(job_id) is None
    assert await service.read_events(job_id) == []
    assert await service.unconsumed_signals(job_id) == []
    assert await service.load_checkpoint(job_id, "graph") is None
