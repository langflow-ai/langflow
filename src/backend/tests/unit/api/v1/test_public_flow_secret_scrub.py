"""Regression tests for LE-1676 / H1-3724458.

The unauthenticated ``GET /api/v1/flows/public_flow/{flow_id}`` endpoint must not
leak the flow owner's stored secrets. Every template field marked ``password``
(API keys, tokens, passwords, connection strings) has its value stripped before
the flow is returned to anonymous callers.
"""

import json

from fastapi import status
from httpx import AsyncClient
from langflow.api.utils.core import strip_secret_field_values


def _flow_payload() -> dict:
    """A flow whose first node carries two secret fields and one public field."""
    return {
        "name": "le1676-secret-leak-flow",
        "description": "regression flow for public-flow secret scrubbing",
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "id": "node-1",
                        "type": "OpenAIModel",
                        "node": {
                            "template": {
                                # name matches API terms -> caught by remove_api_keys too
                                "api_key": {
                                    "name": "api_key",
                                    "password": True,
                                    "value": "sk-SUPERSECRET",  # pragma: allowlist secret
                                    "type": "str",
                                },
                                # password field whose name does NOT look like an API key:
                                # only the stricter strip_secret_field_values nulls this one.
                                "service_token": {
                                    "name": "service_token",
                                    "password": True,
                                    "value": "tok-DEADBEEF",  # pragma: allowlist secret
                                    "type": "str",
                                },
                                # non-secret field must be preserved
                                "base_url": {
                                    "name": "base_url",
                                    "password": False,
                                    "value": "https://api.openai.com/v1",
                                    "type": "str",
                                },
                            }
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


# ---------------------------------------------------------------------------
# Unit tests for the pure helper
# ---------------------------------------------------------------------------


def test_strip_secret_field_values_nulls_all_password_fields():
    data = _flow_payload()["data"]
    scrubbed = strip_secret_field_values(data)
    template = scrubbed["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] is None
    assert template["service_token"]["value"] is None
    # non-secret field preserved
    assert template["base_url"]["value"] == "https://api.openai.com/v1"


def test_strip_secret_field_values_does_not_mutate_input():
    data = _flow_payload()["data"]
    original_secret = data["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]
    strip_secret_field_values(data)
    # input untouched (deep copy returned) so the ORM object is never altered
    assert data["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == original_secret


def test_strip_secret_field_values_handles_none_and_empty():
    assert strip_secret_field_values(None) is None
    assert strip_secret_field_values({}) == {}


def test_strip_secret_field_values_tolerates_malformed_nodes():
    # Non-dict nodes / missing keys must not raise.
    data = {
        "nodes": [
            "not-a-dict",
            {"id": "x"},
            {"id": "y", "data": "not-a-dict"},
            {"id": "z", "data": {"node": {"template": "not-a-dict"}}},
            {"id": "ok", "data": {"node": {"template": {"pw": {"password": True, "value": "s"}}}}},
        ]
    }
    scrubbed = strip_secret_field_values(data)
    assert scrubbed["nodes"][-1]["data"]["node"]["template"]["pw"]["value"] is None


# ---------------------------------------------------------------------------
# Integration test through the unauthenticated endpoint
# ---------------------------------------------------------------------------


async def test_public_flow_read_strips_secrets(client: AsyncClient, logged_in_headers):
    # Create a flow that contains secret field values.
    create_resp = await client.post(
        "api/v1/flows/", json=json.loads(json.dumps(_flow_payload())), headers=logged_in_headers
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    flow_id = create_resp.json()["id"]

    # Make it public.
    patch_resp = await client.patch(
        f"api/v1/flows/{flow_id}", json={"access_type": "PUBLIC"}, headers=logged_in_headers
    )
    assert patch_resp.status_code == status.HTTP_200_OK

    # Read it as an anonymous caller (drop auth cookies).
    client.cookies.clear()
    resp = await client.get(f"api/v1/flows/public_flow/{flow_id}")
    assert resp.status_code == status.HTTP_200_OK

    template = resp.json()["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] is None, "API key leaked through public flow read"
    assert template["service_token"]["value"] is None, "non-api-named secret leaked through public flow read"
    assert template["base_url"]["value"] == "https://api.openai.com/v1", "non-secret field should be preserved"
