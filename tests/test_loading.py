from pathlib import Path

from langflow import load_flow_from_json


def test_load_flow_from_json():
    """Test loading a flow from a json file"""
    path = Path(__file__).parent.absolute()
    path = f"{path}/data/example_flow.json"
    loaded = load_flow_from_json(path)
    assert loaded is not None
