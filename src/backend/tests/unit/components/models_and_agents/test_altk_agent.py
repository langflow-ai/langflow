import os
from typing import Any
from uuid import uuid4

import pytest
from langflow.custom import Component
from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.components.agents.altk_agent import ALTKAgentComponent
from lfx.components.tools.calculator import CalculatorToolComponent

from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel

# ALTKAgent supports the following model providers
MODEL_PROVIDERS = ["Anthropic", "OpenAI"]


class TestAgentComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return ALTKAgentComponent

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def component_setup(self, component_class: type[Any], default_kwargs: dict[str, Any]) -> Component:
        component_instance = await super().component_setup(component_class, default_kwargs)
        # Mock _should_process_output method
        component_instance._should_process_output = lambda output: False  # noqa: ARG005
        return component_instance

    @pytest.fixture
    def default_kwargs(self):
        return {
            "_type": "Agent",
            "add_current_date_tool": True,
            "agent_description": "A helpful agent",
            "agent_llm": MockLanguageModel(),
            "handle_parsing_errors": True,
            "input_value": "",
            "max_iterations": 10,
            "system_prompt": "You are a helpful assistant.",
            "tools": [],
            "verbose": True,
            "n_messages": 100,
            "format_instructions": "You are an AI that extracts structured JSON objects from unstructured text.",
            "output_schema": [],
        }

    async def test_build_config_update(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]
        # Test updating build config for OpenAI
        component.set(agent_llm="OpenAI")
        updated_config = await component.update_build_config(build_config, "OpenAI", "agent_llm")
        assert "agent_llm" in updated_config
        assert updated_config["agent_llm"]["value"] == "OpenAI"
        assert isinstance(updated_config["agent_llm"]["options"], list)
        assert len(updated_config["agent_llm"]["options"]) > 0
        assert all(provider in updated_config["agent_llm"]["options"] for provider in MODEL_PROVIDERS)

        # Verify model_name field is populated for OpenAI

        assert "model_name" in updated_config
        model_name_dict = updated_config["model_name"]
        assert isinstance(model_name_dict["options"], list)
        assert len(model_name_dict["options"]) > 0  # OpenAI should have available models
        assert "gpt-4o" in model_name_dict["options"]

        # Test Anthropic
        component.set(agent_llm="Anthropic")
        updated_config = await component.update_build_config(build_config, "Anthropic", "agent_llm")
        assert "agent_llm" in updated_config
        assert updated_config["agent_llm"]["value"] == "Anthropic"
        assert isinstance(updated_config["agent_llm"]["options"], list)
        assert len(updated_config["agent_llm"]["options"]) > 0
        assert all(provider in updated_config["agent_llm"]["options"] for provider in MODEL_PROVIDERS)
        assert "Anthropic" in updated_config["agent_llm"]["options"]
        assert updated_config["agent_llm"]["input_types"] == []
        options = updated_config["model_name"]["options"]
        assert any("sonnet" in option.lower() for option in options), f"Options: {options}"


class TestAgentComponentWithClient(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ALTKAgentComponent

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_component_with_calculator(self):
        # Now you can access the environment variables
        api_key = os.getenv("OPENAI_API_KEY")
        tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
        input_value = "What is 2 + 2?"

        temperature = 0.1

        # Initialize the agent with mocked inputs
        agent = ALTKAgentComponent(
            tools=tools,
            input_value=input_value,
            api_key=api_key,
            model_name="gpt-4o",
            agent_llm="OpenAI",
            temperature=temperature,
            _session_id=str(uuid4()),
            response_processing_size_threshold=1,
        )

        response = await agent.message_response()
        response_text = str(response.data.get("text", ""))
        assert "4" in response_text

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    @pytest.mark.slow
    async def test_agent_component_with_all_openai_models(self):
        # Mock inputs
        api_key = os.getenv("OPENAI_API_KEY")
        input_value = "What is 2 + 2?"

        # Iterate over all OpenAI models
        failed_models = []
        openai_chat_model_names = ["gpt-4", "gpt-4o", "gpt-4o-mini"]
        for model_name in openai_chat_model_names:
            # Initialize the agent with mocked inputs
            tools = [CalculatorToolComponent().build_tool()]
            agent = ALTKAgentComponent(
                tools=tools,
                input_value=input_value,
                api_key=api_key,
                model_name=model_name,
                agent_llm="OpenAI",
                _session_id=str(uuid4()),
                response_processing_size_threshold=1,
                verbose=True,
            )

            response = await agent.message_response()
            response_text = str(response.data.get("text", ""))
            if "4" not in response_text:
                failed_models.append(model_name)
        assert not failed_models, f"The following models failed the test: {failed_models}"

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    @pytest.mark.slow
    async def test_agent_component_with_all_anthropic_models(self):
        # Mock inputs
        api_key = os.getenv("ANTHROPIC_API_KEY")
        input_value = "What is 2 + 2?"

        # Iterate over all Anthropic models
        failed_models = {}

        for model_name in ANTHROPIC_MODELS:
            try:
                # Initialize the agent with mocked inputs
                tools = [CalculatorToolComponent().build_tool()]
                agent = ALTKAgentComponent(
                    tools=tools,
                    input_value=input_value,
                    api_key=api_key,
                    model_name=model_name,
                    agent_llm="Anthropic",
                    _session_id=str(uuid4()),
                    response_processing_size_threshold=1,
                )

                response = await agent.message_response()
                response_text = response.data.get("text", "")

                if "4" not in response_text:
                    failed_models[model_name] = f"Expected '4' in response but got: {response_text}"

            except Exception as e:
                failed_models[model_name] = f"Exception occurred: {e!s}"

        assert not failed_models, "The following models failed the test:\n" + "\n".join(
            f"{model}: {error}" for model, error in failed_models.items()
        )
