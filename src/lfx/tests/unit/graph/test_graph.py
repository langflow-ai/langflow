import copy
import json

import pytest
from lfx.graph import Graph
from lfx.graph.graph.utils import (
    find_last_node,
    process_flow,
    set_new_target_handle,
    ungroup_node,
    update_source_handle,
    update_target_handle,
    update_template,
)
from lfx.graph.vertex.base import Vertex

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


def get_node_by_type(graph, node_type: type[Vertex]) -> Vertex | None:
    """Get a node by type."""
    return next((node for node in graph.vertices if isinstance(node, node_type)), None)


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
    g = Graph()
    with pytest.raises(KeyError):
        g.add_nodes_and_edges(graph_data["nodes"], graph_data["edges"])


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
    assert any("openai_api_key" in key for key in template_data)
    # Get the openai_api_key dict
    openai_api_key = next(
        (template_data[key] for key in template_data if "openai_api_key" in key),
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
            assert value in edges[idx][key].split("-")[0], (
                f"Edge {idx}, key {key} expected to contain {value} but got {edges[idx][key]}"
            )


def test_update_template(sample_template, sample_nodes):
    # Making a deep copy to keep original sample_nodes unchanged
    nodes_copy = copy.deepcopy(sample_nodes)
    update_template(sample_template, nodes_copy)

    # Now, validate the updates.
    node1_updated = next((n for n in nodes_copy if n["id"] == "node1"), None)
    node2_updated = next((n for n in nodes_copy if n["id"] == "node2"), None)
    node3_updated = next((n for n in nodes_copy if n["id"] == "node3"), None)

    assert node1_updated["data"]["node"]["template"]["some_field"]["show"] is True
    assert node1_updated["data"]["node"]["template"]["some_field"]["advanced"] is False
    assert node1_updated["data"]["node"]["template"]["some_field"]["display_name"] == "Name1"

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
    updated_edge = update_target_handle(new_edge, g_nodes)
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


# TODO: Move to Langflow tests
@pytest.mark.skip(reason="Temporarily disabled")
async def test_serialize_graph():
    pass
    # Get the actual starter projects and directly await the result
    # starter_projects = await load_starter_projects()
    # project_data = starter_projects[0][1]
    # data = project_data["data"]

    # # Create and test the graph
    # graph = Graph.from_payload(data)
    # assert isinstance(graph, Graph)
    # serialized = graph.dumps()
    # assert serialized is not None
    # assert isinstance(serialized, str)
    # assert len(serialized) > 0
