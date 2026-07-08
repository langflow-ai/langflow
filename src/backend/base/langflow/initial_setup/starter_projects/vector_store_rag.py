from textwrap import dedent

from lfx.components.data import FileComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.components.models_and_agents import PromptComponent
from lfx.components.processing import ParserComponent
from lfx.components.processing.split_text import SplitTextComponent
from lfx.graph import Graph


def ingestion_graph():
    # Ingestion Graph
    file_component = FileComponent()
    text_splitter = SplitTextComponent()
    text_splitter.set(data_inputs=file_component.load_files_message)

    return Graph(file_component, text_splitter)


def rag_graph():
    # RAG Graph
    chat_input = ChatInput()
    file_component = FileComponent()
    text_splitter = SplitTextComponent()
    text_splitter.set(data_inputs=file_component.load_files_message)

    parse_data = ParserComponent()
    parse_data.set(input_data=text_splitter.split_text, mode="Stringify")
    prompt_component = PromptComponent()
    prompt_component.set(
        template=dedent("""Given the following context, answer the question.
                         Context:{context}

                         Question: {question}
                         Answer:"""),
        context=parse_data.parse_combined_text,
        question=chat_input.message_response,
    )

    language_model_component = LanguageModelComponent()
    language_model_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput()
    chat_output.set(input_value=language_model_component.text_response)

    return Graph(start=chat_input, end=chat_output)


def vector_store_rag_graph():
    return ingestion_graph() + rag_graph()
