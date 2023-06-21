import json

import pytest
from langchain.chains.base import Chain
from langflow.processing.process import load_flow_from_json
from langflow.graph import Graph
from langflow.utils.payload import get_root_node


def test_load_flow_from_json():
    """Test loading a flow from a json file"""
    loaded = load_flow_from_json(pytest.BASIC_EXAMPLE_PATH)
    assert loaded is not None
    assert isinstance(loaded, Chain)


def test_load_flow_from_json_with_tweaks():
    """Test loading a flow from a json file and applying tweaks"""
    tweaks = {"dndnode_82": {"model_name": "test model"}}
    loaded = load_flow_from_json(pytest.BASIC_EXAMPLE_PATH, tweaks=tweaks)
    assert loaded is not None
    assert isinstance(loaded, Chain)
    assert loaded.llm.model_name == "test model"


def test_get_root_node():
    with open(pytest.BASIC_EXAMPLE_PATH, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]
    graph = Graph(nodes, edges)
    root = get_root_node(graph)
    assert root is not None
    assert hasattr(root, "id")
    assert hasattr(root, "data")
