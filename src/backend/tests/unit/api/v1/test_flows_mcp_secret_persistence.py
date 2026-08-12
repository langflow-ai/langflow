"""A saved flow must not carry an MCP credential in ``flow.data``.

``flow.data`` is an unencrypted JSON column that travels through export, share and
version history. ``cleanMcpConfig`` scrubbed it on those three paths only, never on
save, so registering a project as an MCP server left the auto-minted key sitting in
plaintext in every flow that used it.

Scrubbing is forward-only: the secret moves into the ``mcp_server`` row, which is
encrypted at rest and which ``resolve_mcp_config`` already prefers at runtime, so a
scrubbed flow keeps running unchanged. Flows saved before this are left alone.
"""

import uuid

from fastapi import status
from httpx import AsyncClient
from langflow.api.utils.mcp.flow_secrets import variable_name_for

SECRET = "sk-mcp-should-never-persist"  # noqa: S105


def _flow_payload(server_name: str, config: dict) -> dict:
    return {
        "name": f"mcp-secret-flow-{uuid.uuid4().hex[:8]}",
        "description": "flow carrying an MCP server config",
        "data": {
            "nodes": [
                {
                    "id": "MCPTools-abc12",
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "id": "MCPTools-abc12",
                        "type": "MCPTools",
                        "node": {
                            "template": {
                                "mcp_server": {
                                    "type": "mcp",
                                    "name": "mcp_server",
                                    "value": {"name": server_name, "config": config},
                                }
                            }
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


async def _saved_flow(client: AsyncClient, headers, server_name: str, config: dict) -> tuple[dict, str]:
    response = await client.post("api/v1/flows/", json=_flow_payload(server_name, config), headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json(), response.text


def _stored_config(flow: dict) -> dict:
    node = flow["data"]["nodes"][0]
    return node["data"]["node"]["template"]["mcp_server"]["value"]["config"]


async def test_should_not_persist_header_secret_on_create(client: AsyncClient, logged_in_headers):
    server_name = f"billing-{uuid.uuid4().hex[:6]}"
    config = {
        "url": "https://serving.internal/mcp",
        "headers": {"x-api-key": SECRET},
    }

    flow, raw = await _saved_flow(client, logged_in_headers, server_name, config)

    assert SECRET not in raw
    assert _stored_config(flow)["headers"] == {"x-api-key": variable_name_for(server_name, "x-api-key")}


async def test_should_keep_non_secret_config_intact(client: AsyncClient, logged_in_headers):
    """Blanking the credential must not cost the flow its target."""
    server_name = f"billing-{uuid.uuid4().hex[:6]}"
    config = {
        "url": "https://serving.internal/mcp",
        "mode": "Streamable_HTTP",
        "headers": {"x-api-key": SECRET},
    }

    flow, _ = await _saved_flow(client, logged_in_headers, server_name, config)

    stored = _stored_config(flow)
    assert stored["url"] == "https://serving.internal/mcp"
    assert stored["mode"] == "Streamable_HTTP"


async def test_should_move_the_secret_into_the_mcp_server_row(client: AsyncClient, logged_in_headers):
    """Dropping the value without storing it would break the next run."""
    server_name = f"billing-{uuid.uuid4().hex[:6]}"
    config = {"url": "https://serving.internal/mcp", "headers": {"x-api-key": SECRET}}

    await _saved_flow(client, logged_in_headers, server_name, config)

    response = await client.get(f"api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    stored = response.json()

    assert stored is not None, "the secret must survive somewhere the runtime can reach"
    assert stored["headers"]["x-api-key"] == SECRET


async def test_should_scrub_env_secrets_on_a_stdio_config(client: AsyncClient, logged_in_headers):
    server_name = f"local-{uuid.uuid4().hex[:6]}"
    config = {"command": "uvx", "args": ["some-server"], "env": {"API_TOKEN": SECRET}}

    flow, raw = await _saved_flow(client, logged_in_headers, server_name, config)

    assert SECRET not in raw
    assert _stored_config(flow)["env"] == {"API_TOKEN": variable_name_for(server_name, "API_TOKEN")}


async def test_should_scrub_a_secret_hidden_in_proxy_args(client: AsyncClient, logged_in_headers):
    """Auto-install bakes the minted key into ``--headers x-api-key <key>``."""
    server_name = f"proxy-{uuid.uuid4().hex[:6]}"
    config = {
        "command": "uvx",
        "args": ["mcp-proxy", "--headers", "x-api-key", SECRET, "https://serving.internal/mcp"],
    }

    _, raw = await _saved_flow(client, logged_in_headers, server_name, config)

    assert SECRET not in raw


async def test_should_scrub_on_update_too(client: AsyncClient, logged_in_headers):
    """A flow saved clean can still have a credential pasted into it later."""
    server_name = f"billing-{uuid.uuid4().hex[:6]}"
    flow, _ = await _saved_flow(client, logged_in_headers, server_name, {"url": "https://serving.internal/mcp"})

    payload = _flow_payload(server_name, {"url": "https://serving.internal/mcp", "headers": {"x-api-key": SECRET}})
    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": payload["data"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert SECRET not in response.text


async def test_should_leave_a_static_config_untouched(client: AsyncClient, logged_in_headers):
    """No secret means no rewrite and no row written."""
    server_name = f"static-{uuid.uuid4().hex[:6]}"
    config = {"url": "https://serving.internal/mcp", "mode": "Streamable_HTTP"}

    flow, _ = await _saved_flow(client, logged_in_headers, server_name, config)

    assert _stored_config(flow) == config
