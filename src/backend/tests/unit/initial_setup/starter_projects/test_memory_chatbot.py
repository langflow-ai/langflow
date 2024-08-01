from collections import deque

from langflow.components.helpers.Memory import MemoryComponent
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.prompts.Prompt import PromptComponent
from langflow.graph import Graph
from langflow.graph.graph.constants import Finish


def test_memory_chatbot():
    session_id = "test_session_id"
    template = """{context}

User: {user_message}
AI: """
    memory_component = MemoryComponent(_id="chat_memory")
    memory_component.set(session_id=session_id)
    chat_input = ChatInput(_id="chat_input")
    prompt_component = PromptComponent(_id="prompt")
    prompt_component.set(
        template=template, user_message=chat_input.message_response, context=memory_component.retrieve_messages_as_text
    )
    openai_component = OpenAIModelComponent(_id="openai")
    openai_component.set(
        input_value=prompt_component.build_prompt, max_tokens=100, temperature=0.1, api_key="test_api_key"
    )
    openai_component.get_output("text_output").value = "Mock response"

    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=openai_component.text_response)

    graph = Graph(chat_input, chat_output)
    # Now we run step by step
    expected_order = deque(["chat_input", "chat_memory", "prompt", "openai", "chat_output"])
    for step in expected_order:
        result = graph.step()
        if isinstance(result, Finish):
            break
        assert step == result.vertex.id
