from collections.abc import Callable

from langflow.base.agents.agent import DEFAULT_TOOLS_DESCRIPTION
from langflow.components.agents.agent import AgentComponent
from langflow.components.custom_component.custom_component import CustomComponent
from langflow.components.inputs import ChatInput
from langflow.components.tools.calculator import CalculatorToolComponent


def test_component_to_toolkit():
    calculator_component = CalculatorToolComponent()
    agent_component = AgentComponent().set(tools=[calculator_component])

    tools = agent_component.to_toolkit()
    assert len(tools) == 1
    tool = tools[0]

    assert tool.name == "Agent"

    assert tool.description == DEFAULT_TOOLS_DESCRIPTION, tool.description

    assert isinstance(tool.coroutine, Callable)
    assert tool.args_schema is not None


def test_component_to_tool_has_no_component_as_tool():
    chat_input = ChatInput()
    tools = chat_input.to_toolkit()
    assert len(tools) == 1


def test_custom_component_to_tool():
    custom_component = CustomComponent()
    tools = custom_component.to_toolkit()
    assert len(tools) == 1
