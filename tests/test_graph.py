import json
from langflow.utils.graph import Edge, Graph, Node
import pytest
from langflow.utils.payload import build_json, get_root_node

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


def test_get_nodes_with_target():
    """Test getting connected nodes"""
    graph = get_graph()
    assert isinstance(graph, Graph)
    # Get root node
    root = get_root_node(graph)
    assert root is not None
    connected_nodes = graph.get_nodes_with_target(root)
    assert connected_nodes is not None


def test_get_node_neighbors_basic():
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


def test_get_node_neighbors_complex():
    """Test getting node neighbors"""

    graph = get_graph(basic=False)
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
    # assert BaseTool is in the neighbors
    assert any(
        "BaseTool" in neighbor.data["type"]
        for neighbor, val in neighbors.items()
        if val
    )
    # Now on to the BaseTool's neighbors
    base_tool = next(
        neighbor
        for neighbor, val in neighbors.items()
        if "BaseTool" in neighbor.data["type"] and val
    )
    base_tool_neighbors = graph.get_node_neighbors(base_tool)
    assert base_tool_neighbors is not None
    assert isinstance(base_tool_neighbors, dict)
    # Check if there is an ZeroShotAgent in the base_tool's neighbors
    assert any(
        "ZeroShotAgent" in neighbor.data["type"]
        for neighbor, val in base_tool_neighbors.items()
        if val
    )


def test_get_node():
    """Test getting a single node"""
    graph = get_graph()
    node_id = graph.nodes[0].id
    node = graph.get_node(node_id)
    assert isinstance(node, Node)
    assert node.id == node_id


def test_build_nodes():
    """Test building nodes"""
    graph = get_graph()
    assert len(graph.nodes) == len(graph._nodes)
    for node in graph.nodes:
        assert isinstance(node, Node)


def test_build_edges():
    """Test building edges"""
    graph = get_graph()
    assert len(graph.edges) == len(graph._edges)
    for edge in graph.edges:
        assert isinstance(edge, Edge)
        assert isinstance(edge.source, Node)
        assert isinstance(edge.target, Node)


def test_get_root_node():
    """Test getting root node"""
    graph = get_graph(basic=True)
    assert isinstance(graph, Graph)
    root = get_root_node(graph)
    assert root is not None
    assert isinstance(root, Node)
    assert root.data["type"] == "ZeroShotAgent"
    # For complex example, the root node is a ZeroShotAgent too
    graph = get_graph(basic=False)
    assert isinstance(graph, Graph)
    root = get_root_node(graph)
    assert root is not None
    assert isinstance(root, Node)
    assert root.data["type"] == "ZeroShotAgent"


def test_build_json():
    """Test building JSON from graph"""
    graph = get_graph()
    assert isinstance(graph, Graph)
    root = get_root_node(graph)
    json_data = build_json(root, graph)
    assert isinstance(json_data, dict)
    assert json_data["_type"] == "zero-shot-react-description"
    assert isinstance(json_data["llm_chain"], dict)
    assert json_data["llm_chain"]["_type"] == "llm_chain"
    assert json_data["llm_chain"]["memory"] is None
    assert json_data["llm_chain"]["verbose"] is False
    assert isinstance(json_data["llm_chain"]["prompt"], dict)
    assert isinstance(json_data["llm_chain"]["llm"], dict)
    assert json_data["llm_chain"]["output_key"] == "text"
    assert isinstance(json_data["allowed_tools"], list)
    assert all(isinstance(tool, dict) for tool in json_data["allowed_tools"])
    assert isinstance(json_data["return_values"], list)
    assert all(isinstance(val, str) for val in json_data["return_values"])


def test_validate_edges():
    """Test validating edges"""
    graph = get_graph()
    assert isinstance(graph, Graph)
    # all edges should be valid
    assert all(edge.valid for edge in graph.edges)
