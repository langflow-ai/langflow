from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
from lfx.io import StrInput
from lfx.schema.message import Message
from pydantic import BaseModel, Field


class TabsArgs(BaseModel):
    action: str = Field(..., description="Operation to perform")
    index: float | None = Field(None, description="Tab index")


class MetadataCollisionArgs(BaseModel):
    name: str | None = None
    description: str | None = None
    resolve_path: str | None = None


def test_tool_argument_named_after_a_component_method_gets_its_configured_value():
    component = MCPToolsComponent()
    component._attributes["action"] = "select"
    component._attributes["index"] = 2

    assert component._build_tool_kwargs(TabsArgs) == {
        "action": "select",
        "index": 2,
    }


def test_unset_optional_tool_argument_named_after_a_method_is_omitted():
    component = MCPToolsComponent()
    component._attributes["action"] = "list"

    assert component._build_tool_kwargs(TabsArgs) == {
        "action": "list",
    }


def test_tool_argument_named_index_zero_is_preserved():
    component = MCPToolsComponent()
    component._attributes["action"] = "select"
    component._attributes["index"] = 0

    assert component._build_tool_kwargs(TabsArgs) == {
        "action": "select",
        "index": 0,
    }


def test_tool_argument_colliding_with_class_attributes_omitted_when_unset():
    component = MCPToolsComponent()

    assert component._build_tool_kwargs(MetadataCollisionArgs) == {}


def test_tool_argument_colliding_with_class_attributes_receives_configured_value():
    component = MCPToolsComponent()
    component._attributes["name"] = "custom_tool"
    component._attributes["description"] = "custom description"
    component._attributes["resolve_path"] = "/tmp/custom"

    assert component._build_tool_kwargs(MetadataCollisionArgs) == {
        "name": "custom_tool",
        "description": "custom description",
        "resolve_path": "/tmp/custom",
    }


def test_tool_argument_message_unwrapping():
    component = MCPToolsComponent()
    component._attributes["action"] = Message(text="close")

    assert component._build_tool_kwargs(TabsArgs) == {"action": "close"}


def test_tool_argument_resolved_from_inputs():
    component = MCPToolsComponent()
    component._inputs["action"] = StrInput(name="action", value="reload")

    assert component._build_tool_kwargs(TabsArgs) == {"action": "reload"}
