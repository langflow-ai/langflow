from unittest.mock import MagicMock, patch

import pytest
from lfx.components.azure.azure_openai import AzureChatOpenAIComponent

from tests.base import ComponentTestBaseWithoutClient


class TestAzureChatOpenAIComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return AzureChatOpenAIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "azure_endpoint": "https://example-resource.openai.azure.com/",
            "azure_deployment": "gpt-4o-deployment",
            "model": "gpt-4o",
            "api_key": "test-azure-key",
            "api_version": "2024-06-01",
            "temperature": 1.0,
            "max_tokens": 0,
            "stream": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        component = component_class()
        component.set_attributes(default_kwargs)

        assert component.display_name == "Azure OpenAI"
        assert component.name == "AzureOpenAIModel"
        assert component.azure_endpoint == "https://example-resource.openai.azure.com/"
        assert component.azure_deployment == "gpt-4o-deployment"
        assert component.model == "gpt-4o"

    def test_component_inputs_structure(self, component_class):
        component = component_class()
        input_names = [input_.name for input_ in component.inputs]

        expected_inputs = [
            "azure_endpoint",
            "azure_deployment",
            "model",
            "api_key",
            "api_version",
            "temperature",
            "max_tokens",
        ]
        for input_name in expected_inputs:
            assert input_name in input_names

    def test_model_is_optional_and_advanced(self, component_class):
        component = component_class()
        model_input = next(input_ for input_ in component.inputs if input_.name == "model")

        assert model_input.required is False
        assert model_input.advanced is True

    @patch("lfx.components.azure.azure_openai.AzureChatOpenAI")
    def test_build_model_passes_model(self, mock_azure_chat_openai, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_azure_chat_openai.return_value = mock_instance

        component = component_class()
        component.set_attributes(default_kwargs)
        model = component.build_model()

        mock_azure_chat_openai.assert_called_once_with(
            azure_endpoint="https://example-resource.openai.azure.com/",
            azure_deployment="gpt-4o-deployment",
            model="gpt-4o",
            api_version="2024-06-01",
            api_key="test-azure-key",
            temperature=1.0,
            max_tokens=None,
            streaming=False,
        )
        assert model == mock_instance

    @patch("lfx.components.azure.azure_openai.AzureChatOpenAI")
    def test_build_model_without_model_defaults_to_none(self, mock_azure_chat_openai, component_class, default_kwargs):
        """Omitting Model Name must keep prior behavior: no `model` kwarg value, no regression."""
        default_kwargs = {**default_kwargs, "model": ""}
        mock_instance = MagicMock()
        mock_azure_chat_openai.return_value = mock_instance

        component = component_class()
        component.set_attributes(default_kwargs)
        component.build_model()

        _args, kwargs = mock_azure_chat_openai.call_args
        assert kwargs["model"] is None

    @patch("lfx.components.azure.azure_openai.AzureChatOpenAI")
    def test_build_model_exception_handling(self, mock_azure_chat_openai, component_class, default_kwargs):
        mock_azure_chat_openai.side_effect = ValueError("Invalid API key")

        component = component_class()
        component.set_attributes(default_kwargs)

        with pytest.raises(ValueError, match="Could not connect to AzureOpenAI API"):
            component.build_model()
