"""Scrubbing MCP credentials on save must not disturb a flow saved before it.

The scrub is forward-only. A flow already in the database keeps its embedded config,
keeps resolving through the same precedence, and is never rewritten by being read,
listed, exported or patched on an unrelated field. These tests exist to fail loudly
if the write hook ever starts reaching backwards.
"""

import uuid
from uuid import UUID

from fastapi import status
from httpx import AsyncClient
from langflow.api.utils.mcp.flow_secrets import extract_and_strip_mcp_secrets
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from sqlmodel import select

SECRET = "sk-legacy-embedded-key"  # noqa: S105


def _legacy_flow_data(server_name: str) -> dict:
    """The shape a pre-scrub Langflow wrote: the credential sitting in the graph."""
    return {
        "nodes": [
            {
                "id": "MCPTools-legacy",
                "type": "genericNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "id": "MCPTools-legacy",
                    "type": "MCPTools",
                    "node": {
                        "template": {
                            "mcp_server": {
                                "type": "mcp",
                                "name": "mcp_server",
                                "value": {
                                    "name": server_name,
                                    "config": {
                                        "url": "https://serving.internal/mcp",
                                        "mode": "Streamable_HTTP",
                                        "headers": {"x-api-key": SECRET},
                                    },
                                },
                            }
                        }
                    },
                },
            }
        ],
        "edges": [],
    }


async def _insert_legacy_flow(client: AsyncClient, headers, server_name: str) -> str:
    """Land a pre-scrub row in the table.

    Create through the API, then write the graph straight to the column so the save hook
    never sees it — exactly the state an older release left behind.
    """
    created = await client.post(
        "api/v1/flows/",
        json={"name": f"legacy-mcp-{uuid.uuid4().hex[:8]}", "description": "pre-scrub", "data": {}},
        headers=headers,
    )
    assert created.status_code == status.HTTP_201_CREATED, created.text
    flow_id = created.json()["id"]

    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first()
        flow.data = _legacy_flow_data(server_name)
        session.add(flow)
        await session.commit()

    return flow_id


def _config_of(flow_data: dict) -> dict:
    return flow_data["nodes"][0]["data"]["node"]["template"]["mcp_server"]["value"]["config"]


async def test_should_not_rewrite_a_legacy_flow_on_read(client: AsyncClient, logged_in_headers):
    """Reading is not writing: the embedded credential must come back untouched."""
    flow_id = await _insert_legacy_flow(client, logged_in_headers, f"legacy-{uuid.uuid4().hex[:6]}")

    response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert _config_of(response.json()["data"])["headers"] == {"x-api-key": SECRET}


async def test_should_not_rewrite_a_legacy_flow_when_listing(client: AsyncClient, logged_in_headers):
    flow_id = await _insert_legacy_flow(client, logged_in_headers, f"legacy-{uuid.uuid4().hex[:6]}")

    response = await client.get("api/v1/flows/", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    listed = next(item for item in response.json() if item["id"] == flow_id)
    assert _config_of(listed["data"])["headers"] == {"x-api-key": SECRET}


async def test_should_leave_legacy_data_alone_when_patching_another_field(client: AsyncClient, logged_in_headers):
    """Renaming a flow must not silently strip a credential its deployment still needs."""
    flow_id = await _insert_legacy_flow(client, logged_in_headers, f"legacy-{uuid.uuid4().hex[:6]}")

    response = await client.patch(
        f"api/v1/flows/{flow_id}", json={"description": "renamed only"}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert _config_of(response.json()["data"])["headers"] == {"x-api-key": SECRET}


async def test_should_keep_serving_the_legacy_credential_to_the_runtime(client: AsyncClient, logged_in_headers):
    """The runtime reads the flow graph; a legacy flow must still hand it a usable config."""
    flow_id = await _insert_legacy_flow(client, logged_in_headers, f"legacy-{uuid.uuid4().hex[:6]}")

    response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    config = _config_of(response.json()["data"])

    assert config["url"] == "https://serving.internal/mcp"
    assert config["mode"] == "Streamable_HTTP"
    assert config["headers"]["x-api-key"] == SECRET


async def test_should_still_export_a_legacy_flow(client: AsyncClient, logged_in_headers):
    """Export already scrubbed on its own path; that must keep working, not double-fail."""
    flow_id = await _insert_legacy_flow(client, logged_in_headers, f"legacy-{uuid.uuid4().hex[:6]}")

    response = await client.post("api/v1/flows/download/", json=[flow_id], headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text


def test_should_not_touch_a_flow_without_any_mcp_node():
    """The hook runs on every write, so a graph with no MCP node must come out identical."""
    flow_data = {
        "nodes": [
            {
                "id": "ChatInput-1",
                "data": {
                    "id": "ChatInput-1",
                    "type": "ChatInput",
                    "node": {"template": {"input_value": {"value": "hi"}}},
                },
            }
        ],
        "edges": [],
    }
    before = str(flow_data)

    carried, variables = extract_and_strip_mcp_secrets(flow_data)

    assert carried == []
    assert variables == {}
    assert str(flow_data) == before


def test_should_not_touch_an_mcp_node_without_secrets():
    flow_data = _legacy_flow_data("static")
    _config_of(flow_data).pop("headers")
    before = str(flow_data)

    carried, variables = extract_and_strip_mcp_secrets(flow_data)

    assert carried == []
    assert variables == {}
    assert str(flow_data) == before


def test_should_tolerate_a_malformed_mcp_value():
    """A hand-edited or half-migrated flow must not crash the save path."""
    flow_data = _legacy_flow_data("broken")
    flow_data["nodes"][0]["data"]["node"]["template"]["mcp_server"]["value"] = "not-a-dict"

    assert extract_and_strip_mcp_secrets(flow_data) == ([], {})


def test_should_tolerate_flow_data_without_nodes():
    assert extract_and_strip_mcp_secrets({}) == ([], {})
    assert extract_and_strip_mcp_secrets(None) == ([], {})
    assert extract_and_strip_mcp_secrets({"nodes": None}) == ([], {})


async def test_should_carry_the_credential_when_a_legacy_flow_is_resaved(client: AsyncClient, logged_in_headers):
    """The migration moment: an old flow re-saved with its graph gets scrubbed.

    That is the intended forward-only behavior, but it must not strand the deployment —
    the literal has to land somewhere the runtime can still reach before it leaves the
    graph, otherwise the next run of a flow the user merely reopened starts failing.
    """
    server_name = f"legacy-resave-{uuid.uuid4().hex[:6]}"
    flow_id = await _insert_legacy_flow(client, logged_in_headers, server_name)

    stored = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    response = await client.patch(
        f"api/v1/flows/{flow_id}", json={"data": stored.json()["data"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert SECRET not in response.text, "the re-save must not leave the literal behind"

    reference = _config_of(response.json()["data"])["headers"]["x-api-key"]
    assert reference.startswith("MCP_"), f"expected a variable reference, got {reference!r}"

    variables = await client.get("api/v1/variables/", headers=logged_in_headers)
    assert reference in [item["name"] for item in variables.json()], "the reference must resolve to a real variable"

    server = await client.get(f"api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert server.json()["headers"]["x-api-key"] == SECRET, "the runtime must still find the credential"
