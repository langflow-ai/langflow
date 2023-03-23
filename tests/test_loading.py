import json
from langchain import LLMChain, OpenAI
import pytest
from pathlib import Path
from langflow import load_flow_from_json
from langflow.interface.loading import extract_json
from langflow.utils.payload import get_root_node, build_json
from langflow.interface.loading import load_langchain_type_from_config

EXAMPLE_JSON_PATH = Path(__file__).parent.absolute() / "data" / "example_flow.json"


def test_load_flow_from_json():
    """Test loading a flow from a json file"""
    loaded = load_flow_from_json(EXAMPLE_JSON_PATH)
    assert loaded is not None


def test_extract_json():
    with open(EXAMPLE_JSON_PATH, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    extracted = extract_json(data_graph)
    assert extracted is not None
    assert isinstance(extracted, dict)


def test_get_root_node():
    with open(EXAMPLE_JSON_PATH, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]
    root = get_root_node(nodes, edges)
    assert root is not None
    assert "id" in root
    assert "data" in root


def test_build_json():
    with open(EXAMPLE_JSON_PATH, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]
    root = get_root_node(nodes, edges)
    built_json = build_json(root, nodes, edges)
    assert built_json is not None
    assert isinstance(built_json, dict)


def test_build_json_missing_child():
    with open(EXAMPLE_JSON_PATH, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]

    # Modify nodes to create a missing required child scenario
    for node in nodes:
        if "data" in node and "node" in node["data"]:
            for key, value in node["data"]["node"]["template"].items():
                if isinstance(value, dict) and "required" in value:
                    value["required"] = True

    root = get_root_node(nodes, edges)
    with pytest.raises(ValueError):
        build_json(root, nodes, edges)


def test_build_json_no_nodes():
    with pytest.raises(TypeError):
        build_json(None, [], [])


def test_build_json_invalid_edge():
    with open(EXAMPLE_JSON_PATH, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]
    # Modify edges to create an invalid edge scenario
    for edge in edges:
        edge["source"] = "invalid_id"

    root = get_root_node(nodes, edges)
    with pytest.raises(ValueError):
        build_json(root, nodes, edges)


def test_load_langchain_type_from_config():
    with open(EXAMPLE_JSON_PATH, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    extracted = extract_json(data_graph)

    agent_config = extracted.copy()
    agent_type = "AgentExecutor"  # Replace with the actual agent type in the JSON

    invalid_config = extracted.copy()
    invalid_config["_type"] = "invalid_type"

    agent_loaded = load_langchain_type_from_config(agent_config)
    assert agent_loaded is not None
    assert agent_loaded.__class__.__name__ == agent_type
    assert hasattr(agent_loaded.agent, "llm_chain")
    assert isinstance(
        agent_loaded.agent.llm_chain, LLMChain
    )  # Replace Chain with the appropriate class
    assert hasattr(agent_loaded.agent.llm_chain, "llm")
    assert isinstance(agent_loaded.agent.llm_chain.llm, OpenAI)

    with pytest.raises(ValueError):
        load_langchain_type_from_config(invalid_config)
