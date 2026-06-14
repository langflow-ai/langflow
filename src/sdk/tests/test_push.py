"""Unit tests for lfx push / LangflowClient.upsert_flow.

Uses respx to mock HTTP without a live server.
"""
# pragma: allowlist secret -- all credentials in this file are fake test data

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest
import respx
from langflow_sdk.client import LangflowClient
from langflow_sdk.exceptions import LangflowHTTPError, LangflowNotFoundError

_BASE = "http://langflow.test"
_FLOW_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")

_FLOW_PAYLOAD = {
    "id": str(_FLOW_ID),
    "name": "Test Flow",
    "description": None,
    "data": {"nodes": [], "edges": []},
    "is_component": False,
    "updated_at": None,
    "endpoint_name": None,
    "tags": None,
    "folder_id": None,
    "user_id": None,
    "icon": None,
    "icon_bg_color": None,
    "locked": False,
    "mcp_enabled": False,
    "webhook": False,
    "access_type": "PRIVATE",
}


def _client() -> LangflowClient:
    return LangflowClient(base_url=_BASE, api_key="test-key")  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# upsert_flow -- create path (201)
# ---------------------------------------------------------------------------


@respx.mock
def test_upsert_flow_create():
    respx.put(f"{_BASE}/api/v1/flows/{_FLOW_ID}").mock(return_value=httpx.Response(201, json=_FLOW_PAYLOAD))
    from langflow_sdk.models import FlowCreate

    client = _client()
    flow, created = client.upsert_flow(_FLOW_ID, FlowCreate(name="Test Flow"))
    assert created is True
    assert flow.id == _FLOW_ID
    assert flow.name == "Test Flow"


# ---------------------------------------------------------------------------
# upsert_flow -- update path (200)
# ---------------------------------------------------------------------------


@respx.mock
def test_upsert_flow_update():
    respx.put(f"{_BASE}/api/v1/flows/{_FLOW_ID}").mock(return_value=httpx.Response(200, json=_FLOW_PAYLOAD))
    from langflow_sdk.models import FlowCreate

    client = _client()
    flow, created = client.upsert_flow(_FLOW_ID, FlowCreate(name="Test Flow"))
    assert created is False
    assert flow.id == _FLOW_ID


# ---------------------------------------------------------------------------
# upsert_flow -- 404 raises LangflowNotFoundError
# ---------------------------------------------------------------------------


@respx.mock
def test_upsert_flow_not_found_raises():
    respx.put(f"{_BASE}/api/v1/flows/{_FLOW_ID}").mock(
        return_value=httpx.Response(404, json={"detail": "Flow not found"})
    )
    from langflow_sdk.models import FlowCreate

    client = _client()
    with pytest.raises(LangflowNotFoundError):
        client.upsert_flow(_FLOW_ID, FlowCreate(name="Test Flow"))


# ---------------------------------------------------------------------------
# upsert_flow -- 409 conflict raises LangflowHTTPError
# ---------------------------------------------------------------------------


@respx.mock
def test_upsert_flow_conflict_raises():
    respx.put(f"{_BASE}/api/v1/flows/{_FLOW_ID}").mock(
        return_value=httpx.Response(409, json={"detail": "Name must be unique"})
    )
    from langflow_sdk.models import FlowCreate

    client = _client()
    with pytest.raises(LangflowHTTPError) as exc_info:
        client.upsert_flow(_FLOW_ID, FlowCreate(name="Test Flow"))
    from http import HTTPStatus

    assert exc_info.value.status_code == HTTPStatus.CONFLICT


# ---------------------------------------------------------------------------
# push_command integration (file-based, mocked HTTP)
# ---------------------------------------------------------------------------


@respx.mock
def test_push_command_creates_flow(tmp_path: Path):
    """push_command reads a JSON file and calls upsert_flow."""
    flow_file = tmp_path / "my_flow.json"
    flow_file.write_text(
        json.dumps(
            {
                "id": str(_FLOW_ID),
                "name": "My Flow",
                "data": {"nodes": [], "edges": []},
            }
        ),
        encoding="utf-8",
    )

    respx.put(f"{_BASE}/api/v1/flows/{_FLOW_ID}").mock(return_value=httpx.Response(201, json=_FLOW_PAYLOAD))
    # projects list (empty -- no project targeting in this test)
    respx.get(f"{_BASE}/api/v1/projects/").mock(return_value=httpx.Response(200, json=[]))

    # Write an environments config
    env_file = tmp_path / "langflow-environments.toml"
    env_file.write_text(
        f'[environments.test]\nurl = "{_BASE}"\n',
        encoding="utf-8",
    )

    from lfx.cli.push import push_command

    # Should not raise
    push_command(
        flow_paths=[str(flow_file)],
        env="test",
        dir_path=None,
        project=None,
        project_id=None,
        environments_file=str(env_file),
        dry_run=False,
        normalize=False,
        strip_secrets=False,
    )


@respx.mock
def test_push_command_dry_run_makes_no_requests(tmp_path: Path):
    """Dry-run must not make any mutating HTTP calls."""
    flow_file = tmp_path / "flow.json"
    flow_file.write_text(
        json.dumps({"id": str(_FLOW_ID), "name": "F", "data": {"nodes": [], "edges": []}}),
        encoding="utf-8",
    )

    env_file = tmp_path / "langflow-environments.toml"
    env_file.write_text(
        f'[environments.test]\nurl = "{_BASE}"\n',
        encoding="utf-8",
    )

    # Register NO respx routes -- if any request is made the test will fail
    from lfx.cli.push import push_command

    push_command(
        flow_paths=[str(flow_file)],
        env="test",
        dir_path=None,
        project=None,
        project_id=None,
        environments_file=str(env_file),
        dry_run=True,
        normalize=False,
        strip_secrets=False,
    )


@respx.mock
def test_push_command_project_dir(tmp_path: Path):
    """--dir pushes all *.json files and creates the project if needed."""
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir()

    flow_ids = [
        UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        UUID("bbbbbbbb-0000-0000-0000-000000000002"),
    ]
    for i, fid in enumerate(flow_ids):
        f = flows_dir / f"flow_{i}.json"
        f.write_text(
            json.dumps({"id": str(fid), "name": f"Flow {i}", "data": {"nodes": [], "edges": []}}),
            encoding="utf-8",
        )

    project_id = UUID("cccccccc-0000-0000-0000-000000000001")
    project_payload = {"id": str(project_id), "name": "My Project", "description": None, "parent_id": None}

    respx.get(f"{_BASE}/api/v1/projects/").mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{_BASE}/api/v1/projects/").mock(return_value=httpx.Response(201, json=project_payload))

    for fid in flow_ids:
        payload = {**_FLOW_PAYLOAD, "id": str(fid)}
        respx.put(f"{_BASE}/api/v1/flows/{fid}").mock(return_value=httpx.Response(201, json=payload))

    env_file = tmp_path / "langflow-environments.toml"
    env_file.write_text(
        f'[environments.test]\nurl = "{_BASE}"\n',
        encoding="utf-8",
    )

    from lfx.cli.push import push_command

    push_command(
        flow_paths=[],
        env="test",
        dir_path=str(flows_dir),
        project="My Project",
        project_id=None,
        environments_file=str(env_file),
        dry_run=False,
        normalize=False,
        strip_secrets=False,
    )
