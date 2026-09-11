"""Every scenario in the audit log PRD, executed against the real API.

The rows this suite protects are the ones an investigation starts from: a save
somebody was refused, an edit somebody made, and the guarantee that neither ever
carries a secret.
"""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.deps import get_settings_service

SECRET = "sk-never-write-me-down"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture
def audit_on():
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = True
    yield
    settings.audit_enabled = original


@pytest.fixture
def audit_off():
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = False
    yield
    settings.audit_enabled = original


def _graph(label: str, *, secret: str = "") -> dict:
    return {
        "nodes": [
            {
                "id": "agent-1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "node": {
                        "display_name": "Agent",
                        "template": {
                            "_type": "Component",
                            "model_name": {"value": label},
                            "api_key": {"value": secret, "password": True},
                        },
                    }
                },
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


async def _create_flow(client: AsyncClient, headers) -> dict:
    response = await client.post(
        "api/v1/flows/",
        json={"name": f"audit-{uuid.uuid4()}", "data": _graph("gpt-4")},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _trail(client: AsyncClient, headers, flow_id: str) -> list[dict]:
    response = await client.get(f"api/v1/audit/flow/{flow_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["entries"]


async def test_an_accepted_edit_names_who_and_what(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("gpt-5")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = await _trail(client, logged_in_headers, flow["id"])
    updates = [e for e in entries if e["event"] == "langflow.audit.flow.updated"]

    assert len(updates) == 1
    assert updates[0]["payload"]["changes"] == ["Agent.model_name"]
    assert updates[0]["username"]
    assert updates[0]["resource_type"] == "flow"


async def test_creation_is_recorded(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    entries = await _trail(client, logged_in_headers, flow["id"])

    assert [e["event"] for e in entries] == ["langflow.audit.flow.created"]


async def test_a_row_never_carries_a_secret_or_a_graph(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)
    await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("gpt-4", secret=SECRET)},
        headers=logged_in_headers,
    )

    entries = await _trail(client, logged_in_headers, flow["id"])
    body = str(entries)

    assert "Agent.api_key" in body, "the field must be named"
    assert SECRET not in body, "the value must never be stored"
    assert "nodes" not in body, "no graph fragment may be stored"


async def test_a_rename_records_nothing(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"name": f"renamed-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = await _trail(client, logged_in_headers, flow["id"])

    assert [e["event"] for e in entries] == ["langflow.audit.flow.created"]


async def test_the_reader_is_closed_when_the_flag_is_off(client: AsyncClient, logged_in_headers, audit_off):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    response = await client.get(f"api/v1/audit/flow/{flow['id']}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_nothing_is_written_when_the_flag_is_off(
    client: AsyncClient,
    logged_in_headers,
    audit_off,  # noqa: ARG001
):
    flow = await _create_flow(client, logged_in_headers)
    settings = get_settings_service().settings

    settings.audit_enabled = True
    try:
        entries = await _trail(client, logged_in_headers, flow["id"])
    finally:
        settings.audit_enabled = False

    assert entries == []


async def test_an_unknown_resource_type_is_not_readable(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    response = await client.get(f"api/v1/audit/model_provider/{uuid.uuid4()}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
