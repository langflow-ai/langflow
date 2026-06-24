import copy
import operator
from textwrap import dedent

import pytest
from lfx.components.data import FileComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.components.models_and_agents import PromptComponent
from lfx.components.processing import ParserComponent
from lfx.components.processing.split_text import SplitTextComponent
from lfx.graph.graph.base import Graph
from lfx.graph.graph.constants import Finish
from lfx.schema import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


def _sample_dataframe() -> DataFrame:
    return DataFrame(data=[Data(text="This is a test file.")])


def _file_component(component_id: str) -> FileComponent:
    file_component = FileComponent(_id=component_id)
    file_component.set(path="test.txt")
    file_component.set_on_output(name="message", value=Message(text="This is a test file."), cache=True)
    return file_component


@pytest.fixture
def ingestion_graph():
    file_component = _file_component("file-123")
    text_splitter = SplitTextComponent(_id="text-splitter-123")
    text_splitter.set(data_inputs=file_component.load_files_message)
    text_splitter.set_on_output(name="dataframe", value=_sample_dataframe(), cache=True)

    return Graph(file_component, text_splitter)


@pytest.fixture
def rag_graph():
    chat_input = ChatInput(_id="chatinput-123")
    chat_input.get_output("message").value = Message(text="What is the meaning of life?")

    file_component = _file_component("rag-file-123")
    text_splitter = SplitTextComponent(_id="rag-text-splitter-123")
    text_splitter.set(data_inputs=file_component.load_files_message)
    text_splitter.set_on_output(name="dataframe", value=_sample_dataframe(), cache=True)

    parse_data = ParserComponent(_id="parse-data-123")
    parse_data.set(input_data=text_splitter.split_text, mode="Stringify")
    prompt_component = PromptComponent(_id="prompt-123")
    prompt_component.set(
        template=dedent("""Given the following context, answer the question.
                         Context:{context}

                         Question: {question}
                         Answer:"""),
        context=parse_data.parse_combined_text,
        question=chat_input.message_response,
    )

    language_model_component = LanguageModelComponent(_id="language-model-123")
    language_model_component.set(input_value=prompt_component.build_prompt)
    language_model_component.set_on_output(name="text_output", value="Hello, world!", cache=True)

    chat_output = ChatOutput(_id="chatoutput-123")
    chat_output.set(input_value=language_model_component.text_response)

    return Graph(start=chat_input, end=chat_output)


async def test_vector_store_rag(ingestion_graph, rag_graph):
    assert ingestion_graph is not None
    ingestion_ids = [
        "file-123",
        "text-splitter-123",
    ]
    assert rag_graph is not None
    rag_ids = [
        "chatinput-123",
        "chatoutput-123",
        "language-model-123",
        "parse-data-123",
        "prompt-123",
        "rag-file-123",
        "rag-text-splitter-123",
    ]
    for ids, graph in [(ingestion_ids, ingestion_graph), (rag_ids, rag_graph)]:
        results = [result async for result in graph.async_start(reset_output_values=False)]
        vids = [result.vertex.id for result in results if hasattr(result, "vertex")]
        assert all(vid in ids for vid in vids), f"Diff: {set(vids) - set(ids)}"
        assert results[-1] == Finish()


def test_vector_store_rag_dump_components_and_edges(ingestion_graph, rag_graph):
    ingestion_graph_dump = ingestion_graph.dump(
        name="Ingestion Graph", description="Graph for data ingestion", endpoint_name="ingestion"
    )

    ingestion_data = ingestion_graph_dump["data"]
    ingestion_nodes = ingestion_data["nodes"]
    ingestion_edges = ingestion_data["edges"]

    expected_nodes = {
        "file-123": "File",
        "text-splitter-123": "SplitText",
    }

    assert len(ingestion_nodes) == len(expected_nodes), "Unexpected number of nodes"

    node_map = {node["id"]: node["data"] for node in ingestion_nodes}

    for node_id, expected_type in expected_nodes.items():
        assert node_id in node_map, f"Missing node {node_id}"
        assert node_map[node_id]["type"] == expected_type, (
            f"Node {node_id} has incorrect type. Expected {expected_type}, got {node_map[node_id]['type']}"
        )

    unexpected_nodes = set(node_map.keys()) - set(expected_nodes.keys())
    assert not unexpected_nodes, f"Found unexpected nodes: {unexpected_nodes}"

    expected_ingestion_edges = [
        ("file-123", "text-splitter-123"),
    ]
    assert len(ingestion_edges) == len(expected_ingestion_edges)

    for edge in ingestion_edges:
        source = edge["source"]
        target = edge["target"]
        assert (source, target) in expected_ingestion_edges, edge

    rag_graph_dump = rag_graph.dump(
        name="RAG Graph", description="Graph for Retrieval-Augmented Generation", endpoint_name="rag"
    )

    rag_data = rag_graph_dump["data"]
    rag_nodes = sorted(rag_data["nodes"], key=operator.itemgetter("id"))
    rag_edges = rag_data["edges"]

    expected_rag_nodes = sorted(
        [
            {"id": "chatinput-123", "type": "ChatInput"},
            {"id": "chatoutput-123", "type": "ChatOutput"},
            {"id": "language-model-123", "type": "LanguageModelComponent"},
            {"id": "parse-data-123", "type": "ParserComponent"},
            {"id": "prompt-123", "type": "Prompt Template"},
            {"id": "rag-file-123", "type": "File"},
            {"id": "rag-text-splitter-123", "type": "SplitText"},
        ],
        key=operator.itemgetter("id"),
    )

    for expected_node, node in zip(expected_rag_nodes, rag_nodes, strict=True):
        assert node["data"]["type"] == expected_node["type"]
        assert node["id"] == expected_node["id"]

    expected_rag_edges = [
        ("chatinput-123", "prompt-123"),
        ("language-model-123", "chatoutput-123"),
        ("parse-data-123", "prompt-123"),
        ("prompt-123", "language-model-123"),
        ("rag-file-123", "rag-text-splitter-123"),
        ("rag-text-splitter-123", "parse-data-123"),
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

    assert len(ingestion_graph_copy.vertices) == len(ingestion_graph.vertices) + len(rag_graph.vertices), (
        f"Vertices mismatch: {len(ingestion_graph_copy.vertices)} "
        f"!= {len(ingestion_graph.vertices)} + {len(rag_graph.vertices)}"
    )
    assert len(ingestion_graph_copy.edges) == len(ingestion_graph.edges) + len(rag_graph.edges), (
        f"Edges mismatch: {len(ingestion_graph_copy.edges)} != {len(ingestion_graph.edges)} + {len(rag_graph.edges)}"
    )

    combined_graph_dump = ingestion_graph_copy.dump(
        name="Combined Graph", description="Graph for data ingestion and RAG", endpoint_name="combined"
    )

    combined_data = combined_graph_dump["data"]
    combined_nodes = sorted(combined_data["nodes"], key=operator.itemgetter("id"))
    combined_edges = combined_data["edges"]

    expected_nodes = sorted(
        [
            {"id": "file-123", "type": "File"},
            {"id": "text-splitter-123", "type": "SplitText"},
            {"id": "chatinput-123", "type": "ChatInput"},
            {"id": "chatoutput-123", "type": "ChatOutput"},
            {"id": "language-model-123", "type": "LanguageModelComponent"},
            {"id": "parse-data-123", "type": "ParserComponent"},
            {"id": "prompt-123", "type": "Prompt Template"},
            {"id": "rag-file-123", "type": "File"},
            {"id": "rag-text-splitter-123", "type": "SplitText"},
        ],
        key=operator.itemgetter("id"),
    )

    for expected_node, combined_node in zip(expected_nodes, combined_nodes, strict=True):
        assert combined_node["data"]["type"] == expected_node["type"]
        assert combined_node["id"] == expected_node["id"]

    expected_combined_edges = [
        ("file-123", "text-splitter-123"),
        ("chatinput-123", "prompt-123"),
        ("language-model-123", "chatoutput-123"),
        ("parse-data-123", "prompt-123"),
        ("prompt-123", "language-model-123"),
        ("rag-file-123", "rag-text-splitter-123"),
        ("rag-text-splitter-123", "parse-data-123"),
    ]

    assert len(combined_edges) == len(expected_combined_edges), combined_edges

    for edge in combined_edges:
        source = edge["source"]
        target = edge["target"]
        assert (source, target) in expected_combined_edges, f"Edge {source} -> {target} not found"


def test_vector_store_rag_dump(ingestion_graph, rag_graph):
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
    assert len(ingestion_nodes) == 2
    assert len(ingestion_edges) == 1

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
    assert len(rag_nodes) == 7
    assert len(rag_edges) == 6
