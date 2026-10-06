"""MCP arguments use configured values even when their names collide with Component members."""

import pytest
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
from lfx.io import IntInput
from lfx.schema.message import Message
from pydantic import BaseModel, create_model


class TabsArgs(BaseModel):
    action: str
    index: float | None = None


@pytest.mark.parametrize("index", [0, 2])
@pytest.mark.parametrize("storage", ["attributes", "inputs"])
def test_method_named_tool_argument_receives_configured_value(index, storage):
    component = MCPToolsComponent()
    component.set_attributes({"action": "select"})
    if storage == "attributes":
        component.set_attributes({"index": index})
    else:
        component._inputs["index"] = IntInput(name="index", value=index)

    kwargs = component._build_tool_kwargs(TabsArgs)

    assert kwargs == {"action": "select", "index": index}
    assert TabsArgs(**kwargs).index == index
    assert callable(component.index)


@pytest.mark.parametrize("arg_name", ["index", "run", "log", "build_output", "name", "description", "code"])
def test_unset_tool_argument_does_not_receive_component_member(arg_name):
    args_schema = create_model("ToolArgs", **{arg_name: (str | None, None)})
    component = MCPToolsComponent()

    assert component._build_tool_kwargs(args_schema) == {}


def test_class_attribute_named_tool_argument_receives_configured_value():
    args_schema = create_model("ToolArgs", description=(str | None, None))
    component = MCPToolsComponent()
    component.set_attributes({"description": "tool argument"})

    assert component._build_tool_kwargs(args_schema) == {"description": "tool argument"}


@pytest.mark.parametrize("value", [None, ""])
def test_explicitly_empty_argument_takes_precedence_over_input_value(value):
    component = MCPToolsComponent()
    component._inputs["index"] = IntInput(name="index", value=2)
    component.set_attributes({"action": "list"})
    component._attributes["index"] = value

    assert component._build_tool_kwargs(TabsArgs) == {"action": "list"}


def test_message_tool_argument_is_unwrapped():
    component = MCPToolsComponent()
    component.set_attributes({"action": Message(text="list")})

    assert component._build_tool_kwargs(TabsArgs) == {"action": "list"}


def test_tool_arguments_preserve_empty_required_and_false_values_and_server_defaults():
    class ToolArgs(BaseModel):
        required_text: str
        optional_text: str = "server default"
        options: dict | None = None
        enabled: bool = True
        items: list[str] | None = None

    component = MCPToolsComponent()
    component.set_attributes({"required_text": "", "optional_text": "", "options": {}, "enabled": False, "items": []})

    kwargs = component._build_tool_kwargs(ToolArgs)

    assert kwargs == {"required_text": "", "enabled": False, "items": []}
    assert ToolArgs(**kwargs).optional_text == "server default"
