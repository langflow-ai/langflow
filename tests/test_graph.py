import json
from langflow.utils.graph import Graph
import pytest
from langflow.utils.payload import get_root_node

# Test cases for the graph module


def get_graph(basic=True):
    """Get a graph from a json file"""
    path = pytest.BASIC_EXAMPLE_PATH if basic else pytest.COMPLEX_EXAMPLE_PATH
    with open(path, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]
    return Graph(nodes, edges)


def test_get_connected_nodes():
    """Test getting connected nodes"""
    graph = get_graph()
    assert isinstance(graph, Graph)
    # Get root node
    root = get_root_node(graph)
    assert root is not None
    connected_nodes = graph.get_connected_nodes(root)
    assert connected_nodes is not None


def test_get_node_neighbors():
    """Test getting node neighbors"""

    graph = get_graph(basic=True)
    assert isinstance(graph, Graph)
    # Get root node
    root = get_root_node(graph)
    assert root is not None
    neighbors = graph.get_node_neighbors(root)
    assert neighbors is not None
    assert isinstance(neighbors, dict)
    # Root Node is an Agent, it requires an LLMChain and tools
    # We need to check if there is a Chain in the one of the neighbors'
    # data attribute in the type key
    assert any(
        "Chain" in neighbor.data["type"] for neighbor, val in neighbors.items() if val
    )
    # assert Serper Search is in the neighbors
    assert any(
        "Serper" in neighbor.data["type"] for neighbor, val in neighbors.items() if val
    )
    # Now on to the Chain's neighbors
    chain = next(
        neighbor
        for neighbor, val in neighbors.items()
        if "Chain" in neighbor.data["type"] and val
    )
    chain_neighbors = graph.get_node_neighbors(chain)
    assert chain_neighbors is not None
    assert isinstance(chain_neighbors, dict)
    # Check if there is a LLM in the chain's neighbors
    assert any(
        "OpenAI" in neighbor.data["type"]
        for neighbor, val in chain_neighbors.items()
        if val
    )
    # Chain should have a Prompt as a neighbor
    assert any(
        "Prompt" in neighbor.data["type"]
        for neighbor, val in chain_neighbors.items()
        if val
    )
