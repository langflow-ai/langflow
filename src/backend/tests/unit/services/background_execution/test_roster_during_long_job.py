"""Does the roster still report a worker that is busy with a long job?"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


class _OneJobBackend:
    def __init__(self, job_id):
        self._ids = [str(job_id)]

    async def requeue_lost(self, *, lease_ttl_s=45.0):  # noqa: ARG002
        return []

    async def claim(self, *, block_ms=1000):  # noqa: ARG002
        return self._ids.pop(0) if self._ids else None


@pytest.mark.usefixtures("client")
async def test_roster_reports_a_worker_busy_on_a_long_job():
    from langflow.services.background_execution.worker import run_worker_loop
    from langflow.services.database.models.worker_registry.crud import count_workers_by_state
    from langflow.services.deps import session_scope

    owner = "worker:probe:long"
    job_id = uuid4()
    stop_event = asyncio.Event()
    # Online window far shorter than the job, the way a 45s default relates to a
    # multi-minute background run.
    window = timedelta(seconds=0.4)
    seen = {}

    class _SlowRunner:
        def __init__(self):
            self.ran = []

        async def run(self, claimed_id):
            self.ran.append(claimed_id)
            await asyncio.sleep(1.2)  # outlives the window
            async with session_scope() as session:
                seen.update(await count_workers_by_state(session, now=datetime.now(timezone.utc), online_window=window))
            stop_event.set()

    await run_worker_loop(
        _OneJobBackend(job_id),
        _SlowRunner(),
        stop_event=stop_event,
        idle_block_ms=10,
        owner=owner,
        roster_enabled=True,
        roster_interval_s=0.1,
    )

    assert seen.get("busy") == 1, f"a worker mid-job must read as busy, got {seen}"
    assert seen.get("online") == 1, f"a worker mid-job must read as online, got {seen}"
