import json
from langflow.graph import Graph
from langflow.processing.process import load_or_build_langchain_object

import pytest
from langflow.interface.run import (
    build_langchain_object_with_caching,
)


def get_graph(_type="basic"):
    """Get a graph from a json file"""
    if _type == "basic":
        path = pytest.BASIC_EXAMPLE_PATH
    elif _type == "complex":
        path = pytest.COMPLEX_EXAMPLE_PATH
    elif _type == "openapi":
        path = pytest.OPENAPI_EXAMPLE_PATH

    with open(path, "r") as f:
        flow_graph = json.load(f)
    return flow_graph["data"]


@pytest.fixture
def basic_data_graph():
    return get_graph()


@pytest.fixture
def complex_data_graph():
    return get_graph("complex")


@pytest.fixture
def openapi_data_graph():
    return get_graph("openapi")


def langchain_objects_are_equal(obj1, obj2):
    return str(obj1) == str(obj2)


# Test load_or_build_langchain_object
def test_load_or_build_langchain_object_first_message_true(basic_data_graph):
    build_langchain_object_with_caching.clear_cache()
    graph = load_or_build_langchain_object(basic_data_graph, is_first_message=True)
    assert graph is not None


def test_load_or_build_langchain_object_first_message_false(basic_data_graph):
    graph = load_or_build_langchain_object(basic_data_graph, is_first_message=False)
    assert graph is not None


# Test build_langchain_object_with_caching
def test_build_langchain_object_with_caching(basic_data_graph):
    build_langchain_object_with_caching.clear_cache()
    graph = build_langchain_object_with_caching(basic_data_graph)
    assert graph is not None


# Test build_graph
def test_build_graph(basic_data_graph):
    graph = Graph.from_payload(basic_data_graph)
    assert graph is not None
    assert len(graph.nodes) == len(basic_data_graph["nodes"])
    assert len(graph.edges) == len(basic_data_graph["edges"])


# Test cache size limit
def test_cache_size_limit(basic_data_graph):
    build_langchain_object_with_caching.clear_cache()
    for i in range(11):
        modified_data_graph = basic_data_graph.copy()
        nodes = modified_data_graph["nodes"]
        node_id = nodes[0]["id"]
        # Now we replace all instances ode node_id with a new id in the json
        json_string = json.dumps(modified_data_graph)
        modified_json_string = json_string.replace(node_id, f"{node_id}_{i}")
        modified_data_graph_new_id = json.loads(modified_json_string)
        build_langchain_object_with_caching(modified_data_graph_new_id)

    assert len(build_langchain_object_with_caching.cache) == 10
