"""The v2 live stream serves the stored graph from the warm registry, like sync.

The stream path builds inside the v1 build-vertex loop (``generate_flow_events``).
It used to read and parse the flow row on every run even when the warm registry
held that revision. These tests pin the routing (warm when eligible, cold
otherwise) and run a real flow end to end with the registry on and off.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks
from langflow.api.v1.schemas import FlowDataRequest
from langflow.services.database.models.flow.model import Flow
from langflow.services.warm_registry.service import flow_version
from lfx.events.event_manager import create_default_event_manager
from lfx.services.deps import session_scope
from sqlmodel import select

if TYPE_CHECKING:
    from httpx import AsyncClient


def _fake_graph() -> MagicMock:
    graph = MagicMock()
    graph.source_flow_id = None
    graph.run_id = None
    graph.vertices = []
    graph.vertices_to_run = set()
    graph.sort_vertices.return_value = []
    graph.end_all_traces = AsyncMock()
    calls: list[str] = []
    graph.calls = calls

    def set_run_id(value) -> None:
        calls.append(f"set_run_id:{value}")
        graph.run_id = str(value)

    async def initialize_run() -> None:
        calls.append("initialize_run")

    graph.set_run_id.side_effect = set_run_id
    graph.initialize_run = AsyncMock(side_effect=initialize_run)
    return graph


@pytest.fixture
def build_loop(monkeypatch: pytest.MonkeyPatch):
    """Stub the services around the real build loop; return the graph sources."""
    import langflow.api.build as build_module

    chat_service = MagicMock()
    chat_service.set_cache = AsyncMock()

    @asynccontextmanager
    async def fake_session_scope():
        yield MagicMock()

    cold_graph = _fake_graph()
    warm_graph = _fake_graph()
    build_from_db = AsyncMock(return_value=cold_graph)
    warm_deepcopy = AsyncMock(return_value=warm_graph)
    monkeypatch.setattr(build_module, "get_chat_service", lambda: chat_service)
    monkeypatch.setattr(build_module, "get_telemetry_service", lambda: MagicMock())
    monkeypatch.setattr(build_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(build_module, "build_graph_from_db", build_from_db)
    monkeypatch.setattr(build_module, "build_graph_from_data", AsyncMock(return_value=cold_graph))
    monkeypatch.setattr(build_module, "warm_deepcopy", warm_deepcopy)
    return SimpleNamespace(
        module=build_module,
        build_from_db=build_from_db,
        warm_deepcopy=warm_deepcopy,
        cold_graph=cold_graph,
        warm_graph=warm_graph,
    )


async def _run_build(build_loop, **overrides) -> None:
    kwargs = {
        "flow_id": uuid4(),
        "background_tasks": BackgroundTasks(),
        "event_manager": create_default_event_manager(asyncio.Queue()),
        "inputs": None,
        "data": None,
        "files": None,
        "stop_component_id": None,
        "start_component_id": None,
        "log_builds": False,
        "current_user": SimpleNamespace(id=uuid4()),
        "flow_name": "flow",
        "track_job_status": False,
        "run_id": str(uuid4()),
        "warm_flow_version": "v1",
    }
    kwargs.update(overrides)
    await build_loop.module.generate_flow_events(**kwargs)


async def test_stream_build_serves_the_warm_copy_without_reading_the_flow_row(build_loop) -> None:
    flow_id = uuid4()
    user_id = uuid4()
    run_id = str(uuid4())

    await _run_build(
        build_loop,
        flow_id=flow_id,
        current_user=SimpleNamespace(id=user_id),
        run_id=run_id,
        warm_flow_version="authorized-version",
    )

    build_loop.build_from_db.assert_not_awaited()
    build_loop.warm_deepcopy.assert_awaited_once()
    args, kwargs = build_loop.warm_deepcopy.await_args
    assert args == (str(flow_id),)
    principal = kwargs.pop("execution_principal")
    assert principal is not None
    assert kwargs == {
        "expected_version": "authorized-version",
        "user_id": str(user_id),
        # No session in the request: the build loop defaults it to the flow id.
        "session_id": str(flow_id),
        # The cold build keeps persisted stream values, so the warm copy must too.
        "stream": None,
    }
    # The run id is pinned before tracing starts, as build_graph_from_data does.
    assert build_loop.warm_graph.calls[:2] == [f"set_run_id:{run_id}", "initialize_run"]


async def test_stream_build_falls_back_to_the_db_when_the_registry_misses(build_loop) -> None:
    """A disabled registry, a miss, or another revision all return None."""
    build_loop.warm_deepcopy.return_value = None

    await _run_build(build_loop)

    build_loop.warm_deepcopy.assert_awaited_once()
    build_loop.build_from_db.assert_awaited_once()
    build_loop.warm_graph.initialize_run.assert_not_awaited()


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"warm_flow_version": None}, id="caller-did-not-opt-in"),
        pytest.param({"tweaks": {"node": {"field": "value"}}}, id="tweaks"),
        pytest.param({"job_id": uuid4()}, id="durable-job"),
        pytest.param({"source_flow_id": uuid4()}, id="public-virtual-flow"),
        pytest.param({"data": FlowDataRequest(nodes=[], edges=[])}, id="request-data"),
    ],
)
async def test_stream_build_keeps_the_cold_path_when_the_run_is_not_the_stored_graph(
    build_loop, monkeypatch: pytest.MonkeyPatch, overrides
) -> None:
    import langflow.api.build as build_module

    monkeypatch.setattr(build_module, "process_tweaks_on_graph", MagicMock())
    if "job_id" in overrides:
        from lfx.services import deps as lfx_deps

        monkeypatch.setattr(lfx_deps, "get_checkpoint_service", lambda: MagicMock())

    await _run_build(build_loop, **overrides)

    build_loop.warm_deepcopy.assert_not_awaited()


async def _captured_build_kwargs(monkeypatch: pytest.MonkeyPatch, frames_factory) -> dict:
    from langflow.api.v2 import workflow_execution

    captured: dict = {}

    async def fake_generate_flow_events(**kwargs):
        captured.update(kwargs)
        await kwargs["event_manager"].queue.put((None, None, 0.0))

    monkeypatch.setattr(workflow_execution, "generate_flow_events", fake_generate_flow_events)
    async for _ in frames_factory(workflow_execution):
        pass
    return captured


def _flow_read(updated_at):
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        name="stream-warm",
        data={"nodes": [], "edges": []},
        updated_at=updated_at,
        access_type=None,
    )


async def test_live_stream_passes_the_authorized_revision_to_the_build_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
    from lfx.workflow.converters import ParsedWorkflowRun

    updated_at = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    flow = _flow_read(updated_at)
    user = SimpleNamespace(id=flow.user_id, is_superuser=False)
    parsed = ParsedWorkflowRun(flow_id=str(flow.id), mode="stream")

    def frames(workflow_execution):
        response = workflow_execution._execute_streaming_workflow(
            adapter=get_stream_adapter("langflow", StreamAdapterContext(run_id="r", thread_id="t")),
            run_id=str(uuid4()),
            parsed=parsed,
            flow=flow,
            current_user=user,
            background_tasks=BackgroundTasks(),
        )
        return response.body_iterator

    captured = await _captured_build_kwargs(monkeypatch, frames)

    assert captured["warm_flow_version"] == flow_version(updated_at)
    assert captured["provider_policy_flow"] is flow


@pytest.mark.parametrize("updated_at", [datetime(2026, 9, 29, tzinfo=timezone.utc), None])
async def test_other_stream_frame_callers_keep_the_cold_build(monkeypatch: pytest.MonkeyPatch, updated_at) -> None:
    """Background and public callers do not opt in; a flow with no revision cannot."""
    from langflow.api.v2.workflow_execution import FAMILY_WORKFLOW_V2
    from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
    from lfx.workflow.converters import ParsedWorkflowRun

    flow = _flow_read(updated_at)
    user = SimpleNamespace(id=flow.user_id, is_superuser=False)
    opt_in = updated_at is None

    def frames(workflow_execution):
        return workflow_execution._stream_event_frames(
            adapter=get_stream_adapter("langflow", StreamAdapterContext(run_id="r", thread_id="t")),
            flow_id=flow.id,
            flow_name=flow.name,
            background_tasks=BackgroundTasks(),
            parsed=ParsedWorkflowRun(flow_id=str(flow.id), mode="stream"),
            current_user=user,
            provider_policy_flow=flow,
            protocol="v2",
            execution_family=FAMILY_WORKFLOW_V2,
            use_warm_registry=opt_in,
        )

    captured = await _captured_build_kwargs(monkeypatch, frames)

    assert captured["warm_flow_version"] is None


def _event_types(body: str) -> list[str]:
    types = []
    for line in body.splitlines():
        if line.startswith("data:"):
            payload = json.loads(line.removeprefix("data:").strip())
            types.append(payload.get("event") or payload.get("type"))
    return types


class TestStreamWarmRegistryEndToEnd:
    """A real no-LLM chatbot flow streamed with the registry on and off."""

    @pytest.fixture
    async def chatbot_flow_id(self, created_api_key, json_memory_chatbot_no_llm):
        raw = json.loads(json_memory_chatbot_no_llm)
        flow_id = uuid4()
        async with session_scope() as session:
            session.add(
                Flow(
                    id=flow_id,
                    name="Stream Warm Registry Flow",
                    data=raw.get("data", raw),
                    user_id=created_api_key.user_id,
                )
            )
            await session.flush()
        yield flow_id
        from langflow.services.warm_registry.service import get_warm_registry

        await get_warm_registry().evict(str(flow_id))
        async with session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if flow:
                await session.delete(flow)

    @staticmethod
    def _spy_graph_sources(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
        import langflow.api.build as build_module

        real_from_db = build_module.build_graph_from_db
        real_warm = build_module.warm_deepcopy
        spies = SimpleNamespace(cold=0, warm_hits=0)

        async def counting_from_db(*args, **kwargs):
            spies.cold += 1
            return await real_from_db(*args, **kwargs)

        async def counting_warm(*args, **kwargs):
            graph = await real_warm(*args, **kwargs)
            spies.warm_hits += graph is not None
            return graph

        monkeypatch.setattr(build_module, "build_graph_from_db", counting_from_db)
        monkeypatch.setattr(build_module, "warm_deepcopy", counting_warm)
        return spies

    async def _stream(self, client: AsyncClient, api_key: str, flow_id, session_id: str) -> str:
        response = await client.post(
            "api/v2/workflows",
            json={"flow_id": str(flow_id), "input_value": "hello", "mode": "stream", "session_id": session_id},
            headers={"x-api-key": api_key},
        )
        assert response.status_code == 200
        return response.text

    @pytest.mark.parametrize("enabled", [True, False], ids=["registry-on", "registry-off"])
    async def test_stream_runs_the_same_with_the_registry_on_or_off(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow_id,
        monkeypatch: pytest.MonkeyPatch,
        enabled,
    ):
        from langflow.services.deps import get_settings_service

        monkeypatch.setattr(get_settings_service().settings, "warm_registry_enabled", enabled)
        spies = self._spy_graph_sources(monkeypatch)

        bodies = [
            await self._stream(client, created_api_key.api_key, chatbot_flow_id, session_id=f"s-{i}") for i in range(2)
        ]

        for body in bodies:
            assert "hello" in body
            types = _event_types(body)
            assert "error" not in types
            assert types[-1] == "end"
            assert "end_vertex" in types
            assert "output" in types
        # Same event sequence on every run, whichever source built the graph.
        assert _event_types(bodies[0]) == _event_types(bodies[1])
        if enabled:
            # Both runs are served warm (the first lazily warms the entry).
            assert (spies.warm_hits, spies.cold) == (2, 0)
        else:
            assert (spies.warm_hits, spies.cold) == (0, 2)

    async def test_stream_rebuilds_cold_after_the_flow_changes(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow_id,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from langflow.services.deps import get_settings_service

        monkeypatch.setattr(get_settings_service().settings, "warm_registry_enabled", True)
        spies = self._spy_graph_sources(monkeypatch)
        await self._stream(client, created_api_key.api_key, chatbot_flow_id, session_id="before")
        assert (spies.warm_hits, spies.cold) == (1, 0)

        async with session_scope() as session:
            flow = await session.get(Flow, chatbot_flow_id)
            flow.name = "Stream Warm Registry Flow (renamed)"
            flow.updated_at = datetime.now(timezone.utc)
            session.add(flow)

        body = await self._stream(client, created_api_key.api_key, chatbot_flow_id, session_id="after")

        assert _event_types(body)[-1] == "end"
        # The stale entry is never served: the new revision is warmed and used.
        assert spies.warm_hits == 2
        assert spies.cold == 0


# --------------------------------------------------------------------------- job row
def _job_service() -> SimpleNamespace:
    return SimpleNamespace(
        get_job_by_job_id=AsyncMock(return_value=None),
        create_job=AsyncMock(),
        execute_with_status=AsyncMock(side_effect=lambda _job_id, run, **_kw: run()),
    )


async def test_live_stream_creates_its_job_row_in_progress(build_loop, monkeypatch: pytest.MonkeyPatch) -> None:
    from langflow.services.database.models.jobs.model import JobStatus

    jobs = _job_service()
    monkeypatch.setattr(build_loop.module, "get_job_service", lambda: jobs)
    run_id = str(uuid4())

    await _run_build(build_loop, run_id=run_id, track_job_status=True, fresh_run_id=True)

    # The run id was minted for this request: no row can exist, so none is looked up.
    jobs.get_job_by_job_id.assert_not_awaited()
    assert jobs.create_job.await_args.kwargs["job_id"] == UUID(run_id)
    assert jobs.create_job.await_args.kwargs["status"] == JobStatus.IN_PROGRESS
    assert jobs.execute_with_status.await_args.kwargs == {"mark_in_progress": False}


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"fresh_run_id": False}, id="playground-and-public-callers"),
        pytest.param({"fresh_run_id": True, "run_id": None}, id="no-caller-run-id"),
    ],
)
async def test_other_tracked_runs_keep_the_queued_job_row(
    build_loop, monkeypatch: pytest.MonkeyPatch, overrides
) -> None:
    from langflow.services.database.models.jobs.model import JobStatus

    jobs = _job_service()
    monkeypatch.setattr(build_loop.module, "get_job_service", lambda: jobs)

    await _run_build(build_loop, track_job_status=True, **overrides)

    jobs.get_job_by_job_id.assert_awaited_once()
    assert jobs.create_job.await_args.kwargs["status"] == JobStatus.QUEUED
    assert jobs.execute_with_status.await_args.kwargs == {"mark_in_progress": True}


async def test_an_existing_job_row_is_not_recreated_and_still_flips(
    build_loop, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = _job_service()
    jobs.get_job_by_job_id.return_value = object()
    monkeypatch.setattr(build_loop.module, "get_job_service", lambda: jobs)

    await _run_build(build_loop, track_job_status=True, fresh_run_id=False)

    jobs.create_job.assert_not_awaited()
    assert jobs.execute_with_status.await_args.kwargs == {"mark_in_progress": True}


_JOB_STATEMENT = re.compile(
    r'^\s*(?:(UPDATE)|(SELECT|INSERT)\b.*?\b(?:FROM|INTO))\s+"?job"?\b',
    re.IGNORECASE | re.DOTALL,
)


class TestStreamJobRowStatements:
    """One live stream run writes its job row with one UPDATE fewer, and no lookup."""

    @pytest.fixture
    async def chatbot_flow_id(self, created_api_key, json_memory_chatbot_no_llm):
        raw = json.loads(json_memory_chatbot_no_llm)
        flow_id = uuid4()
        async with session_scope() as session:
            session.add(
                Flow(id=flow_id, name="Stream Job Row Flow", data=raw.get("data", raw), user_id=created_api_key.user_id)
            )
            await session.flush()
        yield flow_id
        async with session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if flow:
                await session.delete(flow)

    @staticmethod
    async def _job_statements(client: AsyncClient, api_key: str, flow_id) -> list[str]:
        from langflow.services.deps import get_db_service
        from sqlalchemy import event

        statements: list[str] = []

        def on_execute(_conn, _cursor, statement, *_args) -> None:
            match = _JOB_STATEMENT.match(statement)
            if match:
                statements.append(f"{(match.group(1) or match.group(2)).upper()} job")

        sync_engine = get_db_service().engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", on_execute)
        try:
            response = await client.post(
                "api/v2/workflows",
                json={"flow_id": str(flow_id), "input_value": "hello", "mode": "stream", "session_id": str(uuid4())},
                headers={"x-api-key": api_key},
            )
            assert response.status_code == 200
            assert _event_types(response.text)[-1] == "end"
            await asyncio.sleep(0.2)  # let fire-and-forget hooks finish
        finally:
            event.remove(sync_engine, "before_cursor_execute", on_execute)
        return statements

    async def test_stream_job_row_skips_the_lookup_and_the_queued_flip(
        self, client: AsyncClient, created_api_key, chatbot_flow_id, monkeypatch: pytest.MonkeyPatch
    ):
        from langflow.api.v2 import workflow_execution
        from langflow.services.database.models.jobs.model import Job, JobStatus

        after = await self._job_statements(client, created_api_key.api_key, chatbot_flow_id)

        # Baseline: the same request with the previous job-row handling.
        real_generate = workflow_execution.generate_flow_events

        async def previous_job_row(*args, **kwargs):
            kwargs["fresh_run_id"] = False
            await real_generate(*args, **kwargs)

        monkeypatch.setattr(workflow_execution, "generate_flow_events", previous_job_row)
        before = await self._job_statements(client, created_api_key.api_key, chatbot_flow_id)

        # No existence lookup before the INSERT, and one status UPDATE fewer: the row is
        # born IN_PROGRESS and written once more when the run ends. (Each UPDATE may be
        # followed by a read-back SELECT, depending on ``update_job_status``.)
        assert before[:2] == ["SELECT job", "INSERT job"], before
        assert after[0] == "INSERT job", after
        assert [s for s in before if s != "SELECT job"] == ["INSERT job", "UPDATE job", "UPDATE job"], before
        assert [s for s in after if s != "SELECT job"] == ["INSERT job", "UPDATE job"], after
        assert len(after) <= len(before) - 2, (before, after)

        async with session_scope() as session:
            rows = (await session.exec(select(Job).where(Job.flow_id == chatbot_flow_id))).all()
        assert len(rows) == 2
        assert {row.status for row in rows} == {JobStatus.COMPLETED}
