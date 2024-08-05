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
from langflow.graph.graph.constants import Finish
from langflow.schema.data import Data


def test_vector_store_rag():
    # Ingestion Graph
    file_component = FileComponent(_id="file-123")
    file_component.set(path="test.txt")
    text_splitter = SplitTextComponent(_id="text-splitter-123")
    text_splitter.set(data_inputs=file_component.load_file)
    openai_embeddings = OpenAIEmbeddingsComponent(_id="openai-embeddings-123")
    openai_embeddings.set(
        openai_api_key="sk-123", openai_api_base="https://api.openai.com/v1", openai_api_type="openai"
    )
    vector_store = AstraVectorStoreComponent(_id="vector-store-123")
    vector_store.set(
        embedding=openai_embeddings.build_embeddings,
        ingest_data=text_splitter.split_text,
        api_endpoint="https://astra.example.com",
        token="token",
    )

    # RAG Graph
    chat_input = ChatInput(_id="chatinput-123")
    chat_input.get_output("message").value = "What is the meaning of life?"
    rag_vector_store = AstraVectorStoreComponent(_id="rag-vector-store-123")
    rag_vector_store.set(
        search_input=chat_input.message_response,
        api_endpoint="https://astra.example.com",
        token="token",
        embedding=openai_embeddings.build_embeddings,
    )
    # Mock search_documents
    rag_vector_store.get_output("search_results").value = [
        Data(data={"text": "Hello, world!"}),
        Data(data={"text": "Goodbye, world!"}),
    ]
    parse_data = ParseDataComponent(_id="parse-data-123")
    parse_data.set(data=rag_vector_store.search_documents)
    prompt_component = PromptComponent(_id="prompt-123")
    prompt_component.set(
        template=dedent("""Given the following context, answer the question.
                         Context:{context}

                         Question: {question}
                         Answer:"""),
        context=parse_data.parse_data,
        question=chat_input.message_response,
    )

    openai_component = OpenAIModelComponent(_id="openai-123")
    openai_component.set(api_key="sk-123", openai_api_base="https://api.openai.com/v1")
    openai_component.set_output_value("text_output", "Hello, world!")
    openai_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput(_id="chatoutput-123")
    chat_output.set(input_value=openai_component.text_response)

    graph = Graph(start=chat_input, end=chat_output)
    assert graph is not None
    ids = [
        "chatinput-123",
        "chatoutput-123",
        "openai-123",
        "parse-data-123",
        "prompt-123",
        "rag-vector-store-123",
        "openai-embeddings-123",
    ]
    results = []
    for result in graph.start():
        results.append(result)

    assert len(results) == 8
    vids = [result.vertex.id for result in results if hasattr(result, "vertex")]
    assert all(vid in ids for vid in vids), f"Diff: {set(vids) - set(ids)}"
    assert results[-1] == Finish()
