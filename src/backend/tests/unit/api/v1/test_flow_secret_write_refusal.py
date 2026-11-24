"""A credential that cannot be stored securely must fail the flow write, visibly.

The refusal only protects anything if it reaches the caller. Every write path wraps the
scrub in broad exception handling, so this drives the real routes over HTTP and asserts
both halves: the request fails, and the secret is not in the flow that came back.
"""

import json

import pytest
from fastapi import status
from httpx import AsyncClient

SECRET = "sk-must-never-be-persisted"  # noqa: S105


def _flow_with_mcp_secret(name: str) -> dict:
    return {
        "name": name,
        "description": "carries an MCP credential",
        "data": {
            "nodes": [
                {
                    "id": "MCPTools-1",
                    "data": {
                        "id": "MCPTools-1",
                        "type": "MCPTools",
                        "node": {
                            "template": {
                                "mcp_server": {
                                    "value": {
                                        "name": "billing",
                                        "config": {
                                            "url": "https://billing.example/mcp",
                                            "headers": {"x-api-key": SECRET},
                                        },
                                    }
                                }
                            }
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


@pytest.fixture
def unstorable_variables(monkeypatch):
    """Every generated variable fails for a reason a retry cannot fix."""
    import langflow.api.utils.mcp.flow_secrets as module

    async def failing_ensure(variables, user_id, session):  # noqa: ARG001
        return set(variables)

    monkeypatch.setattr(module, "_ensure_variables", failing_ensure)


@pytest.mark.usefixtures("unstorable_variables")
async def test_create_flow_should_fail_instead_of_storing_the_secret(client: AsyncClient, logged_in_headers: dict):
    response = await client.post(
        "api/v1/flows/", json=_flow_with_mcp_secret("refuse-create"), headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert SECRET not in response.text


@pytest.mark.usefixtures("unstorable_variables")
async def test_batch_create_should_fail_instead_of_storing_the_secret(client: AsyncClient, logged_in_headers: dict):
    payload = {"flows": [_flow_with_mcp_secret("refuse-batch")]}

    response = await client.post("api/v1/flows/batch/", json=payload, headers=logged_in_headers)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert SECRET not in response.text


async def test_create_flow_should_succeed_and_scrub_when_the_variable_is_storable(
    client: AsyncClient, logged_in_headers: dict
):
    """The refusal must not fire on the happy path: the secret moves out, the flow saves."""
    response = await client.post("api/v1/flows/", json=_flow_with_mcp_secret("scrub-ok"), headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert SECRET not in json.dumps(body["data"])
    header_value = body["data"]["nodes"][0]["data"]["node"]["template"]["mcp_server"]["value"]["config"]["headers"][
        "x-api-key"
    ]
    assert header_value.startswith("MCP_")
