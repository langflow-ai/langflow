import copy
import operator
from textwrap import dedent

import pytest
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


@pytest.fixture
def ingestion_graph():
    # Ingestion Graph
    file_component = FileComponent(_id="file-123")
    file_component.set(path="test.txt")
    file_component.set_on_output(name="data", value=Data(text="This is a test file."), cache=True)
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
    vector_store.set_on_output(name="vector_store", value="mock_vector_store", cache=True)
    vector_store.set_on_output(name="base_retriever", value="mock_retriever", cache=True)
    vector_store.set_on_output(name="search_results", value=[Data(text="This is a test file.")], cache=True)

    return Graph(file_component, vector_store)


@pytest.fixture
def rag_graph():
    # RAG Graph
    openai_embeddings = OpenAIEmbeddingsComponent(_id="openai-embeddings-124")
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
    rag_vector_store.set_on_output(
        name="search_results",
        value=[
            Data(data={"text": "Hello, world!"}),
            Data(data={"text": "Goodbye, world!"}),
        ],
        cache=True,
    )
    rag_vector_store.set_on_output(name="vector_store", value="mock_vector_store", cache=True)
    rag_vector_store.set_on_output(name="base_retriever", value="mock_retriever", cache=True)
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
    openai_component.set_on_output(name="text_output", value="Hello, world!", cache=True)
    openai_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput(_id="chatoutput-123")
    chat_output.set(input_value=openai_component.text_response)

    return Graph(start=chat_input, end=chat_output)


def test_vector_store_rag(ingestion_graph, rag_graph):
    assert ingestion_graph is not None
    ingestion_ids = [
        "file-123",
        "text-splitter-123",
        "openai-embeddings-123",
        "vector-store-123",
    ]
    assert rag_graph is not None
    rag_ids = [
        "chatinput-123",
        "chatoutput-123",
        "openai-123",
        "parse-data-123",
        "prompt-123",
        "rag-vector-store-123",
        "openai-embeddings-124",
    ]
    for ids, graph, len_results in [(ingestion_ids, ingestion_graph, 5), (rag_ids, rag_graph, 8)]:
        results = []
        for result in graph.start():
            results.append(result)

        assert len(results) == len_results
        vids = [result.vertex.id for result in results if hasattr(result, "vertex")]
        assert all(vid in ids for vid in vids), f"Diff: {set(vids) - set(ids)}"
        assert results[-1] == Finish()


def test_vector_store_rag_dump_components_and_edges(ingestion_graph, rag_graph):
    # Test ingestion graph components and edges
    ingestion_graph_dump = ingestion_graph.dump(
        name="Ingestion Graph", description="Graph for data ingestion", endpoint_name="ingestion"
    )

    ingestion_data = ingestion_graph_dump["data"]
    ingestion_nodes = ingestion_data["nodes"]
    assert len(ingestion_nodes) == 4
    ingestion_edges = ingestion_data["edges"]

    # Sort nodes by id to check components
    ingestion_nodes = sorted(ingestion_nodes, key=operator.itemgetter("id"))

    # Check components in the ingestion graph
    assert ingestion_nodes[0]["data"]["type"] == "File"
    assert ingestion_nodes[0]["id"] == "file-123"

    assert ingestion_nodes[1]["data"]["type"] == "OpenAIEmbeddings"
    assert ingestion_nodes[1]["id"] == "openai-embeddings-123"

    assert ingestion_nodes[2]["data"]["type"] == "SplitText"
    assert ingestion_nodes[2]["id"] == "text-splitter-123"

    assert ingestion_nodes[3]["data"]["type"] == "AstraDB"
    assert ingestion_nodes[3]["id"] == "vector-store-123"

    # Check edges in the ingestion graph
    expected_ingestion_edges = [
        ("file-123", "text-splitter-123"),
        ("text-splitter-123", "vector-store-123"),
        ("openai-embeddings-123", "vector-store-123"),
    ]
    assert len(ingestion_edges) == len(expected_ingestion_edges)

    for edge in ingestion_edges:
        source = edge["source"]
        target = edge["target"]
        assert (source, target) in expected_ingestion_edges, edge

    # Test RAG graph components and edges
    rag_graph_dump = rag_graph.dump(
        name="RAG Graph", description="Graph for Retrieval-Augmented Generation", endpoint_name="rag"
    )

    rag_data = rag_graph_dump["data"]
    rag_nodes = rag_data["nodes"]
    rag_edges = rag_data["edges"]

    # Sort nodes by id to check components
    rag_nodes = sorted(rag_nodes, key=operator.itemgetter("id"))

    # Check components in the RAG graph
    assert rag_nodes[0]["data"]["type"] == "ChatInput"
    assert rag_nodes[0]["id"] == "chatinput-123"

    assert rag_nodes[1]["data"]["type"] == "ChatOutput"
    assert rag_nodes[1]["id"] == "chatoutput-123"

    assert rag_nodes[2]["data"]["type"] == "OpenAIModel"
    assert rag_nodes[2]["id"] == "openai-123"

    assert rag_nodes[3]["data"]["type"] == "OpenAIEmbeddings"
    assert rag_nodes[3]["id"] == "openai-embeddings-124"

    assert rag_nodes[4]["data"]["type"] == "ParseData"
    assert rag_nodes[4]["id"] == "parse-data-123"

    assert rag_nodes[5]["data"]["type"] == "Prompt"
    assert rag_nodes[5]["id"] == "prompt-123"

    assert rag_nodes[6]["data"]["type"] == "AstraDB"
    assert rag_nodes[6]["id"] == "rag-vector-store-123"

    # Check edges in the RAG graph
    expected_rag_edges = [
        ("chatinput-123", "rag-vector-store-123"),
        ("openai-embeddings-124", "rag-vector-store-123"),
        ("chatinput-123", "prompt-123"),
        ("rag-vector-store-123", "parse-data-123"),
        ("parse-data-123", "prompt-123"),
        ("prompt-123", "openai-123"),
        ("openai-123", "chatoutput-123"),
    ]
    assert len(rag_edges) == len(expected_rag_edges), rag_edges

    for edge in rag_edges:
        source = edge["source"]
        target = edge["target"]
        assert (source, target) in expected_rag_edges, f"Edge {source} -> {target} not found"


def test_vector_store_rag_add(ingestion_graph: Graph, rag_graph: Graph):
    ingestion_graph_copy = copy.deepcopy(ingestion_graph)
    rag_graph_copy = copy.deepcopy(rag_graph)
    ingestion_graph_copy += rag_graph_copy

    assert (
        len(ingestion_graph_copy.vertices) == len(ingestion_graph.vertices) + len(rag_graph.vertices)
    ), f"Vertices mismatch: {len(ingestion_graph_copy.vertices)} != {len(ingestion_graph.vertices)} + {len(rag_graph.vertices)}"
    assert len(ingestion_graph_copy.edges) == len(ingestion_graph.edges) + len(
        rag_graph.edges
    ), f"Edges mismatch: {len(ingestion_graph_copy.edges)} != {len(ingestion_graph.edges)} + {len(rag_graph.edges)}"

    combined_graph_dump = ingestion_graph_copy.dump(
        name="Combined Graph", description="Graph for data ingestion and RAG", endpoint_name="combined"
    )

    combined_data = combined_graph_dump["data"]
    combined_nodes = combined_data["nodes"]
    combined_edges = combined_data["edges"]

    # Sort nodes by id to check components
    combined_nodes = sorted(combined_nodes, key=operator.itemgetter("id"))

    # Expected components in the combined graph (both ingestion and RAG nodes)
    expected_nodes = sorted(
        [
            {"id": "file-123", "type": "File"},
            {"id": "openai-embeddings-123", "type": "OpenAIEmbeddings"},
            {"id": "text-splitter-123", "type": "SplitText"},
            {"id": "vector-store-123", "type": "AstraDB"},
            {"id": "chatinput-123", "type": "ChatInput"},
            {"id": "chatoutput-123", "type": "ChatOutput"},
            {"id": "openai-123", "type": "OpenAIModel"},
            {"id": "openai-embeddings-124", "type": "OpenAIEmbeddings"},
            {"id": "parse-data-123", "type": "ParseData"},
            {"id": "prompt-123", "type": "Prompt"},
            {"id": "rag-vector-store-123", "type": "AstraDB"},
        ],
        key=operator.itemgetter("id"),
    )

    for expected_node, combined_node in zip(expected_nodes, combined_nodes, strict=True):
        assert combined_node["data"]["type"] == expected_node["type"]
        assert combined_node["id"] == expected_node["id"]

    # Expected edges in the combined graph (both ingestion and RAG edges)
    expected_combined_edges = [
        ("file-123", "text-splitter-123"),
        ("text-splitter-123", "vector-store-123"),
        ("openai-embeddings-123", "vector-store-123"),
        ("chatinput-123", "rag-vector-store-123"),
        ("openai-embeddings-124", "rag-vector-store-123"),
        ("chatinput-123", "prompt-123"),
        ("rag-vector-store-123", "parse-data-123"),
        ("parse-data-123", "prompt-123"),
        ("prompt-123", "openai-123"),
        ("openai-123", "chatoutput-123"),
    ]

    assert len(combined_edges) == len(expected_combined_edges), combined_edges

    for edge in combined_edges:
        source = edge["source"]
        target = edge["target"]
        assert (source, target) in expected_combined_edges, f"Edge {source} -> {target} not found"


def test_vector_store_rag_dump(ingestion_graph, rag_graph):
    # Test ingestion graph dump
    ingestion_graph_dump = ingestion_graph.dump(
        name="Ingestion Graph", description="Graph for data ingestion", endpoint_name="ingestion"
    )
    assert isinstance(ingestion_graph_dump, dict)

    ingestion_data = ingestion_graph_dump["data"]
    assert "nodes" in ingestion_data
    assert "edges" in ingestion_data
    assert "description" in ingestion_graph_dump
    assert "endpoint_name" in ingestion_graph_dump

    ingestion_nodes = ingestion_data["nodes"]
    ingestion_edges = ingestion_data["edges"]
    assert len(ingestion_nodes) == 4  # There are 4 components in the ingestion graph
    assert len(ingestion_edges) == 3  # There are 3 connections between components

    # Test RAG graph dump
    rag_graph_dump = rag_graph.dump(
        name="RAG Graph", description="Graph for Retrieval-Augmented Generation", endpoint_name="rag"
    )
    assert isinstance(rag_graph_dump, dict)

    rag_data = rag_graph_dump["data"]
    assert "nodes" in rag_data
    assert "edges" in rag_data
    assert "description" in rag_graph_dump
    assert "endpoint_name" in rag_graph_dump

    rag_nodes = rag_data["nodes"]
    rag_edges = rag_data["edges"]
    assert len(rag_nodes) == 7  # There are 7 components in the RAG graph
    assert len(rag_edges) == 7  # There are 7 connections between components
