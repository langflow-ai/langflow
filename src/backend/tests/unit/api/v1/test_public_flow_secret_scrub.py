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


# ---------------------------------------------------------------------------
# Group node secret leak regression tests
# ---------------------------------------------------------------------------


def _flow_with_grouped_secret() -> dict:
    """A flow with a group node containing a secret field."""
    return {
        "name": "group-node-secret-leak-test",
        "description": "Test flow with secret in group node",
        "data": {
            "nodes": [
                {
                    "id": "group-node-1",
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "id": "group-node-1",
                        "type": "GroupNode",
                        "node": {
                            "display_name": "Group Node",
                            "description": "A group containing nested nodes",
                            "template": {
                                # Group node itself might have fields
                                "group_param": {
                                    "name": "group_param",
                                    "password": False,
                                    "value": "public-value",
                                    "type": "str",
                                }
                            },
                            # The nested flow inside the group node
                            "flow": {
                                "data": {
                                    "nodes": [
                                        {
                                            "id": "nested-node-1",
                                            "type": "genericNode",
                                            "position": {"x": 0, "y": 0},
                                            "data": {
                                                "id": "nested-node-1",
                                                "type": "OpenAIModel",
                                                "node": {
                                                    "template": {
                                                        "api_key": {
                                                            "name": "api_key",
                                                            "password": True,
                                                            "value": "sk-NESTED-SECRET",  # pragma: allowlist secret
                                                            "type": "str",
                                                        },
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
                                }
                            },
                        },
                    },
                },
                # Also include a top-level node with a secret to ensure we don't break existing functionality
                {
                    "id": "top-level-node",
                    "type": "genericNode",
                    "position": {"x": 100, "y": 100},
                    "data": {
                        "id": "top-level-node",
                        "type": "OpenAIModel",
                        "node": {
                            "template": {
                                "api_key": {
                                    "name": "api_key",
                                    "password": True,
                                    "value": "sk-TOP-LEVEL-SECRET",  # pragma: allowlist secret
                                    "type": "str",
                                },
                            }
                        },
                    },
                },
            ],
            "edges": [],
        },
    }


def _flow_with_deeply_nested_groups() -> dict:
    """A flow with multiple levels of nested group nodes."""
    return {
        "name": "deeply-nested-groups-test",
        "description": "Test flow with multiple nesting levels",
        "data": {
            "nodes": [
                {
                    "id": "outer-group",
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "id": "outer-group",
                        "type": "GroupNode",
                        "node": {
                            "template": {},
                            "flow": {
                                "data": {
                                    "nodes": [
                                        {
                                            "id": "inner-group",
                                            "type": "genericNode",
                                            "position": {"x": 0, "y": 0},
                                            "data": {
                                                "id": "inner-group",
                                                "type": "GroupNode",
                                                "node": {
                                                    "template": {},
                                                    "flow": {
                                                        "data": {
                                                            "nodes": [
                                                                {
                                                                    "id": "deeply-nested-node",
                                                                    "type": "genericNode",
                                                                    "position": {"x": 0, "y": 0},
                                                                    "data": {
                                                                        "id": "deeply-nested-node",
                                                                        "type": "OpenAIModel",
                                                                        "node": {
                                                                            "template": {
                                                                                "api_key": {
                                                                                    "name": "api_key",
                                                                                    "password": True,
                                                                                    # pragma: allowlist secret
                                                                                    "value": "sk-DEEPLY-NESTED-SECRET",
                                                                                    "type": "str",
                                                                                }
                                                                            }
                                                                        },
                                                                    },
                                                                }
                                                            ],
                                                            "edges": [],
                                                        }
                                                    },
                                                },
                                            },
                                        }
                                    ],
                                    "edges": [],
                                }
                            },
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


def test_strip_secret_field_values_handles_group_nodes():
    """Verify that secrets in group nodes are stripped."""
    data = _flow_with_grouped_secret()["data"]
    scrubbed = strip_secret_field_values(data)

    # Top-level secret should be stripped
    top_level_template = scrubbed["nodes"][1]["data"]["node"]["template"]
    assert top_level_template["api_key"]["value"] is None, "Top-level secret not stripped"

    # Nested secret in group node should also be stripped
    group_node = scrubbed["nodes"][0]
    nested_nodes = group_node["data"]["node"]["flow"]["data"]["nodes"]
    nested_template = nested_nodes[0]["data"]["node"]["template"]
    assert nested_template["api_key"]["value"] is None, "Nested secret in group node not stripped"

    # Non-secret field should be preserved
    assert nested_template["base_url"]["value"] == "https://api.openai.com/v1"


def test_strip_secret_field_values_handles_deeply_nested_groups():
    """Verify that secrets in deeply nested group nodes are stripped."""
    data = _flow_with_deeply_nested_groups()["data"]
    scrubbed = strip_secret_field_values(data)

    # Navigate to the deeply nested secret
    outer_group = scrubbed["nodes"][0]
    inner_group = outer_group["data"]["node"]["flow"]["data"]["nodes"][0]
    deeply_nested_node = inner_group["data"]["node"]["flow"]["data"]["nodes"][0]
    deeply_nested_template = deeply_nested_node["data"]["node"]["template"]

    assert deeply_nested_template["api_key"]["value"] is None, "Deeply nested secret not stripped"


def test_strip_secret_field_values_does_not_mutate_input_with_groups():
    """Verify that the input is not mutated when processing group nodes."""
    data = _flow_with_grouped_secret()["data"]
    original_secret = data["nodes"][0]["data"]["node"]["flow"]["data"]["nodes"][0]["data"]["node"]["template"][
        "api_key"
    ]["value"]

    strip_secret_field_values(data)

    # Input should be untouched (deep copy returned)
    current_secret = data["nodes"][0]["data"]["node"]["flow"]["data"]["nodes"][0]["data"]["node"]["template"][
        "api_key"
    ]["value"]
    assert current_secret == original_secret, "Input was mutated"


async def test_public_flow_with_group_node_strips_secrets(client: AsyncClient, logged_in_headers):
    """Integration test: verify group node secrets are stripped via public endpoint."""
    # Create a flow with a group node containing secrets
    create_resp = await client.post(
        "api/v1/flows/",
        json=json.loads(json.dumps(_flow_with_grouped_secret())),
        headers=logged_in_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    flow_id = create_resp.json()["id"]

    # Make it public
    patch_resp = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=logged_in_headers,
    )
    assert patch_resp.status_code == status.HTTP_200_OK

    # Read it as an anonymous caller
    client.cookies.clear()
    resp = await client.get(f"api/v1/flows/public_flow/{flow_id}")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()["data"]

    # Top-level secret should be stripped
    top_level_template = data["nodes"][1]["data"]["node"]["template"]
    assert top_level_template["api_key"]["value"] is None, "Top-level secret leaked"

    # Nested secret in group node should also be stripped
    group_node = data["nodes"][0]
    nested_nodes = group_node["data"]["node"]["flow"]["data"]["nodes"]
    nested_template = nested_nodes[0]["data"]["node"]["template"]
    assert nested_template["api_key"]["value"] is None, "Nested secret in group node leaked through public endpoint"

    # Non-secret field should be preserved
    assert nested_template["base_url"]["value"] == "https://api.openai.com/v1"
