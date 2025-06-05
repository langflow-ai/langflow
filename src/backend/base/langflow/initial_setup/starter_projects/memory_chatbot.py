from langflow.components.helpers.memory import MemoryComponent
<<<<<<< HEAD
from langflow.components.inputs.chat import ChatInput
from langflow.components.models.openai_chat_model import OpenAIModelComponent
from langflow.components.outputs.chat import ChatOutput
from langflow.components.prompts.prompt import PromptComponent
from langflow.graph.graph.base import Graph
=======
from langflow.components.input_output import ChatInput, ChatOutput
from langflow.components.languagemodels import OpenAIModelComponent
from langflow.components.prompts import PromptComponent
from langflow.graph import Graph
>>>>>>> main


def memory_chatbot_graph(template: str | None = None):
    if template is None:
        template = """{context}

    User: {user_message}
    AI: """
    memory_component = MemoryComponent()
    chat_input = ChatInput()
    prompt_component = PromptComponent()
    prompt_component.set(
        template=template, user_message=chat_input.message_response, context=memory_component.retrieve_messages_as_text
    )
    openai_component = OpenAIModelComponent()
    openai_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput()
    chat_output.set(input_value=openai_component.text_response)

    return Graph(chat_input, chat_output)
