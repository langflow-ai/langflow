import json

from langflow.graph import Graph
from langflow.graph.schema import RunOutputs
from langflow.load import aload_flow_from_json, arun_flow_from_json


async def test_load_flow_from_json(json_memory_chatbot_no_llm):
    """Test loading a flow from a json file."""
    memory_chatbot_no_llm_dict = json.loads(json_memory_chatbot_no_llm)
    loaded = await aload_flow_from_json(memory_chatbot_no_llm_dict)
    assert loaded is not None
    assert isinstance(loaded, Graph)


async def test_load_flow_from_json_with_tweaks(json_memory_chatbot_no_llm):
    """Test loading a flow from a json file and applying tweaks."""
    memory_chatbot_no_llm_dict = json.loads(json_memory_chatbot_no_llm)
    tweaks = {"dndnode_82": {"model_name": "gpt-3.5-turbo-16k-0613"}}
    loaded = await aload_flow_from_json(memory_chatbot_no_llm_dict, tweaks=tweaks)
    assert loaded is not None
    assert isinstance(loaded, Graph)


async def test_run_flow_from_json(json_memory_chatbot_no_llm):
    """Test running a flow from a json file."""
    memory_chatbot_no_llm_dict = json.loads(json_memory_chatbot_no_llm)
    loaded = await arun_flow_from_json(memory_chatbot_no_llm_dict, input_value="Hello", session_id="test")
    assert loaded is not None
    assert isinstance(loaded, list)
    # all should be RunOutputs
    assert all(isinstance(item, RunOutputs) for item in loaded)
