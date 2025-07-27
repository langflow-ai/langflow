from collections.abc import Callable

from lfx.base.agents.agent import DEFAULT_TOOLS_DESCRIPTION
from lfx.components.agents.agent import AgentComponent
from lfx.components.tools.calculator import CalculatorToolComponent


async def test_component_to_toolkit():
    calculator_component = CalculatorToolComponent()
    agent_component = AgentComponent().set(tools=[calculator_component])

    tools = await agent_component.to_toolkit()
    assert len(tools) == 1
    tool = tools[0]

    assert tool.name == "Call_Agent"

    assert tool.description == DEFAULT_TOOLS_DESCRIPTION, tool.description

    assert isinstance(tool.coroutine, Callable)
    assert tool.args_schema is not None
