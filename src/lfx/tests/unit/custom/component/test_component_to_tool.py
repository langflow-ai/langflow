from collections.abc import Callable

import pytest


@pytest.mark.skip("Temporarily disabled")
async def test_component_to_toolkit():
    from lfx.components.agents.agent import AgentComponent
    from lfx.components.tools.calculator import CalculatorToolComponent

    calculator_component = CalculatorToolComponent()
    agent_component = AgentComponent().set(tools=[calculator_component])

    tools = await agent_component.to_toolkit()
    assert len(tools) == 1
    tool = tools[0]

    assert tool.name == "Call_Agent"

    # After removing the deprecated agent_description override (issue #9155),
    # an agent-as-tool behaves like any other tool: its description must match
    # the output-derived display_description so the Actions-panel merge logic
    # can detect genuine user customizations.
    assert tool.description
    assert tool.description == tool.metadata["display_description"], tool.description

    assert isinstance(tool.coroutine, Callable)
    assert tool.args_schema is not None
