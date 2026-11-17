"""AG-UI text survives durable replay and resumes after each live event."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi.sse import format_sse_event
from langflow.services.background_execution.runner import JobRunner
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_settings_service
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.real_services


def _parse_frame(frame: bytes) -> tuple[int, dict]:
    lines = frame.decode().splitlines()
    event_id = int(next(line[4:] for line in lines if line.startswith("id: ")))
    payload = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
    return event_id, payload


@pytest.mark.parametrize("expose_graph_state", [True, False])
@pytest.mark.parametrize("terminal_event", ["end", "error"])
async def test_agui_content_replays_and_resumes(real_services_job_service, expose_graph_state, terminal_event):
    jobs = real_services_job_service
    user_id, job_id = uuid4(), uuid4()
    await jobs.create_job(
        job_id=job_id,
        flow_id=uuid4(),
        user_id=user_id,
        initial_metadata={"request": {"stream_protocol": "agui"}},
    )
    service = BackgroundExecutionService(settings_service=get_settings_service())
    user = UserRead.model_construct(id=user_id)
    adapter = get_stream_adapter(
        "agui", StreamAdapterContext(run_id=str(job_id), thread_id="thread", expose_graph_state=expose_graph_state)
    )

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        events = list(adapter.initial_events())
        for message_id, chunk in [("first", "Hello "), ("first", "世界"), ("second", "Again")]:
            events.extend(adapter.translate("token", {"id": message_id, "chunk": chunk}))
        events.extend(
            adapter.translate(terminal_event, {"error": "failed after text"} if terminal_event == "error" else {})
        )
        for seq, event in enumerate(events):
            yield format_sse_event(data_str=event.data_json, id=str(seq)), event.type

    live_frames = []
    subscription = service._bus.subscribe(str(job_id))

    async def collect() -> None:
        live_frames.extend([frame.data async for frame in subscription])

    collector = asyncio.create_task(collect())
    runner = JobRunner(job_service=jobs, live_bus=service._bus, adapter=adapter, frame_source=source)
    try:
        await runner.run(job_id=job_id, source_kwargs={})
        await asyncio.wait_for(collector, timeout=5)
    finally:
        collector.cancel()
        await asyncio.gather(collector, return_exceptions=True)

    stored_job = await jobs.get_job_by_job_id(job_id)
    assert stored_job is not None
    assert stored_job.status == (JobStatus.FAILED if terminal_event == "error" else JobStatus.COMPLETED)
    replay = [frame async for frame in service.events(job_id, None, user)]
    live_events = [_parse_frame(frame) for frame in live_frames]
    replay_events = [_parse_frame(frame) for frame in replay]
    assert replay_events == live_events
    payloads = [payload for _, payload in replay_events]
    content = [event for event in payloads if event["type"] == "TEXT_MESSAGE_CONTENT"]
    assert [(event["messageId"], event["delta"]) for event in content] == [
        ("first", "Hello "),
        ("first", "世界"),
        ("second", "Again"),
    ]
    ids = [event_id for event_id, _ in live_events]
    assert ids == list(range(1, len(live_frames) + 1))
    for index, event_id in enumerate(ids):
        continuation = [frame async for frame in service.events(job_id, str(event_id), user)]
        assert [_parse_frame(frame) for frame in continuation] == live_events[index + 1 :]
