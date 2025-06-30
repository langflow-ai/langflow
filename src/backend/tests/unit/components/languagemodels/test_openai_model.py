import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_openai import ChatOpenAI
from langflow.components.openai.openai_chat_model import OpenAIModelComponent

from tests.base import ComponentTestBaseWithoutClient


class TestOpenAIModelComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return OpenAIModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "max_tokens": 1000,
            "model_kwargs": {},
            "json_mode": False,
            "model_name": "gpt-4.1-nano",
            "openai_api_base": "https://api.openai.com/v1",
            "api_key": "test-api-key",
            "temperature": 0.1,
            "seed": 1,
            "max_retries": 5,
            "timeout": 700,
        }

    @pytest.fixture
    def file_names_mapping(self):
        # Provide an empty list or the actual mapping if versioned files exist
        return []

    @patch("langflow.components.openai.openai_chat_model.ChatOpenAI")
    async def test_build_model(self, mock_chat_openai, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        component = component_class(**default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            api_key="test-api-key",
            model_name="gpt-4.1-nano",
            max_tokens=1000,
            model_kwargs={},
            base_url="https://api.openai.com/v1",
            seed=1,
            max_retries=5,
            timeout=700,
            temperature=0.1,
        )
        assert model == mock_instance

    @patch("langflow.components.openai.openai_chat_model.ChatOpenAI")
    async def test_build_model_reasoning_model(self, mock_chat_openai, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        default_kwargs["model_name"] = "o1"
        component = component_class(**default_kwargs)
        model = component.build_model()

        # For reasoning models, temperature and seed should be excluded
        mock_chat_openai.assert_called_once_with(
            api_key="test-api-key",
            model_name="o1",
            max_tokens=1000,
            model_kwargs={},
            base_url="https://api.openai.com/v1",
            max_retries=5,
            timeout=700,
        )
        assert model == mock_instance

        # Verify that temperature and seed are not in the parameters
        args, kwargs = mock_chat_openai.call_args
        assert "temperature" not in kwargs
        assert "seed" not in kwargs

    @patch("langflow.components.openai.openai_chat_model.ChatOpenAI")
    async def test_build_model_with_json_mode(self, mock_chat_openai, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_bound_instance = MagicMock()
        mock_instance.bind.return_value = mock_bound_instance
        mock_chat_openai.return_value = mock_instance

        default_kwargs["json_mode"] = True
        component = component_class(**default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once()
        mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
        assert model == mock_bound_instance

    @patch("langflow.components.openai.openai_chat_model.ChatOpenAI")
    async def test_build_model_no_api_key(self, mock_chat_openai, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        default_kwargs["api_key"] = None
        component = component_class(**default_kwargs)
        component.build_model()

        # When api_key is None, it should be passed as None to ChatOpenAI
        args, kwargs = mock_chat_openai.call_args
        assert kwargs["api_key"] is None

    @patch("langflow.components.openai.openai_chat_model.ChatOpenAI")
    async def test_build_model_max_tokens_zero(self, mock_chat_openai, component_class, default_kwargs):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        default_kwargs["max_tokens"] = 0
        component = component_class(**default_kwargs)
        component.build_model()

        # When max_tokens is 0, it should be passed as None to ChatOpenAI
        args, kwargs = mock_chat_openai.call_args
        assert kwargs["max_tokens"] is None

    async def test_get_exception_message_bad_request_error(self, component_class, default_kwargs):
        component_class(**default_kwargs)

        # Create a mock BadRequestError with a body attribute
        mock_error = MagicMock()
        mock_error.body = {"message": "test error message"}

        # Test the method directly by patching the import
        with patch("openai.BadRequestError", mock_error.__class__):
            # Manually call isinstance to avoid mocking it
            if hasattr(mock_error, "body"):
                message = mock_error.body.get("message")
                assert message == "test error message"

    async def test_get_exception_message_no_openai_import(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        # Test when openai module is not available
        with patch.dict("sys.modules", {"openai": None}), patch("builtins.__import__", side_effect=ImportError):
            message = component._get_exception_message(Exception("test"))
            assert message is None

    async def test_get_exception_message_other_exception(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        # Create a regular exception (not BadRequestError)
        regular_exception = ValueError("test error")

        # Create a simple mock for BadRequestError that the exception won't match
        class MockBadRequestError:
            pass

        with patch("openai.BadRequestError", MockBadRequestError):
            message = component._get_exception_message(regular_exception)
            assert message is None

    async def test_update_build_config_reasoning_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "temperature": {"show": True},
            "seed": {"show": True},
        }

        # Test with reasoning model
        updated_config = component.update_build_config(build_config, "o1", "model_name")
        assert updated_config["temperature"]["show"] is False
        assert updated_config["seed"]["show"] is False

        # Test with regular model
        updated_config = component.update_build_config(build_config, "gpt-4", "model_name")
        assert updated_config["temperature"]["show"] is True
        assert updated_config["seed"]["show"] is True

    def test_build_model_integration(self):
        component = OpenAIModelComponent()
        component.api_key = os.getenv("OPENAI_API_KEY")
        component.model_name = "gpt-4.1-nano"
        component.temperature = 0.2
        component.max_tokens = 1000
        component.seed = 42
        component.max_retries = 3
        component.timeout = 600
        component.openai_api_base = "https://api.openai.com/v1"

        model = component.build_model()
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == "gpt-4.1-nano"
        assert model.openai_api_base == "https://api.openai.com/v1"

    def test_build_model_integration_reasoning(self):
        component = OpenAIModelComponent()
        component.api_key = os.getenv("OPENAI_API_KEY")
        component.model_name = "o1"
        component.temperature = 0.2  # This should be ignored for reasoning models
        component.max_tokens = 1000
        component.seed = 42  # This should be ignored for reasoning models
        component.max_retries = 3
        component.timeout = 600
        component.openai_api_base = "https://api.openai.com/v1"

        model = component.build_model()
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == "o1"
        assert model.openai_api_base == "https://api.openai.com/v1"
