"""Tests for ComponentToolkit handling of components with multiple outputs.

Bug: When a component has 2+ outputs (each with tool_mode=True) and
tool_name/tool_description are provided, ComponentToolkit.get_tools() raises
ValueError instead of disambiguating tool names.

GIVEN: A component with 2 outputs, both with tool_mode=True (default)
WHEN:  get_tools() is called with tool_name and tool_description
THEN:  ValueError: "When passing a tool name or description, there must be
       only one tool, but 2 tools were found."
EXPECTED: Tools are created with prefixed names to disambiguate them.
"""

from lfx.base.tools.component_tool import ComponentToolkit
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class MultiOutputComponent(Component):
    """Minimal component with two outputs to reproduce the bug."""

    display_name = "Multi Output Component"
    description = "A component with two separate outputs."
    name = "MultiOutputComponent"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Progress",
            name="progress_output",
            method="get_progress",
        ),
        Output(
            display_name="Result",
            name="result_output",
            method="get_result",
        ),
    ]

    async def get_progress(self) -> Message:
        return await Message.create(text="progress")

    async def get_result(self) -> Message:
        return await Message.create(text="result")


def test_should_create_tools_with_prefixed_names_when_component_has_multiple_outputs():
    """Bug fix: get_tools() must handle multiple outputs with tool_name/description.

    Instead of raising ValueError, it should prefix each tool's name
    with the provided tool_name to disambiguate them.
    """
    # Arrange
    component = MultiOutputComponent()
    toolkit = ComponentToolkit(component=component)
    tool_name = "my_agent"
    tool_description = "An agent with split outputs"

    # Act
    tools = toolkit.get_tools(
        tool_name=tool_name,
        tool_description=tool_description,
    )

    # Assert — must create 2 tools with prefixed names, not raise ValueError
    assert len(tools) == 2
    tool_names = {tool.name for tool in tools}
    assert "my_agent_get_progress" in tool_names
    assert "my_agent_get_result" in tool_names
    for tool in tools:
        assert tool_description in tool.description
        assert tool.tags == [tool.name]
