from unittest.mock import Mock

import pytest
from langflow.graph.vertex.base import Vertex


# Mock dependencies
@pytest.fixture
def mock_graph():
    graph = Mock()
    graph.in_degree_map = {}
    graph.inactivated_vertices = set()
    graph.flow_id = "test_flow_id"
    graph.successor_map = {}
    graph.get_vertex_edges.return_value = []
    graph.get_predecessors.return_value = []
    graph.get_successors.return_value = []
    return graph


@pytest.fixture
def mock_node_data():
    return {
        "id": "test_vertex_id",
        "data": {
            "type": "TestType",
            "node": {
                "template": {"_type": "Component"},
                "_type": "Component",
                "display_name": "Test Vertex",
                "icon": "test_icon",
                "description": "Test description",
                "outputs": [],
            },
        },
    }


def test_get_node_property(mock_node_data, mock_graph):
    # Initialize Vertex
    vertex = Vertex(data=mock_node_data, graph=mock_graph)

    # Test existing property
    result = vertex.get_node_property("display_name")
    assert result == "Test Vertex", "The display_name property should return the correct value."

    # Test missing property with default value
    result = vertex.get_node_property("non_existing_property", default="default_value")
    assert result == "default_value", "The default value should be returned when the property does not exist."

    # Test missing property without default value
    result = vertex.get_node_property("non_existing_property")
    assert result is None, "None should be returned when the property does not exist and no default is provided."

    # Test empty node data
    vertex.data["node"] = None
    result = vertex.get_node_property("display_name")
    assert result is None, "None should be returned when the node data is missing."

    # Test empty data
    vertex.data = None
    result = vertex.get_node_property("display_name")
    assert result is None, "None should be returned when the data is missing."
