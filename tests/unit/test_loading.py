import pytest
from langflow.graph import Graph
from langflow.graph.schema import RunOutputs
from langflow.initial_setup.setup import load_starter_projects
from langflow.load import load_flow_from_json, run_flow_from_json


@pytest.mark.noclient
def test_load_flow_from_json():
    """Test loading a flow from a json file"""
    loaded = load_flow_from_json(pytest.BASIC_EXAMPLE_PATH)
    assert loaded is not None
    assert isinstance(loaded, Graph)


@pytest.mark.noclient
def test_load_flow_from_json_with_tweaks():
    """Test loading a flow from a json file and applying tweaks"""
    tweaks = {"dndnode_82": {"model_name": "gpt-3.5-turbo-16k-0613"}}
    loaded = load_flow_from_json(pytest.BASIC_EXAMPLE_PATH, tweaks=tweaks)
    assert loaded is not None
    assert isinstance(loaded, Graph)


@pytest.mark.noclient
def test_load_flow_from_json_object():
    """Test loading a flow from a json file and applying tweaks"""
    _, projects = zip(*load_starter_projects())
    project = projects[0]
    loaded = load_flow_from_json(project)
    assert loaded is not None
    assert isinstance(loaded, Graph)


@pytest.mark.noclient
def test_run_flow_from_json_object():
    """Test loading a flow from a json file and applying tweaks"""
    _, projects = zip(*load_starter_projects())
    project = [project for project in projects if "Basic Prompting" in project["name"]][0]
    results = run_flow_from_json(project, input_value="test", fallback_to_env_vars=True)
    assert results is not None
    assert all(isinstance(result, RunOutputs) for result in results)
