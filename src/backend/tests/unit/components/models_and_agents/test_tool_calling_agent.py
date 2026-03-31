from unittest.mock import patch

import pytest
from lfx.components.langchain_utilities import ToolCallingAgentComponent
from lfx.components.openai.openai_chat_model import OpenAIModelComponent
from lfx.components.tools.calculator import CalculatorToolComponent


class TestToolCallingAgentUpdateBuildConfig:
    """Unit tests for ToolCallingAgentComponent.update_build_config field visibility."""

    def _make_component(self):
        component = ToolCallingAgentComponent()
        component._user_id = None
        component.cache = {}
        return component

    def _get_build_config(self, component):
        return component.to_frontend_node()["data"]["node"]["template"]

    @patch("lfx.components.langchain_utilities.tool_calling.get_language_model_options")
    def test_shows_watsonx_fields_when_watsonx_selected(self, mock_opts):
        """Selecting IBM WatsonX should show base_url_ibm_watsonx and project_id."""
        watsonx_model = [{"name": "ibm/granite-13b-chat-v2", "provider": "IBM WatsonX", "metadata": {}}]
        mock_opts.return_value = watsonx_model
        component = self._make_component()
        build_config = self._get_build_config(component)

        updated = component.update_build_config(build_config, watsonx_model, field_name="model")

        assert updated["base_url_ibm_watsonx"]["show"] is True
        assert updated["base_url_ibm_watsonx"]["required"] is False
        assert updated["project_id"]["show"] is True
        assert "ollama_base_url" not in updated

    @patch("lfx.components.langchain_utilities.tool_calling.get_language_model_options")
    def test_hides_watsonx_fields_when_openai_selected(self, mock_opts):
        """Selecting OpenAI should hide all provider-specific fields."""
        openai_model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        mock_opts.return_value = openai_model
        component = self._make_component()
        build_config = self._get_build_config(component)

        updated = component.update_build_config(build_config, openai_model, field_name="model")

        assert updated["base_url_ibm_watsonx"]["show"] is False
        assert updated["project_id"]["show"] is False
        assert "ollama_base_url" not in updated

    @patch("lfx.components.langchain_utilities.tool_calling.get_language_model_options")
    def test_hides_all_provider_fields_with_no_model_selected(self, mock_opts):
        """With no model selected, all provider-specific fields should be hidden."""
        mock_opts.return_value = []
        component = self._make_component()
        build_config = self._get_build_config(component)

        updated = component.update_build_config(build_config, "", field_name=None)

        assert updated["base_url_ibm_watsonx"]["show"] is False
        assert updated["project_id"]["show"] is False
        assert "ollama_base_url" not in updated


@pytest.mark.api_key_required
@pytest.mark.usefixtures("client")
async def test_tool_calling_agent_component():
    tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
    input_value = "What is 2 + 2?"
    chat_history = []
    from tests.api_keys import get_openai_api_key

    api_key = get_openai_api_key()
    temperature = 0.1

    # Default OpenAI Model Component
    llm_component = OpenAIModelComponent().set(
        api_key=api_key,
        temperature=temperature,
    )
    llm = llm_component.build_model()

    agent = ToolCallingAgentComponent(_session_id="test")
    agent.set(model=llm, tools=[tools], chat_history=chat_history, input_value=input_value)

    # Chat output
    response = await agent.message_response()
    assert "4" in response.data.get("text")
