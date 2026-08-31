"""Tests for server-provenanced public-flow storage scopes."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from langflow.api.v1.schemas import FlowDataRequest
from lfx.events.event_manager import create_default_event_manager
from lfx.graph.vertex.base import Vertex
from lfx.utils.file_path_security import LocalFileAccessError


@pytest.mark.parametrize("use_sanitized_data", [False, True])
async def test_generate_flow_events_sets_source_flow_provenance_for_public_graph(monkeypatch, use_sanitized_data):
    import langflow.api.build as build_module

    virtual_flow_id = uuid.uuid4()
    source_flow_id = uuid.uuid4()
    user_id = uuid.uuid4()
    graph = MagicMock()
    graph.source_flow_id = None
    graph.flow_id = str(source_flow_id)
    graph.session_id = str(virtual_flow_id)
    graph.run_id = None
    graph.vertices = []
    graph.vertices_to_run = set()
    graph.sort_vertices.return_value = []
    graph.set_run_id.side_effect = lambda value: setattr(graph, "run_id", value)
    graph.end_all_traces = AsyncMock()

    chat_service = MagicMock()
    chat_service.set_cache = AsyncMock()
    telemetry_service = MagicMock()

    @asynccontextmanager
    async def fake_session_scope():
        yield MagicMock()

    build_from_db = AsyncMock(return_value=graph)
    build_from_data = AsyncMock(return_value=graph)
    monkeypatch.setattr(build_module, "get_chat_service", lambda: chat_service)
    monkeypatch.setattr(build_module, "get_telemetry_service", lambda: telemetry_service)
    monkeypatch.setattr(build_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(build_module, "build_graph_from_db", build_from_db)
    monkeypatch.setattr(build_module, "build_graph_from_data", build_from_data)

    data = FlowDataRequest(nodes=[], edges=[]) if use_sanitized_data else None
    await build_module.generate_flow_events(
        flow_id=virtual_flow_id,
        source_flow_id=source_flow_id,
        background_tasks=BackgroundTasks(),
        event_manager=create_default_event_manager(asyncio.Queue()),
        inputs=None,
        data=data,
        files=None,
        stop_component_id=None,
        start_component_id=None,
        log_builds=False,
        current_user=SimpleNamespace(id=user_id),
        flow_name="public-flow",
        track_job_status=False,
        expose_error_details=False,
    )

    assert graph.source_flow_id == str(source_flow_id)
    assert graph.flow_id == str(virtual_flow_id)
    if use_sanitized_data:
        build_from_data.assert_awaited_once()
        assert build_from_data.await_args.kwargs["flow_id"] == str(source_flow_id)
        build_from_db.assert_not_awaited()
    else:
        build_from_db.assert_awaited_once()
        build_from_data.assert_not_awaited()


async def test_generate_flow_events_maps_rejected_file_tweaks_to_bad_request(monkeypatch):
    import langflow.api.build as build_module

    flow_id = uuid.uuid4()
    user_id = uuid.uuid4()
    vertex = MagicMock(spec=Vertex)
    vertex.id = "file-node"
    # The tweak only reaches update_raw_params if the template declares the
    # field, so the stand-in needs a real node payload rather than bare mocks.
    vertex.data = {"node": {"template": {"file": {"type": "file", "value": ""}}}}
    vertex.params = {}
    vertex.load_from_db_fields = []
    rejection = "FileInput path is outside the authenticated user's storage scope."
    vertex.update_raw_params.side_effect = LocalFileAccessError(rejection)
    graph = MagicMock()
    graph.vertices = [vertex]

    chat_service = MagicMock()
    telemetry_service = MagicMock()

    @asynccontextmanager
    async def fake_session_scope():
        yield MagicMock()

    monkeypatch.setattr(build_module, "get_chat_service", lambda: chat_service)
    monkeypatch.setattr(build_module, "get_telemetry_service", lambda: telemetry_service)
    monkeypatch.setattr(build_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(build_module, "build_graph_from_db", AsyncMock(return_value=graph))
    unexpected_log = AsyncMock()
    monkeypatch.setattr(build_module.logger, "aexception", unexpected_log)

    with pytest.raises(HTTPException) as exc_info:
        await build_module.generate_flow_events(
            flow_id=flow_id,
            background_tasks=BackgroundTasks(),
            event_manager=create_default_event_manager(asyncio.Queue()),
            inputs=None,
            data=None,
            files=None,
            stop_component_id=None,
            start_component_id=None,
            log_builds=False,
            current_user=SimpleNamespace(id=user_id),
            tweaks={"file-node": {"file": "other-flow/secret.txt"}},
            track_job_status=False,
            expose_error_details=True,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == rejection
    unexpected_log.assert_not_awaited()
