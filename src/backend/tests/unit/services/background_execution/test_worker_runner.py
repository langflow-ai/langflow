"""WorkerJobRunner hydrates a durable job and runs the real JobRunner to terminal.

Real JobService against the migrated test DB; the frame source is injected
(scripted) to stand in for a live graph build, exactly like test_service.py. A
fake live bus stands in for the redis Streams producer (its wire is proven in
test_redis_live_bus_realredis.py).
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import pytest
from langflow.services.background_execution.worker import WorkerJobRunner
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


async def _scripted_source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
    yield _frame("build_start", {})
    yield _frame("end_vertex", {"id": "n1"})
    yield _frame("end", {})


class _RecordingBus:
    """Stands in for the redis live bus (publish/close interface JobRunner uses)."""

    def __init__(self):
        self.published: list = []
        self.closed: list[str] = []

    async def publish(self, job_id, frame):  # noqa: ARG002 - job_id matches the bus contract
        self.published.append(frame)

    async def close(self, job_id):
        self.closed.append(job_id)


async def test_worker_runner_runs_durable_job_to_completion(active_user):
    jobs = get_job_service()
    flow_id = uuid.uuid4()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=flow_id, user_id=active_user.id)
    # The submit path persists the original request under job_metadata["request"].
    await jobs.update_job_metadata(job_id, {"request": {"stream_protocol": "langflow"}})

    bus = _RecordingBus()
    runner = WorkerJobRunner(
        settings=get_settings_service().settings,
        live_bus=bus,
        frame_source_factory=lambda **_kw: _scripted_source,
    )
    await runner.run(str(job_id))

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.COMPLETED
    assert refreshed.result is not None
    # Durable milestones were persisted and the live bus was closed.
    events = await jobs.read_events(job_id)
    types = {e.event_type for e in events}
    assert "build_start" in types
    assert "end_vertex" in types
    assert bus.closed == [str(job_id)]
