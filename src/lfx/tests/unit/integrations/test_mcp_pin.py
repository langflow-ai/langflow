"""Manifest-level validation of the MCP action pin (INT-9).

The pin is manifest data so that moving an action from an SDK/REST adapter to
MCP is a manifest change, not a component rewrite.  These tests hold the rule
that makes that safe: a capability whose substrate is ``mcp`` is rejected unless
it names its tool AND freezes the endpoint and the argument/result schemas.
"""

from __future__ import annotations

import pytest
from lfx.extension.integration_manifest import IntegrationCapabilityManifest
from lfx.integrations import McpToolPin
from lfx.integrations.capabilities import IntegrationCapability
from pydantic import ValidationError

SERVER_URL = "https://mcp.example.com/mcp"
INPUT_SCHEMA = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}


def _capability(**overrides) -> dict:
    base = {
        "id": "example.user.search",
        "display_name": "Example: Search Messages",
        "auth_profile_id": "example-user-oauth",
        "identity": "user_delegated",
        "policy_keys": ("integrations.example.user.search",),
        "substrate": "mcp",
        "maturity": "ga",
        "deployment_contexts": ("hosted",),
        "risk": "read",
        "mcp_tool": "search_messages",
        "mcp_pin": {"server_url": SERVER_URL, "input_schema": INPUT_SCHEMA},
    }
    return {**base, **overrides}


def test_pinned_mcp_capability_validates():
    capability = IntegrationCapability(**_capability())
    assert capability.mcp_pin is not None
    assert capability.mcp_pin.server_url == SERVER_URL
    assert capability.mcp_pin.transport == "streamable_http"
    assert capability.mcp_pin.output_schema is None


def test_mcp_capability_without_a_pin_is_rejected():
    with pytest.raises(ValidationError, match="must declare mcp_pin"):
        IntegrationCapability(**_capability(mcp_pin=None))


def test_mcp_capability_without_a_tool_id_is_rejected():
    with pytest.raises(ValidationError, match="must declare mcp_tool"):
        IntegrationCapability(**_capability(mcp_tool=None, component_ref="ExampleSearch"))


def test_a_pin_on_a_rest_capability_is_rejected():
    payload = _capability(substrate="rest", mcp_tool=None, component_ref="ExampleSearch")
    with pytest.raises(ValidationError, match="only valid on a capability whose substrate is 'mcp'"):
        IntegrationCapability(**payload)


def test_rest_and_sdk_capabilities_still_validate_without_a_pin():
    payload = _capability(substrate="rest", mcp_tool=None, mcp_pin=None, component_ref="ExampleSearch")
    assert IntegrationCapability(**payload).mcp_pin is None


def test_pin_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        McpToolPin(server_url=SERVER_URL, input_schema=INPUT_SCHEMA, expected_version="2.1.0")


def test_pin_rejects_an_unsupported_transport():
    with pytest.raises(ValidationError):
        McpToolPin(server_url=SERVER_URL, input_schema=INPUT_SCHEMA, transport="sse")


def test_a_bundle_manifest_carries_the_pin_at_schema_version_1():
    """The pin is additive: a manifest that uses it stays on ``schema_version`` 1."""
    manifest = IntegrationCapabilityManifest.model_validate(
        {
            "schema_version": 1,
            "provider_id": "example",
            "display_name": "Example",
            "auth_profiles": [
                {"id": "example-user-oauth", "kind": "oauth2_authorization_code", "identity": "user_delegated"}
            ],
            "capabilities": [
                _capability(
                    mcp_pin={
                        "server_url": SERVER_URL,
                        "input_schema": INPUT_SCHEMA,
                        "output_schema": {"type": "object"},
                        "tools_list_hash": "sha256:abc",
                        "server_name": "example",
                        "server_version": "2.1.0",
                    }
                )
            ],
        }
    )
    pin = manifest.capabilities[0].mcp_pin
    assert pin is not None
    assert pin.tools_list_hash == "sha256:abc"
    assert pin.server_version == "2.1.0"
