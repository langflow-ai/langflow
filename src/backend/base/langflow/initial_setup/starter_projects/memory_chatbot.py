from lfx.components.helpers import MemoryComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.components.models_and_agents import PromptComponent
from lfx.components.processing.converter import TypeConverterComponent
from lfx.graph import Graph


def memory_chatbot_graph(template: str | None = None):
    if template is None:
        template = """{context}

    User: {user_message}
    AI: """
    memory_component = MemoryComponent()
    chat_input = ChatInput()
    type_converter = TypeConverterComponent()
    type_converter.set(input_data=memory_component.retrieve_messages_dataframe)
    prompt_component = PromptComponent()
    prompt_component.set(
        template=template,
        user_message=chat_input.message_response,
        context=type_converter.convert_to_message,
    )
    language_model_component = LanguageModelComponent()
    language_model_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput()
    chat_output.set(input_value=language_model_component.text_response)

    return Graph(chat_input, chat_output)
