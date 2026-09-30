from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.components.models_and_agents import PromptComponent
from lfx.graph import Graph


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

    language_model_component = LanguageModelComponent()
    language_model_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput()
    chat_output.set(input_value=language_model_component.text_response)

    return Graph(start=chat_input, end=chat_output)
