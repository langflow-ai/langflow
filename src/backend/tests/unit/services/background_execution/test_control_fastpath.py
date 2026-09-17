"""stop() writes the durable STOP signal (the single source of truth, no fast-path)."""

from __future__ import annotations

import uuid

import pytest
from langflow.services.background_execution.db_backend import DBBackgroundQueue
from langflow.services.database.models.jobs.model import SignalType
from langflow.services.deps import get_job_service


@pytest.mark.usefixtures("client")
@pytest.mark.asyncio
async def test_stop_writes_durable_signal(active_user):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid.uuid4(), user_id=active_user.id)

    backend = DBBackgroundQueue(job_service=jobs)
    await backend.stop(str(job_id))

    # Source of truth: a STOP signal row a worker will see at the next boundary.
    # There is no side channel to check for — the DB backend has no broker to
    # write a dead fast-path marker to.
    signals = await jobs.unconsumed_signals(job_id)
    assert any(s.signal_type == SignalType.STOP for s in signals)
