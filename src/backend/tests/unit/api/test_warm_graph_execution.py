"""Focused import and execution-mode contracts for warm graph copies."""

from __future__ import annotations

import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langflow.api import warm_graph
from langflow.processing.process import process_tweaks
from langflow.services.warm_registry.service import flow_version


class _FakeVertex:
    def __init__(self, raw_params: dict, *, load_from_db_fields: list[str] | None = None) -> None:
        self.raw_params = raw_params.copy()
        self.params = raw_params.copy()
        template = {key: {"value": value} for key, value in raw_params.items()}
        for field_name in load_from_db_fields or []:
            template[field_name]["load_from_db"] = True
        self.full_data = {
            "data": {
                "node": {
                    "template": template,
                }
            }
        }
        self.load_from_db_fields = list(load_from_db_fields or [])
        self.updated_raw_params = False

    def update_raw_params(self, new_params: dict, *, overwrite: bool = False) -> None:
        assert overwrite is True
        self.raw_params.update(new_params)
        self.params = self.raw_params.copy()
        self.updated_raw_params = True


class _FakeGraph:
    def __init__(self, vertices: list[_FakeVertex]) -> None:
        self.vertices = vertices
        self.user_id = None
        self.session_id = None
        self.constructor_stream: bool | None = None
        self.constructor_template_stream: dict | None = None
        self.has_session_id_vertices: list[str] = []

    def get_vertex(self, _vertex_id: str):
        return None

    def copy_for_run(self, *, user_id: str | None, before_instantiate=None):
        copied = deepcopy(self)
        copied.user_id = user_id
        if before_instantiate is not None:
            before_instantiate(copied)
        copied.constructor_stream = copied.vertices[0].params.get("stream") if copied.vertices else None
        if copied.vertices:
            copied.constructor_template_stream = copied.vertices[0].full_data["data"]["node"]["template"].get("stream")
        return copied


def _grouped_stream_graph(*, expose_stream: bool):
    from lfx.graph import Graph

    stream_field = {
        "name": "stream",
        "type": "bool",
        "value": True,
        "list": False,
        "show": True,
        "advanced": False,
    }
    child = {
        "id": "child-1",
        "type": "genericNode",
        "data": {
            "id": "child-1",
            "type": "Generic",
            "node": {
                "template": {"_type": "Generic", "stream": stream_field},
                "base_classes": [],
                "display_name": "Child",
                "outputs": [],
            },
        },
    }
    group_template = {}
    if expose_stream:
        group_template["stream"] = {
            **stream_field,
            "proxy": {"field": "stream", "id": "child-1"},
        }
    group = {
        "id": "group-1",
        "type": "genericNode",
        "data": {
            "id": "group-1",
            "type": "Group",
            "node": {
                "template": group_template,
                "flow": {"data": {"nodes": [child], "edges": []}},
            },
        },
    }
    graph = Graph(flow_id="flow-id", instantiate_components=False)
    graph.add_nodes_and_edges([group], [])
    return graph


def test_warm_graph_has_a_clean_import_path() -> None:
    """Importing the low-level helper must not initialize the v1 router package."""
    repo_root = Path(__file__).resolve().parents[5]
    python_path = os.pathsep.join(
        [
            str(repo_root / "src" / "backend" / "base"),
            str(repo_root / "src" / "lfx" / "src"),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    env = {**os.environ, "PYTHONPATH": python_path}
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            ("import sys; import langflow.api.warm_graph; assert 'langflow.api.v1' not in sys.modules; print('clean')"),
        ],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "clean"


@pytest.mark.parametrize(("stream", "stored_value"), [(True, False), (False, True)])
async def test_warm_deepcopy_matches_cold_implicit_stream_tweak_without_mutating_template(
    monkeypatch: pytest.MonkeyPatch,
    stream,
    stored_value,
) -> None:
    """Warm copies force the run mode just as ``process_tweaks`` does cold."""
    from langflow.services import deps
    from langflow.services.warm_registry import service as registry_service

    template = _FakeGraph(
        [
            _FakeVertex({"stream": stored_value}, load_from_db_fields=["stream"]),
            _FakeVertex({"temperature": 0.2}),
            _FakeVertex({"stream": stored_value}),
        ]
    )
    registry = SimpleNamespace(get=lambda _flow_id: (template, "v1"))
    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _settings: True)
    monkeypatch.setattr(deps, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace()))
    monkeypatch.setattr(registry_service, "get_warm_registry", lambda: registry)

    graph = await warm_graph.warm_deepcopy(
        "flow-id",
        expected_version="v1",
        user_id="user-id",
        session_id="session-id",
        stream=stream,
    )

    cold_payload = {
        "nodes": [
            {
                "id": "model",
                "data": {
                    "node": {
                        "display_name": "Model",
                        "template": {
                            "stream": {
                                "type": "bool",
                                "show": True,
                                "value": stored_value,
                                "load_from_db": True,
                            }
                        },
                    }
                },
            }
        ],
        "edges": [],
    }
    cold_result = process_tweaks(deepcopy(cold_payload), {}, stream=stream)
    cold_stream_field = cold_result["nodes"][0]["data"]["node"]["template"]["stream"]

    assert graph is not None
    assert graph is not template
    assert graph.vertices[0].params["stream"] is cold_stream_field["value"] is stream
    assert graph.constructor_stream is stream
    assert graph.constructor_template_stream["value"] is cold_stream_field["value"] is stream
    assert graph.constructor_template_stream["load_from_db"] is cold_stream_field["load_from_db"] is False
    assert "stream" not in graph.vertices[0].load_from_db_fields
    assert graph.vertices[0].updated_raw_params is True
    assert graph.vertices[1].params == {"temperature": 0.2}
    assert "load_from_db" not in graph.vertices[2].full_data["data"]["node"]["template"]["stream"]
    assert graph.user_id == "user-id"
    assert graph.session_id == "session-id"

    # Only the request-local deepcopy changes; the shared registry template stays pristine.
    assert template.vertices[0].params["stream"] is stored_value
    assert template.vertices[0].load_from_db_fields == ["stream"]
    assert template.vertices[0].updated_raw_params is False


@pytest.mark.parametrize(("expose_stream", "expected"), [(False, True), (True, False)])
def test_warm_stream_tweak_matches_cold_group_proxy_scope(monkeypatch, expose_stream, expected) -> None:
    """Hidden grouped fields stay persisted; exposed proxies receive the tweak."""
    from lfx.graph import Graph

    monkeypatch.setattr(Graph, "_instantiate_components_in_vertices", lambda _graph: None)
    template = _grouped_stream_graph(expose_stream=expose_stream)
    run_graph = template.copy_for_run(
        user_id="caller-id",
        before_instantiate=lambda graph: warm_graph._apply_implicit_stream_tweak(graph, stream=False),
    )

    assert run_graph.get_vertex("child-1").raw_params["stream"] is expected
    assert template.get_vertex("child-1").raw_params["stream"] is True


async def test_warm_deepcopy_rejects_a_graph_from_another_flow_revision(monkeypatch) -> None:
    """Execution must cold-fallback when the authorized FlowRead revision differs."""
    from langflow.services import deps
    from langflow.services.warm_registry import service as registry_service

    template = _FakeGraph([_FakeVertex({"stream": False})])
    registry = SimpleNamespace(get=lambda _flow_id: (template, "cached-version"))
    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _settings: True)
    monkeypatch.setattr(deps, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace()))
    monkeypatch.setattr(registry_service, "get_warm_registry", lambda: registry)

    graph = await warm_graph.warm_deepcopy(
        "flow-id",
        expected_version="authorized-version",
        user_id="user-id",
        session_id=None,
    )

    assert graph is None


async def test_warm_deepcopy_cold_falls_back_when_extension_events_need_user_keyspace(monkeypatch) -> None:
    """Migrated/error-bearing templates must replay parsing under the caller."""
    from langflow.services import deps
    from langflow.services.warm_registry import service as registry_service

    template = _FakeGraph([_FakeVertex({"stream": False})])
    template.requires_extension_event_replay = True
    template.copy_for_run = Mock(side_effect=AssertionError("extension-event graph was copied"))
    registry = SimpleNamespace(get=lambda _flow_id: (template, "v1"))
    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _settings: True)
    monkeypatch.setattr(deps, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace()))
    monkeypatch.setattr(registry_service, "get_warm_registry", lambda: registry)

    graph = await warm_graph.warm_deepcopy(
        "flow-id",
        expected_version="v1",
        user_id="user-id",
        session_id=None,
    )

    assert graph is None
    template.copy_for_run.assert_not_called()


async def test_warm_deepcopy_revalidates_current_component_policy(monkeypatch) -> None:
    """A policy change after preload must reject the cached graph before copying it."""
    from langflow.services import deps
    from langflow.services.warm_registry import service as registry_service
    from lfx.utils import flow_validation

    template = _FakeGraph([_FakeVertex({"stream": False})])
    template.copy_for_run = Mock(side_effect=AssertionError("blocked graph was copied"))
    registry = SimpleNamespace(get=lambda _flow_id: (template, "v1"))
    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _settings: True)
    monkeypatch.setattr(deps, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace()))
    monkeypatch.setattr(registry_service, "get_warm_registry", lambda: registry)

    class PolicyChangedError(ValueError):
        pass

    def _reject(_target) -> None:
        message = "component is now blocked"
        raise PolicyChangedError(message)

    monkeypatch.setattr(flow_validation, "validate_flow_for_current_settings", _reject)

    with pytest.raises(PolicyChangedError, match="now blocked"):
        await warm_graph.warm_deepcopy(
            "flow-id",
            expected_version="v1",
            user_id="user-id",
            session_id=None,
        )

    template.copy_for_run.assert_not_called()


async def test_v1_streaming_run_requests_a_streaming_warm_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    """The V1 streaming flag reaches the warm-copy stream-mode override."""
    from langflow.api.v1 import endpoints
    from langflow.api.v1.schemas import SimplifiedAPIRequest

    captured: dict = {}
    graph = SimpleNamespace(vertices=[], run_id=None)

    def set_run_id(run_id) -> None:
        graph.run_id = str(run_id)

    graph.set_run_id = set_run_id

    async def fake_warm_deepcopy(flow_id, *, expected_version, user_id, session_id, stream=False):
        captured.update(
            flow_id=flow_id,
            expected_version=expected_version,
            user_id=user_id,
            session_id=session_id,
            stream=stream,
        )
        return graph

    job_service = SimpleNamespace(
        create_job=AsyncMock(),
        execute_with_status=AsyncMock(return_value=([], "effective-session")),
    )
    monkeypatch.setattr(warm_graph, "warm_deepcopy", fake_warm_deepcopy)
    monkeypatch.setattr(endpoints, "get_job_service", lambda: job_service)
    monkeypatch.setattr(
        endpoints,
        "get_task_service",
        lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()),
    )
    monkeypatch.setattr(endpoints, "get_memory_base_service", lambda: SimpleNamespace(on_flow_output=AsyncMock()))
    monkeypatch.setattr(endpoints, "process_tweaks", Mock(side_effect=AssertionError("cold path used")))

    flow_id = uuid4()
    user_id = uuid4()
    updated_at = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)
    result = await endpoints.simple_run_flow(
        flow=SimpleNamespace(
            id=flow_id,
            user_id=user_id,
            name="warm",
            data={"nodes": [], "edges": []},
            updated_at=updated_at,
        ),
        input_request=SimplifiedAPIRequest(session_id="v1-session"),
        stream=True,
        api_key_user=SimpleNamespace(id=user_id, is_superuser=False),
    )

    assert result.session_id == "effective-session"
    assert captured == {
        "flow_id": str(flow_id),
        "expected_version": flow_version(updated_at),
        "user_id": user_id,
        "session_id": "v1-session",
        "stream": True,
    }


async def test_v2_sync_run_requests_a_non_streaming_warm_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    """The V2 sync warm path explicitly overrides persisted streaming defaults."""
    from langflow.api.v2 import workflow_execution
    from lfx.workflow.converters import ParsedWorkflowRun

    captured: dict = {}
    graph = SimpleNamespace(vertices=[], run_id=None, get_terminal_nodes=list)

    def set_run_id(run_id) -> None:
        graph.run_id = str(run_id)

    graph.set_run_id = set_run_id

    async def fake_warm_deepcopy(flow_id, *, expected_version, user_id, session_id, stream=False):
        captured.update(
            flow_id=flow_id,
            expected_version=expected_version,
            user_id=user_id,
            session_id=session_id,
            stream=stream,
        )
        return graph

    job_service = SimpleNamespace(
        create_job=AsyncMock(),
        execute_with_status=AsyncMock(return_value=([], "effective-session")),
    )
    expected = object()
    monkeypatch.setattr(workflow_execution, "warm_deepcopy", fake_warm_deepcopy)
    monkeypatch.setattr(workflow_execution, "get_job_service", lambda: job_service)
    monkeypatch.setattr(
        workflow_execution,
        "get_task_service",
        lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()),
    )
    monkeypatch.setattr(
        workflow_execution,
        "get_memory_base_service",
        lambda: SimpleNamespace(on_flow_output=AsyncMock()),
    )
    monkeypatch.setattr(workflow_execution, "run_response_to_workflow_response", Mock(return_value=expected))
    monkeypatch.setattr(workflow_execution, "process_tweaks", Mock(side_effect=AssertionError("cold path used")))

    flow_id = uuid4()
    user_id = uuid4()
    updated_at = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)
    result = await workflow_execution.execute_sync_workflow(
        parsed=ParsedWorkflowRun(flow_id=str(flow_id), session_id="v2-session", mode="sync"),
        flow=SimpleNamespace(
            id=flow_id,
            user_id=user_id,
            name="warm",
            data={"nodes": [], "edges": []},
            updated_at=updated_at,
        ),
        job_id=uuid4(),
        current_user=SimpleNamespace(id=user_id),
        background_tasks=SimpleNamespace(),
        http_request=None,
    )

    assert result is expected
    assert captured == {
        "flow_id": str(flow_id),
        "expected_version": flow_version(updated_at),
        "user_id": str(user_id),
        "session_id": "v2-session",
        "stream": False,
    }
