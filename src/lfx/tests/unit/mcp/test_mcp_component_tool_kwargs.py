from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
from pydantic import BaseModel, Field


class TabsArgs(BaseModel):
    action: str = Field(..., description="Operation to perform")
    index: float | None = Field(None, description="Tab index")


def test_tool_argument_named_after_a_component_method_gets_its_configured_value():
    # `index` is also CustomComponent.index; getattr returned the bound method (#15519).
    component = MCPToolsComponent()
    component._attributes["action"] = "select"
    component._attributes["index"] = 2

    assert component._build_tool_kwargs(TabsArgs) == {"action": "select", "index": 2}


def test_unset_optional_tool_argument_named_after_a_method_is_omitted():
    component = MCPToolsComponent()
    component._attributes["action"] = "list"

    assert component._build_tool_kwargs(TabsArgs) == {"action": "list"}
