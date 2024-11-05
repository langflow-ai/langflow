import os

import pytest
from langflow.components.agents.agent import AgentComponent
from langflow.components.tools.calculator import CalculatorToolComponent


@pytest.mark.api_key_required
async def test_agent_component_with_calculator():
    # Mock inputs
    tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
    input_value = "What is 2 + 2?"

    api_key = os.environ["OPENAI_API_KEY"]
    temperature = 0.1

    # Initialize the AgentComponent with mocked inputs
    agent = AgentComponent(
        tools=tools,
        input_value=input_value,
        api_key=api_key,
        model_name="gpt-4o",
        llm_type="OpenAI",
        temperature=temperature,
    )

    response = await agent.get_response()
    assert "4" in response.data.get("text")




async def test_agent_as_tool():
    tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
    input_value = "What is 2 + 2?"

    api_key = os.environ["OPENAI_API_KEY"]
    temperature = 0.1

    # Initialize the AgentComponent with mocked inputs
    agent_one = AgentComponent(
        tools=tools,
        api_key=api_key,
        model_name="gpt-4o",
        llm_type="OpenAI",
        temperature=temperature,
    )
    agent_tool = agent_one.to_toolkit()

    agent_two = AgentComponent(
        tools=agent_tool,
        input_value=input_value,
        api_key=api_key,
        model_name="gpt-4o",
        llm_type="OpenAI",
        temperature=temperature,
    )
    response = await agent_two.get_response()
    assert "4" in response.data.get("text")

