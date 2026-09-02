"""Run telemetry regression tests for v2 workflow execution."""

from __future__ import annotations

import asyncio
import contextlib
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import BackgroundTasks
from lfx.graph.exceptions import GraphPausedException
from lfx.schema.workflow import JobStatus
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun


class _FakeGraph:
    run_id: str | None = None

    def set_run_id(self, run_id) -> None:
        self.run_id = str(run_id)

    def get_terminal_nodes(self) -> list[str]:
        return ["output-1"]


def _patch_sync_dependencies(monkeypatch, *, execute_side_effect=None, persist_side_effect=None):
    from langflow.api.v2 import workflow_execution as wf_exec
    from langflow.services import deps

    job_service = SimpleNamespace(
        create_job=AsyncMock(),
        execute_with_status=AsyncMock(
            return_value=([], "session-1") if execute_side_effect is None else None,
            side_effect=execute_side_effect,
        ),
        update_job_status=AsyncMock(),
    )
    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    settings = SimpleNamespace(sync_result_storage_enabled=True)
    settings_service = SimpleNamespace(settings=settings)

    monkeypatch.setattr(wf_exec, "warm_deepcopy", AsyncMock(return_value=None))
    monkeypatch.setattr(wf_exec.Graph, "from_payload", lambda *_args, **_kwargs: _FakeGraph())
    monkeypatch.setattr(wf_exec, "get_job_service", lambda: job_service)
    monkeypatch.setattr(wf_exec, "get_settings_service", lambda: settings_service)
    monkeypatch.setattr(
        wf_exec,
        "get_task_service",
        lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()),
    )
    monkeypatch.setattr(wf_exec, "get_memory_base_service", lambda: SimpleNamespace(on_flow_output=AsyncMock()))
    monkeypatch.setattr(wf_exec, "run_response_to_workflow_response", lambda **_kwargs: SimpleNamespace())
    monkeypatch.setattr(wf_exec, "_persist_sync_result", AsyncMock(side_effect=persist_side_effect))
    monkeypatch.setattr(wf_exec, "create_error_response", lambda **_kwargs: "error-response")
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)
    return wf_exec, telemetry


async def _execute_sync(wf_exec):
    flow_id = uuid4()
    return await wf_exec.execute_sync_workflow(
        parsed=ParsedWorkflowRun(flow_id=str(flow_id), input_value="", mode="sync"),
        flow=SimpleNamespace(id=flow_id, data={"nodes": [], "edges": []}, name="flow", updated_at=None),
        job_id=uuid4(),
        current_user=SimpleNamespace(id=uuid4()),
        background_tasks=BackgroundTasks(),
        http_request=None,
    )


async def test_live_stream_uses_one_run_id_for_adapter_graph_and_telemetry(monkeypatch):
    """A live stream's SSE run id must also identify its job row and RunPayload."""
    from langflow.api.v2 import workflow as workflow_api
    from langflow.api.v2 import workflow_execution as wf_exec
    from langflow.services import deps

    captured: dict[str, object] = {}
    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    original_get_stream_adapter = workflow_api.get_stream_adapter

    def capture_adapter(name, context):
        captured["adapter_run_id"] = context.run_id
        return original_get_stream_adapter(name, context)

    async def fake_generate_flow_events(**kwargs):
        captured["graph_run_id"] = kwargs["run_id"]
        captured["log_builds"] = kwargs["log_builds"]
        await kwargs["event_manager"].queue.put((None, None, time.time()))

    monkeypatch.setattr(workflow_api, "_apply_execution_gates", lambda parsed, *_args: parsed)
    monkeypatch.setattr(workflow_api, "get_stream_adapter", capture_adapter)
    monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)

    flow_id = uuid4()
    response = workflow_api.build_stream_response(
        ParsedWorkflowRun(flow_id=str(flow_id), input_value="", mode="stream"),
        SimpleNamespace(id=flow_id, name="flow", user_id=uuid4()),
        SimpleNamespace(id=uuid4()),
        stream_protocol="langflow",
        background_tasks=BackgroundTasks(),
    )
    async for _frame in response.body_iterator:
        pass

    payload = telemetry.log_package_run.await_args.args[0]
    assert captured["adapter_run_id"] == captured["graph_run_id"] == payload.run_id
    assert captured["log_builds"] is False


async def test_stream_pause_does_not_emit_terminal_run_telemetry(monkeypatch):
    from langflow.api.v2 import workflow_execution as wf_exec
    from langflow.services import deps

    async def fake_generate_flow_events(**kwargs):
        kwargs["event_manager"].send_event(
            event_type="human_input_required",
            data={"request_id": "request-1"},
        )
        await kwargs["event_manager"].queue.put((None, None, time.time()))

    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)

    adapter = get_stream_adapter(
        "langflow",
        StreamAdapterContext(run_id="job-1", thread_id="thread-1"),
    )
    frames = [
        frame
        async for frame, _event_type in wf_exec._stream_event_frames(
            adapter=adapter,
            flow_id=uuid4(),
            flow_name="flow",
            background_tasks=BackgroundTasks(),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
            current_user=SimpleNamespace(id=uuid4()),
            run_id="job-1",
            job_id=uuid4(),
            protocol="langflow",
        )
    ]

    assert any(b"human_input_required" in frame for frame in frames)
    telemetry.log_package_run.assert_not_awaited()


async def test_stream_client_disconnect_does_not_emit_run_telemetry(monkeypatch):
    """CancelledError (client disconnect / tab close) must not be recorded as a failed run."""
    from langflow.api.v2 import workflow_execution as wf_exec
    from langflow.services import deps

    async def fake_generate_flow_events(**_kwargs):
        # Simulate a mid-stream disconnect: never puts the sentinel, just hangs
        await asyncio.sleep(9999)

    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)

    adapter = get_stream_adapter(
        "langflow",
        StreamAdapterContext(run_id="job-2", thread_id="thread-2"),
    )

    async def _consume_then_cancel():
        gen = wf_exec._stream_event_frames(
            adapter=adapter,
            flow_id=uuid4(),
            flow_name="flow",
            background_tasks=BackgroundTasks(),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
            current_user=SimpleNamespace(id=uuid4()),
            run_id="job-2",
            job_id=uuid4(),
            protocol="langflow",
        )
        # Exhaust initial events then simulate the consumer task being cancelled
        async for _frame, _event_type in gen:
            break  # stop after the first frame to trigger cancellation on aclose

    task = asyncio.create_task(_consume_then_cancel())
    await asyncio.sleep(0)  # let the generator start
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    telemetry.log_package_run.assert_not_awaited()


async def test_stream_non_job_tracked_run_emits_run_id_none(monkeypatch):
    """Non-job-tracked streams (run_id=None) must emit run_id=None, not run_id=''."""
    from langflow.api.v2 import workflow_execution as wf_exec
    from langflow.services import deps

    async def fake_generate_flow_events(**kwargs):
        await kwargs["event_manager"].queue.put((None, None, time.time()))

    telemetry = SimpleNamespace(log_package_run=AsyncMock())
    monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)
    monkeypatch.setattr(deps, "get_telemetry_service", lambda: telemetry)

    adapter = get_stream_adapter(
        "langflow",
        StreamAdapterContext(run_id="", thread_id="thread-3"),
    )
    async for _frame, _event_type in wf_exec._stream_event_frames(
        adapter=adapter,
        flow_id=uuid4(),
        flow_name="flow",
        background_tasks=BackgroundTasks(),
        parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
        current_user=SimpleNamespace(id=uuid4()),
        run_id=None,  # explicitly no job tracking
        job_id=None,
        protocol="langflow",
    ):
        pass

    payload = telemetry.log_package_run.await_args.args[0]
    assert payload.run_id is None, f"expected run_id=None, got {payload.run_id!r}"


async def test_sync_pause_does_not_emit_terminal_run_telemetry(monkeypatch):
    paused = GraphPausedException(
        checkpoint_id="checkpoint-1",
        reason="waiting on a human",
        data={"request_id": "request-1"},
    )
    wf_exec, telemetry = _patch_sync_dependencies(monkeypatch, execute_side_effect=paused)

    response = await _execute_sync(wf_exec)

    assert response.status == JobStatus.SUSPENDED
    telemetry.log_package_run.assert_not_awaited()


async def test_sync_persistence_failure_emits_failed_run_telemetry(monkeypatch):
    wf_exec, telemetry = _patch_sync_dependencies(
        monkeypatch,
        persist_side_effect=RuntimeError("persist failed"),
    )

    response = await _execute_sync(wf_exec)

    assert response == "error-response"
    payload = telemetry.log_package_run.await_args.args[0]
    assert payload.run_success is False


async def test_sync_success_emits_successful_run_telemetry(monkeypatch):
    wf_exec, telemetry = _patch_sync_dependencies(monkeypatch)

    await _execute_sync(wf_exec)

    payload = telemetry.log_package_run.await_args.args[0]
    assert payload.run_success is True
