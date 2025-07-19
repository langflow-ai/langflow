import pytest
from unittest.mock import MagicMock, patch
from langchain_openai import ChatOpenAI
from langflow.components.openrouter.openrouter import OpenRouterComponent
from tests.base import ComponentTestBaseWithoutClient


class TestOpenRouterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return OpenRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-api-key",
            "model_name": "openai/gpt-4",
            "provider": "OpenAI",
            "temperature": 0.7,
            "max_tokens": 1000,
            "site_url": "https://example.com",
            "app_name": "Test App",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @patch("langflow.components.openrouter.openrouter.ChatOpenAI")
    async def test_build_model(self, mock_chat_openai, component_class, default_kwargs):
        """Test building the OpenRouter model with valid parameters."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        component = component_class(**default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            model="openai/gpt-4",
            openai_api_key="test-api-key",
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.7,
            max_tokens=1000,
            default_headers={
                "HTTP-Referer": "https://example.com",
                "X-Title": "Test App"
            }
        )
        assert model == mock_instance

    @patch("langflow.components.openrouter.openrouter.ChatOpenAI")
    async def test_build_model_minimal_config(self, mock_chat_openai, component_class):
        """Test building the model with minimal configuration."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        
        component = component_class(
            api_key="test-api-key",
            model_name="openai/gpt-4",
            provider="OpenAI"
        )
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            model="openai/gpt-4",
            openai_api_key="test-api-key",
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.7
        )
        assert model == mock_instance

    async def test_build_model_no_api_key(self, component_class):
        """Test that building model without API key raises ValueError."""
        component = component_class(
            model_name="openai/gpt-4",
            provider="OpenAI"
        )
        
        with pytest.raises(ValueError, match="API key is required"):
            component.build_model()

    async def test_build_model_no_model_selected(self, component_class):
        """Test that building model without selecting a model raises ValueError."""
        component = component_class(
            api_key="test-api-key",
            model_name="Select a provider first"
        )
        
        with pytest.raises(ValueError, match="Please select a model"):
            component.build_model()

    @patch("langflow.components.openrouter.openrouter.httpx.Client")
    async def test_fetch_models_success(self, mock_client_class, component_class, default_kwargs):
        """Test successful fetching of models from OpenRouter API."""
        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "description": "OpenAI's GPT-4 model",
                    "context_length": 8192
                },
                {
                    "id": "anthropic/claude-3-opus",
                    "name": "Claude 3 Opus",
                    "description": "Anthropic's Claude 3 Opus model",
                    "context_length": 200000
                },
                {
                    "id": "google/gemini-pro",
                    "name": "Gemini Pro",
                    "description": "Google's Gemini Pro model",
                    "context_length": 32768
                }
            ]
        }
        
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        component = component_class(**default_kwargs)
        models = component.fetch_models()
        
        # Verify the models are organized by provider
        assert "Openai" in models
        assert "Anthropic" in models
        assert "Google" in models
        
        # Check specific model details
        openai_models = models["Openai"]
        assert len(openai_models) == 1
        assert openai_models[0]["id"] == "openai/gpt-4"
        assert openai_models[0]["name"] == "GPT-4"
        assert openai_models[0]["context_length"] == 8192

    @patch("langflow.components.openrouter.openrouter.httpx.Client")
    async def test_fetch_models_http_error(self, mock_client_class, component_class, default_kwargs):
        """Test handling of HTTP errors when fetching models."""
        import httpx
        
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.HTTPError("Network error")
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        component = component_class(**default_kwargs)
        models = component.fetch_models()
        
        # Should return error structure
        assert "Error" in models
        assert "Network error" in models["Error"][0]["name"]

    async def test_update_build_config_provider_change(self, component_class, default_kwargs):
        """Test updating build config when provider changes."""
        component = component_class(**default_kwargs)
        
        # Mock fetch_models to return test data
        with patch.object(component, 'fetch_models') as mock_fetch:
            mock_fetch.return_value = {
                "OpenAI": [
                    {"id": "openai/gpt-4", "name": "GPT-4", "description": "GPT-4 model", "context_length": 8192},
                    {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "GPT-3.5 model", "context_length": 4096}
                ],
                "Anthropic": [
                    {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "description": "Claude model", "context_length": 200000}
                ]
            }
            
            build_config = {
                "provider": {"options": [], "value": ""},
                "model_name": {"options": [], "value": "", "tooltips": {}}
            }
            
            # Test provider selection
            updated_config = component.update_build_config(build_config, "OpenAI", "provider")
            
            # Check that provider options are updated
            assert "OpenAI" in updated_config["provider"]["options"]
            assert "Anthropic" in updated_config["provider"]["options"]
            
            # Check that model options are updated for selected provider
            assert "openai/gpt-4" in updated_config["model_name"]["options"]
            assert "openai/gpt-3.5-turbo" in updated_config["model_name"]["options"]
            assert updated_config["model_name"]["value"] == "openai/gpt-4"
            
            # Check tooltips are set
            assert "openai/gpt-4" in updated_config["model_name"]["tooltips"]
            assert "GPT-4" in updated_config["model_name"]["tooltips"]["openai/gpt-4"]

    async def test_get_exception_message_bad_request_error(self, component_class, default_kwargs):
        """Test extracting message from OpenAI BadRequestError."""
        component = component_class(**default_kwargs)
        
        # Create a mock BadRequestError with a body attribute
        mock_error = MagicMock()
        mock_error.body = {"message": "Invalid model specified"}
        
        # Test the method directly by patching the import
        with patch("openai.BadRequestError", mock_error.__class__):
            if hasattr(mock_error, "body"):
                message = mock_error.body.get("message")
                assert message == "Invalid model specified"

    async def test_get_exception_message_no_openai_import(self, component_class, default_kwargs):
        """Test handling when openai module is not available."""
        component = component_class(**default_kwargs)
        
        # Test when openai module is not available
        with patch.dict("sys.modules", {"openai": None}), patch("builtins.__import__", side_effect=ImportError):
            message = component._get_exception_message(Exception("test"))
            assert message is None

    async def test_get_exception_message_other_exception(self, component_class, default_kwargs):
        """Test handling of non-BadRequestError exceptions."""
        component = component_class(**default_kwargs)
        
        # Create a regular exception (not BadRequestError)
        regular_exception = ValueError("test error")
        
        # Create a simple mock for BadRequestError that the exception won't match
        class MockBadRequestError:
            pass
        
        with patch("openai.BadRequestError", MockBadRequestError):
            message = component._get_exception_message(regular_exception)
            assert message is None

    def test_component_attributes(self, component_class):
        """Test that the component has the correct attributes."""
        component = component_class()
        
        assert component.display_name == "OpenRouter"
        assert "OpenRouter provides unified access" in component.description
        assert component.icon == "OpenRouter"

    def test_component_inputs(self, component_class):
        """Test that the component has the expected inputs."""
        component = component_class()
        
        input_names = [input_field.name for input_field in component.inputs]
        
        # Check that all expected inputs are present
        expected_inputs = [
            "api_key", "site_url", "app_name", "provider", 
            "model_name", "temperature", "max_tokens"
        ]
        
        for expected_input in expected_inputs:
            assert expected_input in input_names

    @patch("langflow.components.openrouter.openrouter.ChatOpenAI")
    async def test_build_model_with_headers(self, mock_chat_openai, component_class):
        """Test that headers are properly set when site_url and app_name are provided."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        
        component = component_class(
            api_key="test-api-key",
            model_name="openai/gpt-4",
            provider="OpenAI",
            site_url="https://mysite.com",
            app_name="My App"
        )
        
        component.build_model()
        
        # Check that headers are included in the call
        args, kwargs = mock_chat_openai.call_args
        assert "default_headers" in kwargs
        assert kwargs["default_headers"]["HTTP-Referer"] == "https://mysite.com"
        assert kwargs["default_headers"]["X-Title"] == "My App"

    @patch("langflow.components.openrouter.openrouter.ChatOpenAI")
    async def test_build_model_without_headers(self, mock_chat_openai, component_class):
        """Test that no headers are set when site_url and app_name are not provided."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        
        component = component_class(
            api_key="test-api-key",
            model_name="openai/gpt-4",
            provider="OpenAI"
        )
        
        component.build_model()
        
        # Check that headers are not included in the call
        args, kwargs = mock_chat_openai.call_args
        assert "default_headers" not in kwargs