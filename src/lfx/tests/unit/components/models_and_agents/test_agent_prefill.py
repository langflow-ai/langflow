from uuid import uuid4

import pytest
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.schema.dotdict import dotdict


@pytest.mark.asyncio
async def test_agent_component_update_build_config_prefill_watsonx(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("WATSONX_APIKEY", "test-api-key")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("WATSONX_URL", "https://test.watsonx.ai")

    agent = AgentComponent()
    agent._user_id = uuid4()

    # Provide all required keys to avoid validation error
    build_config = dotdict(
        {
            "model": {"value": [{"name": "ibm/granite-3-8b-instruct", "provider": "IBM WatsonX"}]},
            "api_key": {"value": ""},
            "project_id": {"value": ""},
            "base_url_ibm_watsonx": {"value": "https://us-south.ml.cloud.ibm.com"},
            "code": {"value": ""},
            "_type": {"value": ""},
            "tools": {"value": []},
            "input_value": {"value": ""},
            "add_current_date_tool": {"value": False},
            "system_prompt": {"value": ""},
            "agent_description": {"value": ""},
            "max_iterations": {"value": 10},
            "handle_parsing_errors": {"value": True},
            "verbose": {"value": True},
            "memory": {"value": None},
        }
    )

    # Call update_build_config (e.g. when and component is loaded)
    updated_config = await agent.update_build_config(build_config, field_value=None, field_name=None)

    assert updated_config["api_key"]["value"] == "test-api-key"
    assert updated_config["project_id"]["value"] == "test-project-id"
    assert updated_config["base_url_ibm_watsonx"]["value"] == "https://test.watsonx.ai"


@pytest.mark.asyncio
async def test_agent_component_update_build_config_on_model_change(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("WATSONX_APIKEY", "new-api-key")

    agent = AgentComponent()
    agent._user_id = uuid4()

    build_config = dotdict(
        {
            "model": {"value": []},
            "api_key": {"value": ""},
            "project_id": {"value": ""},
            "base_url_ibm_watsonx": {"value": ""},
            "code": {"value": ""},
            "_type": {"value": ""},
            "tools": {"value": []},
            "input_value": {"value": ""},
            "add_current_date_tool": {"value": False},
            "system_prompt": {"value": ""},
            "agent_description": {"value": ""},
            "max_iterations": {"value": 10},
            "handle_parsing_errors": {"value": True},
            "verbose": {"value": True},
            "memory": {"value": None},
        }
    )

    # Simulate model selection
    new_model_value = [{"name": "ibm/granite", "provider": "IBM WatsonX"}]
    updated_config = await agent.update_build_config(build_config, field_value=new_model_value, field_name="model")

    assert updated_config["api_key"]["value"] == "new-api-key"
