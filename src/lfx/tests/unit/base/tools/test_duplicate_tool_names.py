"""Same-type components wired as separate Agent tools must stay distinguishable.

Reported failure (Langflow 1.12.3, reproduced locally on 1.12.5): two
components of the same type, each configured differently and each wired as
its own tool into one Agent's ``Tools`` input (e.g. two A2A Agent nodes
pointing at two different remote agents), register under the *identical*
LLM-facing tool name.

``_derive_tool_name`` names a tool from the component's class and its output
method -- both class-level constants, identical across every instance of that
class -- and nothing between the toolkit and the LLM resolves the duplicate.
Confirmed live on the running server: two URL nodes wired into one Agent both
registered as ``fetch_content``; the model formed two correctly targeted
calls and *both* executed against the first node (``build_start`` fired twice
for the same component id, never for the second node).

The toolkit cannot see the collision: it builds one component's tools at a
time. The agent aggregating every connected tool is the first place the whole
set is visible, so that is where duplicates are resolved -- and only for the
names that actually collide, because a tool name is the key the saved flow's
``tools_metadata`` rows match on (renaming an uncontested tool would drop the
user's Actions-panel edits, and drop the tool entirely at runtime).
"""

from __future__ import annotations

import pytest
from langchain_core.tools import StructuredTool
from lfx.base.tools.component_tool import ComponentToolkit, disambiguate_tool_names
from lfx.base.tools.constants import TOOL_OUTPUT_NAME
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.inputs.inputs import MessageTextInput
from lfx.io import HandleInput, Output
from lfx.schema.message import Message

# --- Test components ---------------------------------------------------


class RemoteAgentCall(Component):
    """Mirrors the reported case: one output, a descriptive method name.

    ``target`` is the per-instance configuration that decides what the tool
    actually does, exactly like the A2A Agent node's selected agent.
    """

    display_name = "Remote Agent Call"
    description = "Send a message to a remote agent and return its reply."
    name = "RemoteAgentCall"

    inputs = [
        MessageTextInput(name="target", display_name="Target"),
        MessageTextInput(name="input_value", display_name="Message", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="send_to_agent"),
        Output(display_name="Toolset", name=TOOL_OUTPUT_NAME, method="to_toolkit", types=["Tool"]),
    ]

    def send_to_agent(self) -> Message:
        return Message(text=f"{self.target} answered: {self.input_value}")


class SingleGenericOutput(Component):
    """Takes the class-name branch of ``_derive_tool_name`` instead."""

    display_name = "Single Generic Output"
    description = "Returns a fixed label."
    name = "SingleGenericOutput"

    inputs = [MessageTextInput(name="label", display_name="Label", tool_mode=True)]

    outputs = [Output(display_name="Out", name="out", method="build_output")]

    def build_output(self) -> Message:
        return Message(text=self.label or "")


def _tool_for(component: Component) -> StructuredTool:
    tools = ComponentToolkit(component=component).get_tools()
    assert len(tools) == 1
    return tools[0]


# --- The reported bug --------------------------------------------------


def test_same_type_instances_produce_colliding_names_at_the_toolkit_level():
    """The toolkit's per-component name is type-derived, and stays that way.

    This is the collision's origin and is deliberately preserved: the name is
    the saved flow's ``tools_metadata`` key. Resolution happens one layer up.
    """
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))

    assert alpha.name == beta.name == "send_to_agent"


def test_duplicate_names_are_resolved_when_the_agent_aggregates_the_tools():
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))

    alpha, beta = disambiguate_tool_names([alpha, beta])

    assert alpha.name != beta.name
    assert len({alpha.name, beta.name}) == 2


def test_resolved_name_identifies_the_component_instance_it_runs():
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))

    alpha, beta = disambiguate_tool_names([alpha, beta])

    assert alpha.name == "send_to_agent_RemoteAgentCall_alpha"
    assert beta.name == "send_to_agent_RemoteAgentCall_beta"


def test_resolved_name_also_lands_on_the_tags_the_agent_reads():
    """``tags[0]`` is the tool's identity for metadata and HITL gating."""
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))

    alpha, beta = disambiguate_tool_names([alpha, beta])

    assert alpha.tags == [alpha.name]
    assert beta.tags == [beta.name]


def test_three_instances_of_one_type_all_get_distinct_names():
    tools = [_tool_for(RemoteAgentCall(_id=f"RemoteAgentCall-{n}", target=n)) for n in ("a", "b", "c")]

    tools = disambiguate_tool_names(tools)

    assert len({tool.name for tool in tools}) == 3


def test_class_name_derived_duplicates_are_resolved_too():
    tools = [_tool_for(SingleGenericOutput(_id=f"SingleGenericOutput-{n}", label=n)) for n in ("a", "b")]

    assert all(tool.name.startswith("single_generic_output") for tool in tools)

    tools = disambiguate_tool_names(tools)

    assert len({tool.name for tool in tools}) == 2


def test_each_resolved_tool_still_runs_its_own_instance():
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))

    alpha, beta = disambiguate_tool_names([alpha, beta])

    by_name = {alpha.name: alpha, beta.name: beta}

    assert by_name["send_to_agent_RemoteAgentCall_alpha"].invoke({"input_value": "ping"}) == "alpha answered: ping"
    assert by_name["send_to_agent_RemoteAgentCall_beta"].invoke({"input_value": "ping"}) == "beta answered: ping"


# --- What must NOT change ---------------------------------------------


def test_uncontested_names_are_left_exactly_as_they_were():
    """A saved flow's ``tools_metadata`` rows match on the tool name.

    Renaming a tool that collides with nothing would stop those rows from
    matching, which drops the user's Actions-panel edits -- and the tool
    itself, since ``update_tools_metadata`` only keeps tools it finds in the
    metadata. So only genuine duplicates may be touched.
    """
    remote = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    generic = _tool_for(SingleGenericOutput(_id="SingleGenericOutput-x", label="x"))

    disambiguate_tool_names([remote, generic])

    assert remote.name == "send_to_agent"
    assert remote.tags == ["send_to_agent"]
    assert generic.name == "single_generic_output"


def test_a_single_tool_is_never_renamed():
    tool = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))

    disambiguate_tool_names([tool])

    assert tool.name == "send_to_agent"


def test_saved_actions_metadata_still_matches_after_resolution():
    """End-to-end on the regression that matters: the Actions row survives.

    The metadata is applied per node, before the agent aggregates, so a saved
    row keyed on ``send_to_agent`` must still match the tool the toolkit
    builds for that node.
    """
    import pandas as pd

    component = RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha")
    saved_rows = pd.DataFrame(
        [
            {
                "name": "ask_alpha",
                "description": "Ask the alpha agent.",
                "display_description": "Send a message to a remote agent and return its reply.",
                "tags": ["send_to_agent"],
                "status": True,
            }
        ]
    )

    toolkit = ComponentToolkit(component=component, metadata=saved_rows)
    tools = toolkit.update_tools_metadata(tools=toolkit.get_tools())

    assert [tool.name for tool in tools] == ["ask_alpha"]
    assert tools[0].description == "Ask the alpha agent."


def test_user_renamed_duplicates_are_not_touched():
    """If the Actions panel already made the names unique, leave them alone."""
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))
    alpha.name = "ask_alpha"
    alpha.tags = ["ask_alpha"]
    beta.name = "ask_beta"
    beta.tags = ["ask_beta"]

    alpha, beta = disambiguate_tool_names([alpha, beta])

    assert alpha.name == "ask_alpha"
    assert beta.name == "ask_beta"


# --- Provider constraints ---------------------------------------------


@pytest.mark.parametrize("name_length", [40, 64, 90])
def test_resolved_name_stays_within_the_provider_name_limit(name_length: int):
    """OpenAI and Anthropic reject tool names longer than 64 characters."""
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))
    long_name = "a" * name_length
    alpha.name = beta.name = long_name

    alpha, beta = disambiguate_tool_names([alpha, beta])

    assert alpha.name != beta.name
    for tool in (alpha, beta):
        assert len(tool.name) <= 64
        assert tool.name.replace("-", "_").replace("_", "").isalnum()


def test_resolved_names_only_use_characters_providers_accept():
    tools = [_tool_for(RemoteAgentCall(_id=f"Remote Agent Call #{n}!", target=n)) for n in ("a", "b")]

    tools = disambiguate_tool_names(tools)

    pattern_safe = all(all(char.isalnum() or char in "_-" for char in tool.name) for tool in tools)
    assert pattern_safe
    assert len({tool.name for tool in tools}) == 2


def test_a_non_tool_item_on_the_list_is_ignored():
    """A Tool list input can still carry a template default next to the tools."""
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))

    alpha, _, beta = disambiguate_tool_names([alpha, Message(text="not a tool"), beta])

    assert alpha.name != beta.name


def test_tools_without_a_source_component_still_end_up_distinct():
    """Tools built outside the toolkit carry no component id to fall back on."""
    plain = [
        StructuredTool.from_function(func=lambda: "a", name="shared", description="a"),
        StructuredTool.from_function(func=lambda: "b", name="shared", description="b"),
    ]

    plain = disambiguate_tool_names(plain)

    assert len({tool.name for tool in plain}) == 2


# --- Through the graph, where saved flows are fixed -------------------


class ToolNameCollector(Component):
    """Stands in for an agent: a Tool list input, reported back as text."""

    display_name = "Tool Name Collector"
    description = "Reports the names of the tools wired into it."
    name = "ToolNameCollector"

    inputs = [
        HandleInput(name="tools", display_name="Tools", input_types=["Tool"], is_list=True, required=False),
    ]

    outputs = [Output(display_name="Names", name="names", method="collect_names")]

    def collect_names(self) -> Message:
        return Message(text=",".join(tool.name for tool in self.tools or []))


def _collected_names(results) -> str:
    built = next(
        result.vertex.built_object
        for result in results
        if getattr(result, "vertex", None) is not None and result.vertex.id == "ToolNameCollector-1"
    )
    message = built["names"] if isinstance(built, dict) else built
    return message.get_text()


async def test_graph_resolves_duplicate_tool_names_before_the_consumer_runs():
    """The engine seam is what reaches flows already saved.

    A saved flow carries its own frozen copy of the consuming component's
    code, so resolving the collision inside the Agent would never reach the
    flows reporting this. The graph assembles the Tool list input itself, and
    that code is never frozen.
    """
    alpha = RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha")
    beta = RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta")
    collector = ToolNameCollector(_id="ToolNameCollector-1")
    collector.set(tools=[alpha, beta])

    graph = Graph(start=alpha, end=collector)
    results = [result async for result in graph.async_start()]

    names = _collected_names(results).split(",")

    assert len(names) == 2
    assert sorted(names) == ["send_to_agent_RemoteAgentCall_alpha", "send_to_agent_RemoteAgentCall_beta"]


async def test_graph_leaves_a_lone_tool_name_untouched():
    alpha = RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha")
    collector = ToolNameCollector(_id="ToolNameCollector-1")
    collector.set(tools=[alpha])

    graph = Graph(start=alpha, end=collector)
    results = [result async for result in graph.async_start()]

    assert _collected_names(results) == "send_to_agent"


def test_resolution_does_not_mutate_tools_shared_with_another_consumer():
    alpha = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))
    beta = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-beta", target="beta"))

    resolved = disambiguate_tool_names([alpha, beta])

    assert len({tool.name for tool in resolved}) == 2
    assert alpha.name == beta.name == "send_to_agent"
    assert alpha.tags == beta.tags == ["send_to_agent"]
    assert disambiguate_tool_names([alpha])[0].name == "send_to_agent"


def test_collision_checks_use_the_final_provider_safe_name():
    tools = [
        StructuredTool.from_function(func=lambda: "a", name="f x", description="a"),
        StructuredTool.from_function(func=lambda: "b", name="f x", description="b"),
        StructuredTool.from_function(func=lambda: "c", name="f-x_1", description="c"),
    ]

    resolved = disambiguate_tool_names(tools)

    assert len({tool.name for tool in resolved}) == 3
    assert resolved[2].name == "f-x_1"


def test_the_same_tool_connected_twice_gets_distinct_consumer_copies():
    tool = _tool_for(RemoteAgentCall(_id="RemoteAgentCall-alpha", target="alpha"))

    resolved = disambiguate_tool_names([tool, tool])

    assert resolved[0].name != resolved[1].name
    assert tool.name == "send_to_agent"


def test_renaming_preserves_additional_tracing_tags():
    tools = [
        StructuredTool.from_function(func=lambda: "a", name="shared", description="a", tags=["shared", "tracing"]),
        StructuredTool.from_function(func=lambda: "b", name="shared", description="b", tags=["shared", "tracing"]),
    ]

    resolved = disambiguate_tool_names(tools)

    assert all(tool.tags == [tool.name, "tracing"] for tool in resolved)
