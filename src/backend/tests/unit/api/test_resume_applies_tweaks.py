"""A resumed HITL run must re-apply the run's tweaks to the restored graph.

The checkpoint stores the flow's raw graph data, which never received the
run's tweaks (the fresh build path applies them after construction via
``process_tweaks_on_graph``). The resume path in ``build.py`` restored the
graph without an equivalent step, so every vertex after the pause ran with
the flow's saved defaults instead of the per-run overrides (issue #16075).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from langflow.api import build as build_module
from lfx.events.event_manager import create_default_event_manager

pytestmark = pytest.mark.no_blockbuster

_TWEAKS = {"OutNo": {"sender_name": "TWEAKED-AFTER"}}


def _user(user_id=None):
    return SimpleNamespace(id=user_id or uuid4(), is_superuser=False)


def _restored_graph() -> MagicMock:
    graph = MagicMock()
    graph.vertices = []
    graph.vertices_to_run = set()
    graph.human_input_decisions = {}
    graph.tracing_service = None
    graph.user_id = "job-owner"
    graph.flow_name = "flow"
    graph.run_id = None
    graph.initialize_run = AsyncMock()
    graph.resume_first_layer = MagicMock(return_value=[])
    graph.end_all_traces = AsyncMock()
    return graph


async def _drive_resume(monkeypatch: pytest.MonkeyPatch, *, tweaks) -> tuple[MagicMock, list]:
    """Drive the real ``generate_flow_events`` down the resume path.

    Only the checkpoint store, the restored graph, and the service lookups are
    stubbed; the build loop under test is the production one. Returns the
    restored graph and the recorded ``process_tweaks_on_graph`` calls.
    """
    graph = _restored_graph()

    chat_service = MagicMock()
    chat_service.set_cache = AsyncMock()
    monkeypatch.setattr(build_module, "get_chat_service", lambda: chat_service)
    monkeypatch.setattr(build_module, "get_telemetry_service", lambda: MagicMock())

    job_service = MagicMock()
    job_service.get_pending_human_request = AsyncMock(return_value=None)
    monkeypatch.setattr(build_module, "get_job_service", lambda: job_service)

    store = MagicMock()
    store.load_by_run_id = AsyncMock(return_value=object())
    monkeypatch.setattr("lfx.services.deps.get_checkpoint_service", lambda: store)

    from lfx.graph.graph.base import Graph as LfxGraph

    monkeypatch.setattr(
        LfxGraph,
        "resume_from_checkpoint",
        classmethod(lambda _cls, _checkpoint, **_kwargs: graph),
    )

    tweak_calls: list = []
    monkeypatch.setattr(
        build_module,
        "process_tweaks_on_graph",
        lambda g, t: tweak_calls.append((g, t)),
    )

    await build_module.generate_flow_events(
        flow_id=uuid4(),
        background_tasks=BackgroundTasks(),
        event_manager=create_default_event_manager(asyncio.Queue()),
        inputs=None,
        data=None,
        files=None,
        stop_component_id=None,
        start_component_id=None,
        log_builds=False,
        current_user=_user(),
        flow_name="flow",
        job_id=uuid4(),
        resume={"request_id": "Ask:job-1", "decision": {"action_id": "reject"}},
        tweaks=tweaks,
        track_job_status=False,
        expose_error_details=False,
    )
    return graph, tweak_calls


async def test_resume_reapplies_the_runs_tweaks_to_the_restored_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    graph, tweak_calls = await _drive_resume(monkeypatch, tweaks=_TWEAKS)

    assert tweak_calls == [(graph, _TWEAKS)]


async def test_resume_without_tweaks_does_not_touch_the_restored_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    _graph, tweak_calls = await _drive_resume(monkeypatch, tweaks=None)

    assert tweak_calls == []
