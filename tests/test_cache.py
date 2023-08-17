import json
from langflow.graph import Graph
from langflow.services.cache.utils import compute_dict_hash

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


# Test build_langchain_object_with_caching
def test_build_langchain_object_with_caching(client, basic_data_graph):
    session_id = compute_dict_hash(basic_data_graph)
    build_langchain_object_with_caching.clear_cache(session_id)
    graph = build_langchain_object_with_caching(basic_data_graph)
    assert graph is not None


# Test build_graph
def test_build_graph(basic_data_graph):
    graph = Graph.from_payload(basic_data_graph)
    assert graph is not None
    assert len(graph.nodes) == len(basic_data_graph["nodes"])
    assert len(graph.edges) == len(basic_data_graph["edges"])
