import os

import pytest
from langflow.components.langchain_utilities import ToolCallingAgentComponent
from langflow.components.languagemodels.openai_chat_model import OpenAIModelComponent
from langflow.components.tools.calculator import CalculatorToolComponent


@pytest.mark.api_key_required
@pytest.mark.usefixtures("client")
async def test_tool_calling_agent_component():
    tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
    input_value = "What is 2 + 2?"
    chat_history = []
    api_key = os.environ["OPENAI_API_KEY"]
    temperature = 0.1

    # Default OpenAI Model Component
    llm_component = OpenAIModelComponent().set(
        api_key=api_key,
        temperature=temperature,
    )
    llm = llm_component.build_model()

    agent = ToolCallingAgentComponent(_session_id="test")
    agent.set(llm=llm, tools=[tools], chat_history=chat_history, input_value=input_value)

    # Chat output
    response = await agent.message_response()
    assert "4" in response.data.get("text")
