import os

import pytest
from langflow.components.agents.simple_agent import SimpleAgentComponent
from langflow.components.tools.calculator import CalculatorToolComponent


@pytest.mark.api_key_required
@pytest.mark.asyncio
async def test_simple_agent_with_calculator():
    # Mock inputs
    tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
    input_value = "What is 2 + 2?"

    api_key = os.environ["OPENAI_API_KEY"]
    temperature = 0.1

    # Initialize the SimpleAgentComponent with mocked inputs
    agent = SimpleAgentComponent(
        tools=tools,
        input_value=input_value,
        api_key=api_key,
        temperature=temperature
    )

    response = await agent.get_response()
    assert "4" in response.data.get("text")

