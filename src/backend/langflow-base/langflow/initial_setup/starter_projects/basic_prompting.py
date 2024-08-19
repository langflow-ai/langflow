from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.prompts.Prompt import PromptComponent
from langflow.graph.graph.base import Graph


def basic_prompting_graph(template: str | None = None):
    if template is None:
        template = """Answer the user as if you were a pirate.

User: {user_input}

Answer:
"""
    chat_input = ChatInput()
    prompt_component = PromptComponent()
    prompt_component.set(
        template=template,
        user_input=chat_input.message_response,
    )

    openai_component = OpenAIModelComponent()
    openai_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput()
    chat_output.set(input_value=openai_component.text_response)

    graph = Graph(start=chat_input, end=chat_output)
    return graph
