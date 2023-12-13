import copy
import json
import os
import pickle
from pathlib import Path
from typing import Type, Union

import pytest
from langchain.agents import AgentExecutor
from langchain.chains.base import Chain
from langchain.llms.fake import FakeListLLM

from langflow.graph import Graph
from langflow.graph.edge.base import Edge
from langflow.graph.graph.utils import (
    find_last_node,
    process_flow,
    set_new_target_handle,
    ungroup_node,
    update_source_handle,
    update_target_handle,
    update_template,
)
from langflow.graph.utils import UnbuiltObject
from langflow.graph.vertex.base import Vertex
from langflow.graph.vertex.types import FileToolVertex, LLMVertex, ToolkitVertex
from langflow.processing.process import get_result_and_thought
from langflow.utils.payload import get_root_vertex

# Test cases for the graph module

# now we have three types of graph:
# BASIC_EXAMPLE_PATH, COMPLEX_EXAMPLE_PATH, OPENAPI_EXAMPLE_PATH


@pytest.fixture
def sample_template():
    return {
        "field1": {"proxy": {"field": "some_field", "id": "node1"}},
        "field2": {"proxy": {"field": "other_field", "id": "node2"}},
    }


@pytest.fixture
def sample_nodes():
    return [
        {
            "id": "node1",
            "data": {"node": {"template": {"some_field": {"show": True, "advanced": False, "name": "Name1"}}}},
        },
        {
            "id": "node2",
            "data": {
                "node": {
                    "template": {
                        "other_field": {
                            "show": False,
                            "advanced": True,
                            "display_name": "DisplayName2",
                        }
                    }
                }
            },
        },
        {
            "id": "node3",
            "data": {"node": {"template": {"unrelated_field": {"show": True, "advanced": True}}}},
        },
    ]


def get_node_by_type(graph, node_type: Type[Vertex]) -> Union[Vertex, None]:
    """Get a node by type"""
    return next((node for node in graph.vertices if isinstance(node, node_type)), None)


def test_graph_structure(basic_graph):
    assert isinstance(basic_graph, Graph)
    assert len(basic_graph.vertices) > 0
    assert len(basic_graph.edges) > 0
    for node in basic_graph.vertices:
        assert isinstance(node, Vertex)
    for edge in basic_graph.edges:
        assert isinstance(edge, Edge)
        assert edge.source_id in basic_graph.vertex_map.keys()
        assert edge.target_id in basic_graph.vertex_map.keys()


def test_circular_dependencies(basic_graph):
    assert isinstance(basic_graph, Graph)

    def check_circular(node, visited):
        visited.add(node)
        neighbors = basic_graph.get_vertices_with_target(node)
        for neighbor in neighbors:
            if neighbor in visited:
                return True
            if check_circular(neighbor, visited.copy()):
                return True
        return False

    for node in basic_graph.vertices:
        assert not check_circular(node, set())


def test_invalid_node_types():
    graph_data = {
        "nodes": [
            {
                "id": "1",
                "data": {
                    "node": {
                        "base_classes": ["BaseClass"],
                        "template": {
                            "_type": "InvalidNodeType",
                        },
                    },
                },
            },
        ],
        "edges": [],
    }
    with pytest.raises(Exception):
        Graph(graph_data["nodes"], graph_data["edges"])


def test_get_vertices_with_target(basic_graph):
    """Test getting connected nodes"""
    assert isinstance(basic_graph, Graph)
    # Get root node
    root = get_root_vertex(basic_graph)
    assert root is not None
    connected_nodes = basic_graph.get_vertices_with_target(root.id)
    assert connected_nodes is not None


def test_get_node_neighbors_basic(basic_graph):
    """Test getting node neighbors"""

    assert isinstance(basic_graph, Graph)
    # Get root node
    root = get_root_vertex(basic_graph)
    assert root is not None
    neighbors = basic_graph.get_vertex_neighbors(root)
    assert neighbors is not None
    assert isinstance(neighbors, dict)
    # Root Node is an Agent, it requires an LLMChain and tools
    # We need to check if there is a Chain in the one of the neighbors'
    # data attribute in the type key
    assert any("ConversationBufferMemory" in neighbor.data["type"] for neighbor, val in neighbors.items() if val)

    assert any("OpenAI" in neighbor.data["type"] for neighbor, val in neighbors.items() if val)


# def test_get_node_neighbors_complex(complex_graph):
#     """Test getting node neighbors"""
#     assert isinstance(complex_graph, Graph)
#     # Get root node
#     root = get_root_node(complex_graph)
#     assert root is not None
#     neighbors = complex_graph.get_nodes_with_target(root)
#     assert neighbors is not None
#     # Neighbors should be a list of nodes
#     assert isinstance(neighbors, list)
#     # Root Node is an Agent, it requires an LLMChain and tools
#     # We need to check if there is a Chain in the one of the neighbors'
#     assert any("Chain" in neighbor.data["type"] for neighbor in neighbors)
#     # assert Tool is in the neighbors
#     assert any("Tool" in neighbor.data["type"] for neighbor in neighbors)
#     # Now on to the Chain's neighbors
#     chain = next(neighbor for neighbor in neighbors if "Chain" in neighbor.data["type"])
#     chain_neighbors = complex_graph.get_nodes_with_target(chain)
#     assert chain_neighbors is not None
#     # Check if there is a LLM in the chain's neighbors
#     assert any("OpenAI" in neighbor.data["type"] for neighbor in chain_neighbors)
#     # Chain should have a Prompt as a neighbor
#     assert any("Prompt" in neighbor.data["type"] for neighbor in chain_neighbors)
#     # Now on to the Tool's neighbors
#     tool = next(neighbor for neighbor in neighbors if "Tool" in neighbor.data["type"])
#     tool_neighbors = complex_graph.get_nodes_with_target(tool)
#     assert tool_neighbors is not None
#     # Check if there is an Agent in the tool's neighbors
#     assert any("Agent" in neighbor.data["type"] for neighbor in tool_neighbors)
#     # This Agent has a Tool that has a PythonFunction as func
#     agent = next(
#         neighbor for neighbor in tool_neighbors if "Agent" in neighbor.data["type"]
#     )
#     agent_neighbors = complex_graph.get_nodes_with_target(agent)
#     assert agent_neighbors is not None
#     # Check if there is a Tool in the agent's neighbors
#     assert any("Tool" in neighbor.data["type"] for neighbor in agent_neighbors)
#     # This Tool has a PythonFunction as func
#     tool = next(
#         neighbor for neighbor in agent_neighbors if "Tool" in neighbor.data["type"]
#     )
#     tool_neighbors = complex_graph.get_nodes_with_target(tool)
#     assert tool_neighbors is not None
#     # Check if there is a PythonFunction in the tool's neighbors
#     assert any(
#         "PythonFunctionTool" in neighbor.data["type"] for neighbor in tool_neighbors
#     )


def test_get_node(basic_graph):
    """Test getting a single node"""
    node_id = basic_graph.vertices[0].id
    node = basic_graph.get_vertex(node_id)
    assert isinstance(node, Vertex)
    assert node.id == node_id


def test_build_nodes(basic_graph):
    """Test building nodes"""

    assert len(basic_graph.vertices) == len(basic_graph._vertices)
    for node in basic_graph.vertices:
        assert isinstance(node, Vertex)


def test_build_edges(basic_graph):
    """Test building edges"""
    assert len(basic_graph.edges) == len(basic_graph._edges)
    for edge in basic_graph.edges:
        assert isinstance(edge, Edge)

        assert isinstance(edge.source_id, str)
        assert isinstance(edge.target_id, str)


def test_get_root_vertex(client, basic_graph, complex_graph):
    """Test getting root node"""
    assert isinstance(basic_graph, Graph)
    root = get_root_vertex(basic_graph)
    assert root is not None
    assert isinstance(root, Vertex)
    assert root.data["type"] == "TimeTravelGuideChain"
    # For complex example, the root node is a ZeroShotAgent too
    assert isinstance(complex_graph, Graph)
    root = get_root_vertex(complex_graph)
    assert root is not None
    assert isinstance(root, Vertex)
    assert root.data["type"] == "ZeroShotAgent"


def test_validate_edges(basic_graph):
    """Test validating edges"""

    assert isinstance(basic_graph, Graph)
    # all edges should be valid
    assert all(edge.valid for edge in basic_graph.edges)


def test_matched_type(basic_graph):
    """Test matched type attribute in Edge"""
    assert isinstance(basic_graph, Graph)
    # all edges should be valid
    assert all(edge.valid for edge in basic_graph.edges)
    # all edges should have a matched_type attribute
    assert all(hasattr(edge, "matched_type") for edge in basic_graph.edges)
    # The matched_type attribute should be in the source_types attr
    assert all(edge.matched_type in edge.source_types for edge in basic_graph.edges)


def test_build_params(basic_graph):
    """Test building params"""

    assert isinstance(basic_graph, Graph)
    # all edges should be valid
    assert all(edge.valid for edge in basic_graph.edges)
    # all edges should have a matched_type attribute
    assert all(hasattr(edge, "matched_type") for edge in basic_graph.edges)
    # The matched_type attribute should be in the source_types attr
    assert all(edge.matched_type in edge.source_types for edge in basic_graph.edges)
    # Get the root node
    root = get_root_vertex(basic_graph)
    # Root node is a TimeTravelGuideChain
    # which requires an llm and memory
    assert root is not None
    assert isinstance(root.params, dict)
    assert "llm" in root.params
    assert "memory" in root.params


@pytest.mark.asyncio
async def test_build(basic_graph):
    """Test Node's build method"""
    await assert_agent_was_built(basic_graph)


async def assert_agent_was_built(graph):
    """Assert that the agent was built"""
    assert isinstance(graph, Graph)
    # Now we test the build method
    # Build the Agent
    result = await graph.build()
    # The agent should be a AgentExecutor
    assert isinstance(result, Chain)


@pytest.mark.asyncio
async def test_llm_node_build(basic_graph):
    llm_node = get_node_by_type(basic_graph, LLMVertex)
    assert llm_node is not None
    built_object = await llm_node.build()
    assert built_object is not UnbuiltObject()


@pytest.mark.asyncio
async def test_toolkit_node_build(client, openapi_graph):
    # Write a file to the disk
    file_path = "api-with-examples.yaml"
    with open(file_path, "w") as f:
        f.write("openapi: 3.0.0")

    toolkit_node = get_node_by_type(openapi_graph, ToolkitVertex)
    assert toolkit_node is not None
    built_object = await toolkit_node.build()
    assert built_object is not UnbuiltObject
    # Remove the file
    os.remove(file_path)
    assert not Path(file_path).exists()


@pytest.mark.asyncio
async def test_file_tool_node_build(client, openapi_graph):
    file_path = "api-with-examples.yaml"
    with open(file_path, "w") as f:
        f.write("openapi: 3.0.0")

    assert Path(file_path).exists()
    file_tool_node = get_node_by_type(openapi_graph, FileToolVertex)
    assert file_tool_node is not UnbuiltObject and file_tool_node is not None
    built_object = await file_tool_node.build()
    assert built_object is not UnbuiltObject
    # Remove the file
    os.remove(file_path)
    assert not Path(file_path).exists()


@pytest.mark.asyncio
async def test_get_result_and_thought(basic_graph):
    """Test the get_result_and_thought method"""
    responses = [
        "Final Answer: I am a response",
    ]
    message = {"input": "Hello"}
    # Find the node that is an LLMNode and change the
    # _built_object to a FakeListLLM
    llm_node = get_node_by_type(basic_graph, LLMVertex)
    assert llm_node is not None
    llm_node._built_object = FakeListLLM(responses=responses)
    llm_node._built = True
    langchain_object = await basic_graph.build()
    # assert all nodes are built
    assert all(node._built for node in basic_graph.vertices)
    # now build again and check if FakeListLLM was used

    # Get the result and thought
    result = get_result_and_thought(langchain_object, message)
    assert isinstance(result, dict)


def test_find_last_node(grouped_chat_json_flow):
    grouped_chat_data = json.loads(grouped_chat_json_flow).get("data")
    nodes, edges = grouped_chat_data["nodes"], grouped_chat_data["edges"]
    last_node = find_last_node(nodes, edges)
    assert last_node is not None  # Replace with the actual expected value
    assert last_node["id"] == "LLMChain-pimAb"  # Replace with the actual expected value


def test_ungroup_node(grouped_chat_json_flow):
    grouped_chat_data = json.loads(grouped_chat_json_flow).get("data")
    group_node = grouped_chat_data["nodes"][2]  # Assuming the first node is a group node
    base_flow = copy.deepcopy(grouped_chat_data)
    ungroup_node(group_node["data"], base_flow)
    # after ungroup_node is called, the base_flow and grouped_chat_data should be different
    assert base_flow != grouped_chat_data
    # assert node 2 is not a group node anymore
    assert base_flow["nodes"][2]["data"]["node"].get("flow") is None
    # assert the edges are updated
    assert len(base_flow["edges"]) > len(grouped_chat_data["edges"])
    assert base_flow["edges"][0]["source"] == "ConversationBufferMemory-kUMif"
    assert base_flow["edges"][0]["target"] == "LLMChain-2P369"
    assert base_flow["edges"][1]["source"] == "PromptTemplate-Wjk4g"
    assert base_flow["edges"][1]["target"] == "LLMChain-2P369"
    assert base_flow["edges"][2]["source"] == "ChatOpenAI-rUJ1b"
    assert base_flow["edges"][2]["target"] == "LLMChain-2P369"


def test_process_flow(grouped_chat_json_flow):
    grouped_chat_data = json.loads(grouped_chat_json_flow).get("data")

    processed_flow = process_flow(grouped_chat_data)
    assert processed_flow is not None
    assert isinstance(processed_flow, dict)
    assert "nodes" in processed_flow
    assert "edges" in processed_flow


def test_process_flow_one_group(one_grouped_chat_json_flow):
    grouped_chat_data = json.loads(one_grouped_chat_json_flow).get("data")
    # There should be only one node
    assert len(grouped_chat_data["nodes"]) == 1
    # Get the node, it should be a group node
    group_node = grouped_chat_data["nodes"][0]
    node_data = group_node["data"]["node"]
    assert node_data.get("flow") is not None
    template_data = node_data["template"]
    assert any("openai_api_key" in key for key in template_data.keys())
    # Get the openai_api_key dict
    openai_api_key = next(
        (template_data[key] for key in template_data.keys() if "openai_api_key" in key),
        None,
    )
    assert openai_api_key is not None
    assert openai_api_key["value"] == "test"

    processed_flow = process_flow(grouped_chat_data)
    assert processed_flow is not None
    assert isinstance(processed_flow, dict)
    assert "nodes" in processed_flow
    assert "edges" in processed_flow

    # Now get the node that has ChatOpenAI in its id
    chat_openai_node = next((node for node in processed_flow["nodes"] if "ChatOpenAI" in node["id"]), None)
    assert chat_openai_node is not None
    assert chat_openai_node["data"]["node"]["template"]["openai_api_key"]["value"] == "test"


def test_process_flow_vector_store_grouped(vector_store_grouped_json_flow):
    grouped_chat_data = json.loads(vector_store_grouped_json_flow).get("data")
    nodes = grouped_chat_data["nodes"]
    assert len(nodes) == 4
    # There are two group nodes in this flow
    # One of them is inside the other totalling 7 nodes
    # 4 nodes grouped, one of these turns into 1 normal node and 1 group node
    # This group node has 2 nodes inside it

    processed_flow = process_flow(grouped_chat_data)
    assert processed_flow is not None
    processed_nodes = processed_flow["nodes"]
    assert len(processed_nodes) == 7
    assert isinstance(processed_flow, dict)
    assert "nodes" in processed_flow
    assert "edges" in processed_flow
    edges = processed_flow["edges"]
    # Expected keywords in source and target fields
    expected_keywords = [
        {"source": "VectorStoreInfo", "target": "VectorStoreAgent"},
        {"source": "ChatOpenAI", "target": "VectorStoreAgent"},
        {"source": "OpenAIEmbeddings", "target": "Chroma"},
        {"source": "Chroma", "target": "VectorStoreInfo"},
        {"source": "WebBaseLoader", "target": "RecursiveCharacterTextSplitter"},
        {"source": "RecursiveCharacterTextSplitter", "target": "Chroma"},
    ]

    for idx, expected_keyword in enumerate(expected_keywords):
        for key, value in expected_keyword.items():
            assert (
                value in edges[idx][key].split("-")[0]
            ), f"Edge {idx}, key {key} expected to contain {value} but got {edges[idx][key]}"


def test_update_template(sample_template, sample_nodes):
    # Making a deep copy to keep original sample_nodes unchanged
    nodes_copy = copy.deepcopy(sample_nodes)
    update_template(sample_template, nodes_copy)

    # Now, validate the updates.
    node1_updated = next((n for n in nodes_copy if n["id"] == "node1"), None)
    node2_updated = next((n for n in nodes_copy if n["id"] == "node2"), None)
    node3_updated = next((n for n in nodes_copy if n["id"] == "node3"), None)

    assert node1_updated is not None
    assert node1_updated["data"]["node"]["template"]["some_field"]["show"] is True
    assert node1_updated["data"]["node"]["template"]["some_field"]["advanced"] is False
    assert node1_updated["data"]["node"]["template"]["some_field"]["display_name"] == "Name1"

    assert node2_updated is not None
    assert node2_updated["data"]["node"]["template"]["other_field"]["show"] is False
    assert node2_updated["data"]["node"]["template"]["other_field"]["advanced"] is True
    assert node2_updated["data"]["node"]["template"]["other_field"]["display_name"] == "DisplayName2"

    # Ensure node3 remains unchanged
    assert node3_updated == sample_nodes[2]


# Test `update_target_handle`
def test_update_target_handle_proxy():
    new_edge = {
        "data": {
            "targetHandle": {
                "type": "some_type",
                "proxy": {"id": "some_id", "field": ""},
            }
        }
    }
    g_nodes = [{"id": "some_id", "data": {"node": {"flow": None}}}]
    group_node_id = "group_id"
    updated_edge = update_target_handle(new_edge, g_nodes, group_node_id)
    assert updated_edge["data"]["targetHandle"] == new_edge["data"]["targetHandle"]


# Test `set_new_target_handle`
def test_set_new_target_handle():
    proxy_id = "proxy_id"
    new_edge = {"target": None, "data": {"targetHandle": {}}}
    target_handle = {"type": "type_1", "proxy": {"field": "field_1"}}
    node = {
        "data": {
            "node": {
                "flow": True,
                "template": {"field_1": {"proxy": {"field": "new_field", "id": "new_id"}}},
            }
        }
    }
    set_new_target_handle(proxy_id, new_edge, target_handle, node)
    assert new_edge["target"] == "proxy_id"
    assert new_edge["data"]["targetHandle"]["fieldName"] == "field_1"
    assert new_edge["data"]["targetHandle"]["proxy"] == {
        "field": "new_field",
        "id": "new_id",
    }


# Test `update_source_handle`
def test_update_source_handle():
    new_edge = {"source": None, "data": {"sourceHandle": {"id": None}}}
    flow_data = {
        "nodes": [{"id": "some_node"}, {"id": "last_node"}],
        "edges": [{"source": "some_node"}],
    }
    updated_edge = update_source_handle(new_edge, flow_data["nodes"], flow_data["edges"])
    assert updated_edge["source"] == "last_node"
    assert updated_edge["data"]["sourceHandle"]["id"] == "last_node"


@pytest.mark.asyncio
async def test_pickle_graph(json_vector_store):
    loaded_json = json.loads(json_vector_store)
    graph = Graph.from_payload(loaded_json)
    assert isinstance(graph, Graph)
    first_result = await graph.build()
    assert isinstance(first_result, AgentExecutor)
    pickled = pickle.dumps(graph)
    assert pickled is not UnbuiltObject
    unpickled = pickle.loads(pickled)
    assert unpickled is not UnbuiltObject
    result = await unpickled.build()
    assert isinstance(result, AgentExecutor)


@pytest.mark.asyncio
async def test_pickle_each_vertex(json_vector_store):
    loaded_json = json.loads(json_vector_store)
    graph = Graph.from_payload(loaded_json)
    assert isinstance(graph, Graph)
    for vertex in graph.vertices:
        await vertex.build()
        pickled = pickle.dumps(vertex)
        assert pickled is not UnbuiltObject
        unpickled = pickle.loads(pickled)
        assert unpickled is not UnbuiltObject
