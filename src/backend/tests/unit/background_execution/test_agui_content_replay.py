"""AG-UI text survives durable replay and resumes after each live event."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from fastapi.sse import format_sse_event
from langflow.api.v2 import workflow_execution
from langflow.services.background_execution.runner import JobRunner
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_settings_service
from lfx.custom.custom_component.component import Component
from lfx.schema.message import Message
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun

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
        tool = {"type": "tool_use", "name": "weather", "tool_input": {"city": "Ames"}, "output": "sunny"}
        events.extend(adapter.translate("add_message", {"id": "second", "content_blocks": [{"contents": [tool]}]}))
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
    tool_end = next(i for i, event in enumerate(payloads) if event["type"] == "TOOL_CALL_END")
    assert payloads[tool_end + 1]["type"] == "TOOL_CALL_RESULT"
    assert payloads[tool_end + 1]["content"] == "sunny"
    assert payloads[tool_end + 1]["toolCallId"] == payloads[tool_end]["toolCallId"]
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


@pytest.mark.parametrize("producer", ["sync_iterator", "async_iterator", "callback_burst"])
async def test_fast_background_stream_completes_and_replays(real_services_job_service, monkeypatch, producer):
    jobs = real_services_job_service
    flow_id, user_id, job_id = uuid4(), uuid4(), uuid4()
    await jobs.create_job(
        job_id=job_id, flow_id=flow_id, user_id=user_id, initial_metadata={"request": {"stream_protocol": "agui"}}
    )
    user = UserRead.model_construct(id=user_id)
    service = BackgroundExecutionService(settings_service=get_settings_service())
    adapter = get_stream_adapter("agui", StreamAdapterContext(run_id=str(job_id), thread_id="thread"))
    chunks = [f"{index}🌎" for index in range(1200)]

    async def build(*, event_manager, **_kwargs):
        async def paced_chunks():
            for chunk in chunks:
                await asyncio.sleep(0.001)
                yield SimpleNamespace(content=chunk)

        if producer == "callback_burst":
            for chunk in chunks:
                event_manager.on_token(data={"id": "message", "chunk": chunk})
        else:
            component = Component()
            component.set_event_manager(event_manager)
            iterator = paced_chunks() if producer == "async_iterator" else (SimpleNamespace(content=c) for c in chunks)
            await component._stream_message(iterator, Message(id="message", sender="Machine", text=""))
        event_manager.on_end(data={})
        await event_manager.queue.put((None, None, time.time()))

    monkeypatch.setattr(workflow_execution, "generate_flow_events", build)
    runner = JobRunner(
        job_service=jobs, live_bus=service._bus, adapter=adapter, frame_source=workflow_execution._stream_event_frames
    )
    source_kwargs = {
        "adapter": adapter,
        "flow_id": flow_id,
        "flow_name": "fast stream",
        "current_user": user,
        "background_tasks": BackgroundTasks(),
        "parsed": ParsedWorkflowRun(
            flow_id=str(flow_id), mode="background", input_value="", emit_v1_side_channel=False
        ),
        "protocol": "v2.background",
        "execution_family": "workflow_v2",
    }

    async def collect_live():
        return [_parse_frame(frame) async for frame in service.events(job_id, None, user)]

    live, _ = await asyncio.gather(collect_live(), runner.run(job_id=job_id, source_kwargs=source_kwargs))
    job = await jobs.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED, job.error
    frames = [_parse_frame(frame) async for frame in service.events(job_id, None, user)]
    assert live == frames
    assert [seq for seq, _ in frames] == list(range(1, len(frames) + 1))
    assert [payload["delta"] for _, payload in frames if payload["type"] == "TEXT_MESSAGE_CONTENT"] == chunks
    assert frames[-1][1]["type"] == "RUN_FINISHED"
