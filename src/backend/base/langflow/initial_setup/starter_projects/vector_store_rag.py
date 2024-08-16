from textwrap import dedent

from langflow.components.data.File import FileComponent
from langflow.components.embeddings.OpenAIEmbeddings import OpenAIEmbeddingsComponent
from langflow.components.helpers.ParseData import ParseDataComponent
from langflow.components.helpers.SplitText import SplitTextComponent
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.prompts.Prompt import PromptComponent
from langflow.components.vectorstores.AstraDB import AstraVectorStoreComponent
from langflow.graph.graph.base import Graph


def ingestion_graph():
    # Ingestion Graph
    file_component = FileComponent()
    text_splitter = SplitTextComponent()
    text_splitter.set(data_inputs=file_component.load_file)
    openai_embeddings = OpenAIEmbeddingsComponent()
    vector_store = AstraVectorStoreComponent()
    vector_store.set(
        embedding=openai_embeddings.build_embeddings,
        ingest_data=text_splitter.split_text,
    )

    ingestion_graph = Graph(file_component, vector_store)
    return ingestion_graph


def rag_graph():
    # RAG Graph
    openai_embeddings = OpenAIEmbeddingsComponent()
    chat_input = ChatInput()
    rag_vector_store = AstraVectorStoreComponent()
    rag_vector_store.set(
        search_input=chat_input.message_response,
        embedding=openai_embeddings.build_embeddings,
    )

    parse_data = ParseDataComponent()
    parse_data.set(data=rag_vector_store.search_documents)
    prompt_component = PromptComponent()
    prompt_component.set(
        template=dedent("""Given the following context, answer the question.
                         Context:{context}

                         Question: {question}
                         Answer:"""),
        context=parse_data.parse_data,
        question=chat_input.message_response,
    )

    openai_component = OpenAIModelComponent()
    openai_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput()
    chat_output.set(input_value=openai_component.text_response)

    graph = Graph(start=chat_input, end=chat_output)
    return graph


def vector_store_rag_graph():
    return ingestion_graph() + rag_graph()
