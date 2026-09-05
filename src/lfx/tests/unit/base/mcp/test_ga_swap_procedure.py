"""Exercise the GA-swap procedure on one sample action.

``design/dedicated-integrations/ga-swap-procedure.md`` claims that a provider
bundle can move an action from its REST/SDK adapter to the provider's official
MCP server *without changing component identity or the saved-flow schema*.  This
module is the executable form of that claim: one action is written twice -- once
REST-backed, once pinned to an MCP server -- and the tests below hold the
invariants the procedure promises, then prove the pinned half fails closed when
the server drifts.

The recorded ``tools/list`` is
``fixtures/slack-mcp-tools-list.synthetic.json``: a hand-written, Slack-*shaped*
fixture that is clearly labeled synthetic inside the file.  It is deliberately
not evidence.  Moving a real Slack action to MCP still needs the dated
authenticated capture named in ``decisions/substrate-slack.md``'s re-open
trigger, which does not exist yet; that is why the sample action here belongs to
a fictional ``example`` provider instead of to ``lfx-slack``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.mcp.pinned import pinned_spec_from_capabilities, tools_list_digest
from lfx.base.mcp.preset import MCPPresetComponent
from lfx.base.mcp.util import MCPServerInfo
from lfx.custom.custom_component.component import Component
from lfx.integrations.capabilities import IntegrationCapability
from lfx.integrations.errors import IncompatibleToolError
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.dataframe import DataFrame

FIXTURE = Path(__file__).parent / "fixtures" / "slack-mcp-tools-list.synthetic.json"
UPDATE_TOOLS_TARGET = "lfx.base.mcp.preset.update_tools"
PINNED_URL = "https://mcp.example.com/mcp"

MATCHES = [
    {"permalink": "https://example.invalid/archives/C1/p1", "text": "the orders report is late", "ts": "1.1"},
    {"permalink": "https://example.invalid/archives/C1/p2", "text": "orders are back to normal", "ts": "2.2"},
]


def _recording() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _tool_named(recording: dict[str, Any], name: str) -> dict[str, Any]:
    for tool in recording["result"]["tools"]:
        if tool["name"] == name:
            return tool
    msg = f"{name} is not in the recording"
    raise AssertionError(msg)


# --------------------------------------------------------------- the manifest
# Everything above the substrate line is what the swap must leave alone.
_SHARED_CAPABILITY_FIELDS: dict[str, Any] = {
    "display_name": "Example: Search Messages",
    "auth_profile_id": "example-user-oauth",
    "identity": "user_delegated",
    "required_scopes": ("search:read",),
    "policy_keys": ("integrations.example.user.search",),
    "maturity": "ga",
    "deployment_contexts": ("hosted", "self_managed"),
    "risk": "read",
    "component_ref": "ExampleSearchMessages",
}

REST_CAPABILITY: dict[str, Any] = {
    "id": "example.user.search",
    **_SHARED_CAPABILITY_FIELDS,
    "substrate": "rest",
}


def _pin_for(tool_name: str, recording: dict[str, Any]) -> dict[str, Any]:
    tool = _tool_named(recording, tool_name)
    server_info = recording["_initialize_result"]["serverInfo"]
    return {
        "server_url": PINNED_URL,
        "input_schema": tool["inputSchema"],
        "output_schema": tool["outputSchema"],
        "tools_list_hash": tools_list_digest(recording["result"]["tools"]),
        "server_name": server_info["name"],
        "server_version": server_info["version"],
    }


def mcp_capabilities(recording: dict[str, Any] | None = None) -> list[IntegrationCapability]:
    """The post-swap manifest: every tool the pinned server may expose is pinned."""
    recording = recording or _recording()
    search = IntegrationCapability(
        **{
            "id": "example.user.search",
            **_SHARED_CAPABILITY_FIELDS,
            "substrate": "mcp",
            "mcp_tool": "example_search_messages",
            "mcp_pin": _pin_for("example_search_messages", recording),
        }
    )
    history = IntegrationCapability(
        id="example.user.read_history",
        display_name="Example: Read Channel History",
        auth_profile_id="example-user-oauth",
        identity="user_delegated",
        required_scopes=("channels:history",),
        policy_keys=("integrations.example.user.read_history",),
        substrate="mcp",
        maturity="ga",
        deployment_contexts=("hosted", "self_managed"),
        risk="read",
        component_ref="ExampleReadChannelHistory",
        mcp_tool="example_read_channel_history",
        mcp_pin=_pin_for("example_read_channel_history", recording),
    )
    return [search, history]


# ------------------------------------------------------------- the two halves
_SAMPLE_INPUTS = [
    MessageTextInput(name="query", display_name="Query", info="Search terms.", required=True, tool_mode=True),
    IntInput(name="limit", display_name="Limit", info="Maximum number of matches.", value=20, advanced=True),
]
_SAMPLE_OUTPUTS = [Output(display_name="Matches", name="matches", method="search", types=["DataFrame"])]


async def _fake_rest_search(query: str, limit: int) -> list[dict[str, Any]]:
    """Stands in for the provider's Web API client in the pre-swap adapter."""
    return [dict(match) for match in MATCHES[:limit] if query in match["text"]]


class ExampleSearchMessagesRest(Component):
    """Before the swap: same identity, REST adapter."""

    display_name = "Example: Search Messages"
    description = "Search messages the calling user can see."
    icon = "Search"
    name = "ExampleSearchMessages"
    inputs = _SAMPLE_INPUTS
    outputs = _SAMPLE_OUTPUTS

    async def search(self) -> DataFrame:
        rows = await _fake_rest_search(self.query, int(self.limit))
        frame = DataFrame(rows)
        self.status = frame
        return frame


class ExampleSearchMessagesPinned(MCPPresetComponent):
    """After the swap: same identity, same inputs and output, pinned MCP adapter.

    The node shape is preserved by *not* declaring ``preset_control_inputs``: a
    single-action pinned component takes its tool from the pin and builds the
    arguments from its own declared inputs, so no Tool dropdown or raw-JSON
    argument box appears where the REST version had none.
    """

    display_name = "Example: Search Messages"
    description = "Search messages the calling user can see."
    icon = "Search"
    name = "ExampleSearchMessages"
    integration_provider_id = "example"
    add_tool_output = False
    inputs = _SAMPLE_INPUTS
    outputs = _SAMPLE_OUTPUTS

    capabilities: list[IntegrationCapability] | None = None

    @property
    def tool(self) -> str:
        return "example_search_messages"

    @property
    def tool_arguments(self) -> dict[str, Any]:
        arguments: dict[str, Any] = {"query": self.query}
        if self.limit is not None:
            arguments["limit"] = int(self.limit)
        return arguments

    def _pinned_spec(self):
        return pinned_spec_from_capabilities(self.capabilities or mcp_capabilities())

    def _mcp_server_config(self):
        return "example-workspace-mcp", {"headers": {"Authorization": "Bearer token"}}

    async def search(self) -> DataFrame:
        return await self.run_tool()


# ------------------------------------------------------------------- doubles
def _tool_double(spec: dict[str, Any]):
    async def coroutine(**kwargs):
        payload = [match for match in MATCHES if kwargs.get("query", "") in match["text"]]
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(payload))])

    return SimpleNamespace(
        name=spec["name"],
        description=spec.get("description", ""),
        coroutine=coroutine,
        metadata={
            "server_name": "example-workspace-mcp",
            "input_schema": spec["inputSchema"],
            "output_schema": spec.get("outputSchema"),
        },
    )


def _engine_for(recording: dict[str, Any]):
    tools = [_tool_double(spec) for spec in recording["result"]["tools"]]
    return AsyncMock(return_value=("Streamable_HTTP", tools, {tool.name: tool for tool in tools}))


def _pinned_component(recording: dict[str, Any] | None = None) -> ExampleSearchMessagesPinned:
    recording = recording or _recording()
    component = ExampleSearchMessagesPinned()
    component.query = "orders"
    component.limit = 20
    component.tool_execution_timeout = 0.0
    component.verify_ssl = True
    component.capabilities = mcp_capabilities()
    server_info = recording["_initialize_result"]["serverInfo"]
    component._streamable_http_client = SimpleNamespace(
        server_info=MCPServerInfo(name=server_info["name"], version=server_info["version"])
    )
    return component


def _rest_component() -> ExampleSearchMessagesRest:
    component = ExampleSearchMessagesRest()
    component.query = "orders"
    component.limit = 20
    return component


# ------------------------------------------------------- the fixture is honest
def test_the_recorded_tools_list_is_labeled_synthetic():
    recording = _recording()
    assert recording["_synthetic"] is True
    assert "NOT A CAPTURE" in recording["_label"]
    assert "mcp.slack.com" in recording["_warning"]


# ------------------------------------------------- invariants of the procedure
def test_component_identity_survives_the_swap():
    assert ExampleSearchMessagesPinned.name == ExampleSearchMessagesRest.name
    assert ExampleSearchMessagesPinned.display_name == ExampleSearchMessagesRest.display_name
    assert ExampleSearchMessagesPinned.description == ExampleSearchMessagesRest.description
    assert ExampleSearchMessagesPinned.icon == ExampleSearchMessagesRest.icon


def test_saved_flow_schema_survives_the_swap():
    """Field names, types, and requiredness are what a saved flow stores."""

    def shape(component: type[Component]) -> list[tuple]:
        return [
            (item.name, type(item).__name__, item.display_name, getattr(item, "required", False))
            for item in component.inputs
        ]

    def outputs(component: type[Component]) -> list[tuple]:
        return [(item.name, item.display_name, item.method, tuple(item.types or ())) for item in component.outputs]

    assert shape(ExampleSearchMessagesPinned) == shape(ExampleSearchMessagesRest)
    assert outputs(ExampleSearchMessagesPinned) == outputs(ExampleSearchMessagesRest)
    # The preset control inputs would have changed the node shape; a pinned
    # single-action component must not declare them.
    assert {item.name for item in ExampleSearchMessagesPinned.inputs} == {"query", "limit"}


def test_only_the_substrate_fields_change_in_the_manifest():
    after = mcp_capabilities()[0].model_dump()
    before = IntegrationCapability(**REST_CAPABILITY).model_dump()
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {"substrate", "mcp_tool", "mcp_pin"}
    assert after["id"] == before["id"] == "example.user.search"
    assert after["policy_keys"] == before["policy_keys"]
    assert after["component_ref"] == before["component_ref"]
    assert after["required_scopes"] == before["required_scopes"]


def test_the_pin_reproduces_the_recorded_tools_list_digest():
    recording = _recording()
    spec = pinned_spec_from_capabilities(mcp_capabilities(recording))
    assert spec.tools_list_hash == tools_list_digest(recording["result"]["tools"])
    assert spec.digest() == spec.tools_list_hash
    assert set(spec.names) == {tool["name"] for tool in recording["result"]["tools"]}


# ---------------------------------------------------------- the swapped action
async def test_both_halves_return_the_same_rows_for_one_saved_flow():
    rest_rows = (await _rest_component().search()).to_dict(orient="records")
    with patch(UPDATE_TOOLS_TARGET, new=_engine_for(_recording())):
        pinned_rows = (await _pinned_component().search()).to_dict(orient="records")
    assert pinned_rows == rest_rows == MATCHES


async def test_the_swapped_action_connects_only_to_the_pinned_endpoint():
    with patch(UPDATE_TOOLS_TARGET, new=_engine_for(_recording())) as engine:
        await _pinned_component().search()
    _, config = engine.await_args.args[:2]
    assert config["url"] == PINNED_URL
    assert config["allow_sse_fallback"] is False


# ------------------------------------------------------------- drift, at GA
def _with_added_tool(recording: dict[str, Any]) -> dict[str, Any]:
    recording["result"]["tools"].append(
        {
            "name": "example_delete_message",
            "description": "Delete a message.",
            "inputSchema": {"type": "object", "properties": {"ts": {"type": "string"}}, "required": ["ts"]},
        }
    )
    return recording


def _with_renamed_tool(recording: dict[str, Any]) -> dict[str, Any]:
    _tool_named(recording, "example_search_messages")["name"] = "example_search_messages_v2"
    return recording


def _with_removed_tool(recording: dict[str, Any]) -> dict[str, Any]:
    recording["result"]["tools"] = [
        tool for tool in recording["result"]["tools"] if tool["name"] != "example_read_channel_history"
    ]
    return recording


def _with_widened_arguments(recording: dict[str, Any]) -> dict[str, Any]:
    tool = _tool_named(recording, "example_search_messages")
    tool["inputSchema"]["properties"]["cursor"] = {"type": "string"}
    return recording


def _with_drifted_results(recording: dict[str, Any]) -> dict[str, Any]:
    tool = _tool_named(recording, "example_search_messages")
    tool["outputSchema"]["properties"]["hits"] = tool["outputSchema"]["properties"].pop("matches")
    tool["outputSchema"]["required"] = ["hits"]
    return recording


@pytest.mark.parametrize(
    ("mutate", "expected_key", "expected_value"),
    [
        (_with_added_tool, "added", ["example_delete_message"]),
        (_with_removed_tool, "removed", ["example_read_channel_history"]),
        (_with_renamed_tool, "renamed", ["example_search_messages -> example_search_messages_v2"]),
        (_with_widened_arguments, "changed", ["example_search_messages: argument schema"]),
        (_with_drifted_results, "changed", ["example_search_messages: result schema"]),
    ],
)
async def test_the_pinned_action_fails_closed_when_the_server_drifts(mutate, expected_key, expected_value):
    drifted = mutate(copy.deepcopy(_recording()))
    component = _pinned_component()
    with patch(UPDATE_TOOLS_TARGET, new=_engine_for(drifted)), pytest.raises(IncompatibleToolError) as excinfo:
        await component.search()
    assert excinfo.value.code == "incompatible-tool"
    assert excinfo.value.details[expected_key] == expected_value
    # The digest pin catches the same drift a second time, independently.
    assert excinfo.value.details["server"]


async def test_the_pinned_action_fails_closed_when_the_server_version_moves():
    component = _pinned_component()
    component._streamable_http_client = SimpleNamespace(
        server_info=MCPServerInfo(name="example-workspace-mcp", version="2026.10.0")
    )
    with patch(UPDATE_TOOLS_TARGET, new=_engine_for(_recording())), pytest.raises(IncompatibleToolError) as excinfo:
        await component.search()
    assert excinfo.value.details["server"] == [
        "server version 2026.10.0 does not match the pinned 2026.09.1",
    ]


async def test_the_pinned_action_rejects_arguments_outside_the_recorded_schema():
    """The swap must not widen the action: the pinned schema is the contract."""
    component = _pinned_component()
    with patch(UPDATE_TOOLS_TARGET, new=_engine_for(_recording())):
        tools, _ = await component._load_tools()
        with pytest.raises(IncompatibleToolError) as excinfo:
            await tools[0].coroutine(query="orders", cursor="page-2")
    assert excinfo.value.details["unexpected"] == ["cursor"]
