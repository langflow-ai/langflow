"""Unit tests for ``lfx.base.mcp.pinned``: the pinned action-to-tool engine.

Every case here is a way an official MCP server can drift away from what a
bundle pinned -- a tool added, removed, renamed, or re-shaped, a server version
or ``tools/list`` digest that moved -- and every one of them must fail closed
with the typed ``incompatible-tool`` error rather than degrade to whatever the
server currently offers.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from lfx.base.mcp.pinned import (
    DiscoveredTool,
    PinnedServerSpec,
    PinnedToolSpec,
    diff_pinned_tools,
    discovered_tool,
    enforce_pinned_tools,
    pinned_spec_from_capabilities,
    tools_list_digest,
    validate_pinned_arguments,
)
from lfx.base.mcp.util import MCPServerInfo
from lfx.integrations.capabilities import IntegrationCapability, McpToolPin
from lfx.integrations.errors import INTEGRATION_ERROR_CODES, IncompatibleToolError

SERVER_URL = "https://mcp.example.com/mcp"

SEARCH_INPUT = {
    "type": "object",
    "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    "required": ["query"],
    "additionalProperties": False,
}
SEARCH_OUTPUT = {"type": "object", "properties": {"messages": {"type": "array"}}}
POST_INPUT = {
    "type": "object",
    "properties": {"channel": {"type": "string"}, "text": {"type": "string"}},
    "required": ["channel", "text"],
    "additionalProperties": False,
}


def _pin(**overrides) -> PinnedServerSpec:
    base = {
        "server_url": SERVER_URL,
        "tools": (
            PinnedToolSpec(name="search_messages", input_schema=SEARCH_INPUT, output_schema=SEARCH_OUTPUT),
            PinnedToolSpec(name="post_message", input_schema=POST_INPUT),
        ),
    }
    return PinnedServerSpec(**{**base, **overrides})


def _found(name: str, input_schema: dict, output_schema: dict | None = None) -> DiscoveredTool:
    return DiscoveredTool(name=name, input_schema=input_schema, output_schema=output_schema)


def _matching() -> list[DiscoveredTool]:
    return [
        _found("search_messages", SEARCH_INPUT, SEARCH_OUTPUT),
        _found("post_message", POST_INPUT),
    ]


# ----------------------------------------------------------------------- digest
def test_digest_is_stable_across_key_and_tool_order():
    reordered_schema = {
        "additionalProperties": False,
        "required": ["query"],
        "properties": {"limit": {"type": "integer"}, "query": {"type": "string"}},
        "type": "object",
    }
    first = tools_list_digest(_matching())
    second = tools_list_digest(
        [_found("post_message", POST_INPUT), _found("search_messages", reordered_schema, SEARCH_OUTPUT)]
    )
    assert first == second
    assert first.startswith("sha256:")
    assert _pin().digest() == first


def test_digest_changes_when_a_schema_changes():
    widened = {**SEARCH_INPUT, "properties": {**SEARCH_INPUT["properties"], "cursor": {"type": "string"}}}
    assert tools_list_digest(_matching()) != tools_list_digest(
        [_found("search_messages", widened, SEARCH_OUTPUT), _found("post_message", POST_INPUT)]
    )


def test_discovered_tool_reads_raw_schemas_from_structured_tool_metadata():
    tool = SimpleNamespace(
        name="search_messages",
        metadata={"server_name": "slack", "input_schema": SEARCH_INPUT, "output_schema": SEARCH_OUTPUT},
    )
    view = discovered_tool(tool)
    assert view.name == "search_messages"
    assert view.input_schema == SEARCH_INPUT
    assert view.output_schema == SEARCH_OUTPUT


def test_a_tools_own_schema_attributes_do_not_shadow_the_recorded_ones():
    """A LangChain tool is a ``Runnable``, which owns ``input_schema``/``output_schema``.

    Those properties return pydantic model classes, not JSON Schema. Reading them
    ahead of ``metadata`` compared an empty schema against the pin and reported
    every real engine-built tool as re-shaped.
    """
    tool = SimpleNamespace(
        name="search_messages",
        metadata={"server_name": "slack", "input_schema": SEARCH_INPUT, "output_schema": SEARCH_OUTPUT},
        input_schema=SimpleNamespace,
        output_schema=SimpleNamespace,
    )
    view = discovered_tool(tool)
    assert view.input_schema == SEARCH_INPUT
    assert view.output_schema == SEARCH_OUTPUT


def test_discovered_tool_without_schemas_is_empty_not_none():
    view = discovered_tool(SimpleNamespace(name="x"))
    assert view.input_schema == {}
    assert view.output_schema is None


# ------------------------------------------------------------------------- diff
def test_matching_discovery_is_compatible():
    diff = diff_pinned_tools(_pin(), _matching())
    assert diff.is_compatible
    assert diff.summary() == "no difference"


def test_added_tool_fails_closed_and_names_the_addition():
    discovered = [*_matching(), _found("delete_message", {"type": "object", "properties": {}})]
    diff = diff_pinned_tools(_pin(), discovered)
    assert diff.added == ("delete_message",)
    assert not diff.removed
    assert not diff.is_compatible

    with pytest.raises(IncompatibleToolError) as excinfo:
        enforce_pinned_tools(_pin(), discovered, provider="slack")
    assert "delete_message" in str(excinfo.value.message)
    assert excinfo.value.details["added"] == ["delete_message"]


def test_removed_tool_fails_closed_with_no_partial_toolset():
    discovered = [_found("search_messages", SEARCH_INPUT, SEARCH_OUTPUT)]
    diff = diff_pinned_tools(_pin(), discovered)
    assert diff.removed == ("post_message",)
    with pytest.raises(IncompatibleToolError) as excinfo:
        enforce_pinned_tools(_pin(), discovered)
    assert "removed post_message" in excinfo.value.message


def test_empty_discovery_reports_every_pinned_tool_as_removed():
    diff = diff_pinned_tools(_pin(), [])
    assert set(diff.removed) == {"search_messages", "post_message"}
    assert not diff.is_compatible


def test_renamed_tool_is_reported_as_removed_plus_added_and_paired():
    discovered = [_found("slack_search_messages", SEARCH_INPUT, SEARCH_OUTPUT), _found("post_message", POST_INPUT)]
    diff = diff_pinned_tools(_pin(), discovered)
    assert diff.added == ("slack_search_messages",)
    assert diff.removed == ("search_messages",)
    assert diff.renamed == (("search_messages", "slack_search_messages"),)
    with pytest.raises(IncompatibleToolError) as excinfo:
        enforce_pinned_tools(_pin(), discovered)
    assert "renamed search_messages to slack_search_messages" in excinfo.value.message


def test_widened_argument_schema_fails_closed():
    widened = {**SEARCH_INPUT, "properties": {**SEARCH_INPUT["properties"], "cursor": {"type": "string"}}}
    discovered = [_found("search_messages", widened, SEARCH_OUTPUT), _found("post_message", POST_INPUT)]
    diff = diff_pinned_tools(_pin(), discovered)
    assert diff.changed == (("search_messages", "argument schema"),)
    assert not diff.is_compatible


def test_narrowed_argument_schema_fails_closed():
    narrowed = {**SEARCH_INPUT, "required": []}
    diff = diff_pinned_tools(
        _pin(), [_found("search_messages", narrowed, SEARCH_OUTPUT), _found("post_message", POST_INPUT)]
    )
    assert diff.changed == (("search_messages", "argument schema"),)


def test_result_schema_drift_fails_closed():
    drifted = {"type": "object", "properties": {"matches": {"type": "array"}}}
    diff = diff_pinned_tools(
        _pin(), [_found("search_messages", SEARCH_INPUT, drifted), _found("post_message", POST_INPUT)]
    )
    assert diff.changed == (("search_messages", "result schema"),)


def test_result_schema_appearing_where_none_was_pinned_fails_closed():
    discovered = [
        _found("search_messages", SEARCH_INPUT, SEARCH_OUTPUT),
        _found("post_message", POST_INPUT, {"type": "object"}),
    ]
    diff = diff_pinned_tools(_pin(), discovered)
    assert diff.changed == (("post_message", "result schema"),)


# ---------------------------------------------------------------- server pins
def test_tools_list_digest_mismatch_fails_closed():
    spec = _pin(tools_list_hash="sha256:0000")
    diff = diff_pinned_tools(spec, _matching())
    assert len(diff.server_mismatch) == 1
    assert "digest" in diff.server_mismatch[0]
    assert not diff.is_compatible


def test_matching_tools_list_digest_passes():
    spec = _pin(tools_list_hash=tools_list_digest(_matching()))
    assert diff_pinned_tools(spec, _matching()).is_compatible


def test_server_version_mismatch_fails_closed():
    spec = _pin(server_version="2.1.0")
    diff = diff_pinned_tools(spec, _matching(), server_info=MCPServerInfo(name="slack", version="2.2.0"))
    assert diff.server_mismatch == ("server version 2.2.0 does not match the pinned 2.1.0",)


def test_pinned_version_with_no_reported_version_fails_closed():
    """A server that stops publishing serverInfo is drift, not a free pass."""
    spec = _pin(server_version="2.1.0")
    diff = diff_pinned_tools(spec, _matching(), server_info=None)
    assert diff.server_mismatch == ("server version no version does not match the pinned 2.1.0",)


def test_unpinned_version_ignores_whatever_the_server_reports():
    diff = diff_pinned_tools(_pin(), _matching(), server_info=MCPServerInfo(name="slack", version="9.9.9"))
    assert diff.is_compatible


def test_server_name_mismatch_fails_closed():
    spec = _pin(server_name="slack")
    diff = diff_pinned_tools(spec, _matching(), server_info=MCPServerInfo(name="not-slack", version=None))
    assert diff.server_mismatch == ("server name not-slack does not match the pinned slack",)


# ---------------------------------------------------------------------- error
def test_incompatible_tool_error_is_in_the_code_vocabulary_and_is_sanitized():
    assert "incompatible-tool" in INTEGRATION_ERROR_CODES
    spec = _pin(server_url="https://user:s3cret@mcp.example.com/mcp")
    with pytest.raises(IncompatibleToolError) as excinfo:
        enforce_pinned_tools(spec, [], provider="slack")
    error = excinfo.value
    assert error.code == "incompatible-tool"
    assert error.retryable is False
    assert error.provider == "slack"
    assert "s3cret" not in error.message
    assert "s3cret" not in str(error)
    # ``safe_message`` is what a delegated caller sees; it names no endpoint at all.
    assert "mcp.example.com" not in error.safe_message


def test_enforce_returns_the_diff_when_everything_matches():
    diff = enforce_pinned_tools(_pin(), _matching())
    assert diff.is_compatible


# ------------------------------------------------------------------ arguments
def test_pinned_arguments_reject_unknown_keys():
    tool = _pin().tools[0]
    with pytest.raises(IncompatibleToolError) as excinfo:
        validate_pinned_arguments(tool, {"query": "orders", "cursor": "abc"})
    assert excinfo.value.details["unexpected"] == ["cursor"]


def test_a_missing_required_key_is_left_to_the_derived_args_schema():
    """An omitted field is a caller mistake, not provider drift.

    Calling it ``incompatible-tool`` would hand an agent a non-retryable error and
    tell an operator to upgrade a bundle that cannot fix it; the derived args
    schema already rejects it with a self-correctable message.
    """
    validate_pinned_arguments(_pin().tools[0], {"limit": 5})


def test_pinned_arguments_accept_the_pinned_shape():
    validate_pinned_arguments(_pin().tools[0], {"query": "orders", "limit": 5})


def test_pinned_arguments_allow_extras_only_when_the_pin_allows_them():
    tool = PinnedToolSpec(
        name="open",
        input_schema={"type": "object", "properties": {"id": {"type": "string"}}, "additionalProperties": True},
    )
    validate_pinned_arguments(tool, {"id": "1", "anything": True})


# ------------------------------------------------------------ manifest bridge
def _capability(action: str, tool: str, **pin_overrides) -> IntegrationCapability:
    pin = McpToolPin(
        server_url=SERVER_URL,
        input_schema=SEARCH_INPUT if tool == "search_messages" else POST_INPUT,
        output_schema=SEARCH_OUTPUT if tool == "search_messages" else None,
        **pin_overrides,
    )
    return IntegrationCapability(
        id=f"slack.user.{action}",
        display_name=f"Slack: {action}",
        auth_profile_id="slack-user-oauth",
        identity="user_delegated",
        policy_keys=(f"integrations.slack.user.{action}",),
        substrate="mcp",
        maturity="ga",
        deployment_contexts=("hosted",),
        risk="read",
        mcp_tool=tool,
        mcp_pin=pin,
    )


def test_pinned_spec_is_built_from_the_manifest_capabilities():
    capabilities = [_capability("search", "search_messages"), _capability("post", "post_message")]
    spec = pinned_spec_from_capabilities(capabilities)
    assert spec.server_url == SERVER_URL
    assert spec.names == ("search_messages", "post_message")
    assert diff_pinned_tools(spec, _matching()).is_compatible


def test_pinned_spec_rejects_capabilities_that_disagree_about_the_server():
    capabilities = [
        _capability("search", "search_messages"),
        _capability("post", "post_message", server_version="2.1.0"),
    ]
    with pytest.raises(ValueError, match="same server endpoint"):
        pinned_spec_from_capabilities(capabilities)


def test_pinned_spec_requires_at_least_one_mcp_capability():
    with pytest.raises(ValueError, match="nothing to pin"):
        pinned_spec_from_capabilities([])


def test_pinned_spec_accepts_a_hash_computed_over_exactly_the_pinned_tools():
    digest = tools_list_digest(_matching())
    capabilities = [
        _capability("search", "search_messages", tools_list_hash=digest),
        _capability("post", "post_message", tools_list_hash=digest),
    ]
    assert pinned_spec_from_capabilities(capabilities).tools_list_hash == digest


def test_pinned_spec_rejects_a_hash_that_is_not_the_digest_of_its_tools():
    """A hash taken over a wider recording than the manifest pins is a bundle error.

    Left unchecked it would surface at every load as an added tool plus a digest
    mismatch, which reads like the server drifted rather than like the pin is wrong.
    """
    whole_recording = tools_list_digest(_matching())
    with pytest.raises(ValueError, match="is not the digest of the pinned tools"):
        pinned_spec_from_capabilities([_capability("search", "search_messages", tools_list_hash=whole_recording)])
