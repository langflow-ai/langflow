import pytest
from lfx.components.langchain_utilities import ToolCallingAgentComponent
from lfx.components.openai.openai_chat_model import OpenAIModelComponent
from lfx.components.tools.calculator import CalculatorToolComponent


@pytest.mark.api_key_required
@pytest.mark.usefixtures("client")
async def test_tool_calling_agent_component():
    tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
    input_value = "What is 2 + 2?"
    chat_history = []
    from tests.api_keys import get_openai_api_key

    api_key = get_openai_api_key()
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
