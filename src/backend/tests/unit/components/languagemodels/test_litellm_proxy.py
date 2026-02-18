from unittest.mock import MagicMock, patch

import pytest
from lfx.components.litellm.litellm_proxy import LiteLLMProxyComponent
from lfx.inputs.inputs import IntInput, SecretStrInput, SliderInput, StrInput

from tests.base import ComponentTestBaseWithoutClient


class TestLiteLLMProxyComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LiteLLMProxyComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_base": "http://litellm:4000/v1",
            "api_key": "sk-test-key",
            "model_name": "gpt-4o",
            "temperature": 0.7,
            "max_tokens": 1000,
            "timeout": 60,
            "max_retries": 2,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_initialization(self, component_class):
        component = component_class()
        assert component.display_name == "LiteLLM Proxy"
        assert component.name == "LiteLLMProxyModel"
        assert component.icon == "GitBranch"

    def test_inputs(self):
        component = LiteLLMProxyComponent()
        inputs = component.inputs
        expected_inputs = {
            "api_base": StrInput,
            "api_key": SecretStrInput,
            "model_name": StrInput,
            "temperature": SliderInput,
            "max_tokens": IntInput,
            "timeout": IntInput,
            "max_retries": IntInput,
        }
        for name, input_type in expected_inputs.items():
            matching = [inp for inp in inputs if isinstance(inp, input_type) and inp.name == name]
            assert matching, f"Missing or incorrect input: {name}"

    def test_build_model(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)

        mock_chat_openai = mocker.patch(
            "lfx.components.litellm.litellm_proxy.ChatOpenAI",
            return_value=MagicMock(),
        )
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            base_url="http://litellm:4000/v1",
            api_key="sk-test-key",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
            timeout=60,
            max_retries=2,
            streaming=False,
        )
        assert model == mock_chat_openai.return_value

    def test_build_model_max_tokens_zero(self, component_class, default_kwargs, mocker):
        default_kwargs["max_tokens"] = 0
        component = component_class(**default_kwargs)

        mock_chat_openai = mocker.patch(
            "lfx.components.litellm.litellm_proxy.ChatOpenAI",
            return_value=MagicMock(),
        )
        component.build_model()

        _args, kwargs = mock_chat_openai.call_args
        assert kwargs["max_tokens"] is None

    def test_get_exception_message_auth_error(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        from openai import AuthenticationError

        error = AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body={"message": "Invalid API key"},
        )
        message = component._get_exception_message(error)
        assert "Authentication failed" in message

    def test_get_exception_message_not_found(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        from openai import NotFoundError

        error = NotFoundError(
            message="Not found",
            response=MagicMock(status_code=404),
            body={"message": "Model not found"},
        )
        message = component._get_exception_message(error)
        assert "gpt-4o" in message
        assert "not found" in message

    def test_get_exception_message_bad_request(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        from openai import BadRequestError

        error = BadRequestError(
            message="Bad request",
            response=MagicMock(status_code=400),
            body={"message": "Context length exceeded"},
        )
        message = component._get_exception_message(error)
        assert message == "Context length exceeded"

    def test_get_exception_message_unknown_exception(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        message = component._get_exception_message(ValueError("something else"))
        assert message is None

    def test_get_exception_message_no_openai_import(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        with patch.dict("sys.modules", {"openai": None}), patch("builtins.__import__", side_effect=ImportError):
            message = component._get_exception_message(Exception("test"))
            assert message is None
