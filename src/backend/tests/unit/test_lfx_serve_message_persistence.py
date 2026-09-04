"""Regression coverage for message persistence through the lfx serve v2 API."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from lfx.cli.commands import build_registry_from_paths
from lfx.cli.flow_store import NullFlowStore
from lfx.cli.serve_app import create_multi_serve_app
from lfx.services.database.service import NoopDatabaseService
from lfx.services.deps import get_db_service
from lfx.services.manager import ServiceManager


def test_v2_sync_and_stream_chat_flow_keep_noop_database(monkeypatch):
    """DB-less serve runs must not create Langflow persistence between chat vertices."""
    from lfx.services import manager as manager_module

    service_manager = ServiceManager()
    monkeypatch.setattr(manager_module, "_service_manager", service_manager)
    monkeypatch.setenv("LANGFLOW_API_KEY", "test-key")

    repo_root = Path(__file__).parents[4]
    flow_path = repo_root / "src/lfx/tests/data/simple_chat_no_llm.json"
    registry = asyncio.run(
        build_registry_from_paths(
            [flow_path],
            lambda _message: None,
            check_variables=True,
            store=NullFlowStore(),
        )
    )
    flow_id = registry.list_metas()[0].id

    with TestClient(create_multi_serve_app(registry=registry)) as client:
        sync_response = client.post(
            "/api/v2/workflows?mode=sync",
            json={"flow_id": flow_id, "input_value": "hello"},
            headers={"x-api-key": "test-key"},
        )
        stream_response = client.post(
            "/api/v2/workflows",
            json={
                "flow_id": flow_id,
                "input_value": "hello",
                "mode": "stream",
                "stream_protocol": "agui",
            },
            headers={"x-api-key": "test-key"},
        )

    assert sync_response.status_code == 200, sync_response.text
    body = sync_response.json()
    assert body["status"] == "completed", body["errors"]
    assert body["output"]["text"] == "hello"

    assert stream_response.status_code == 200, stream_response.text
    assert "RUN_FINISHED" in stream_response.text
    assert "hello" in stream_response.text
    assert isinstance(get_db_service(), NoopDatabaseService)
