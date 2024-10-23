import os

import pytest
from langchain.agents import AgentExecutor
from langchain_core.runnables import Runnable
from langflow.components.agents.tool_calling import ToolCallingAgentComponent
from langflow.components.data import URLComponent
from langflow.components.models import OpenAIModelComponent


@pytest.mark.api_key_required
@pytest.fixture
def tool_calling_agent():
    # Initialize the ToolCallingAgentComponent with OpenAI LLM and URL tool
    api_key = os.getenv("OPENAI_API_KEY")
    llm = OpenAIModelComponent(api_key=api_key).build_model()  # Initialize OpenAI LLM
    tools = URLComponent().to_toolkit()  # Initialize URL tool
    return ToolCallingAgentComponent(llm=llm, tools=tools)


def test_create_agent_runnable(tool_calling_agent):
    tool_calling_agent.user_prompt = "{input}"
    tool_calling_agent.system_prompt = "You are a helpful assistant."
    # Test with a sample input
    input_text = "What are the contents of https://example.com?"
    tool_calling_agent.input_value = input_text  # Assuming chat_history is at index 2

    # Call the method and check if it runs without errors
    try:
        agent_runnable = tool_calling_agent.create_agent_runnable()
        assert isinstance(agent_runnable, Runnable)  # Ensure the agent runnable is an instance of Runnable
    except ValueError as e:
        pytest.fail(f"ValueError raised: {e}")
    except NotImplementedError as e:
        pytest.fail(f"NotImplementedError raised: {e}")


# test for running an agent to get message response
def test_run_agent(tool_calling_agent):
    tool_calling_agent.user_prompt = "{input}"
    tool_calling_agent.system_prompt = "You are a helpful assistant."
    input_text = "What are the contents of https://example.com?"
    tool_calling_agent.input_value = input_text
    agent_runnable = tool_calling_agent.create_agent_runnable()
    # response = tool_calling_agent.message_response()
    agent_executor = AgentExecutor(agent=agent_runnable, tools=tool_calling_agent.tools)
    response_invoke = agent_executor.invoke({"input": input_text})
    assert isinstance(response_invoke, dict)
    assert "output" in response_invoke
    assert "input" in response_invoke
