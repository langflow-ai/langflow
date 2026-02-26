from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx.components.litellm.litellm_proxy import LiteLLMProxyComponent
from lfx.inputs.inputs import IntInput, SecretStrInput, SliderInput, StrInput
from pydantic.v1 import SecretStr

from tests.base import ComponentTestBaseWithoutClient


def _mock_models_response(models=None, status_code=200):
    """Create a mock httpx response for the /models endpoint."""
    if models is None:
        models = [{"id": "gpt-4o"}, {"id": "claude-3-opus"}]
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = {"data": models}
    response.raise_for_status = MagicMock()
    return response


class TestLiteLLMProxyComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LiteLLMProxyComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_base": "http://localhost:4000/v1",
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

    def test_temperature_range_max_is_one(self):
        component = LiteLLMProxyComponent()
        temp_input = next(inp for inp in component.inputs if inp.name == "temperature")
        assert temp_input.range_spec.max == 1

    def test_build_model(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)

        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            return_value=_mock_models_response(),
        )
        mock_chat_openai = mocker.patch(
            "lfx.components.litellm.litellm_proxy.ChatOpenAI",
            return_value=MagicMock(),
        )
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            base_url="http://localhost:4000/v1",
            api_key="sk-test-key",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
            timeout=60,
            max_retries=2,
            streaming=False,
        )
        assert model == mock_chat_openai.return_value

    def test_build_model_secret_str_api_key(self, component_class, default_kwargs, mocker):
        default_kwargs["api_key"] = SecretStr("sk-secret-key")
        component = component_class(**default_kwargs)

        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            return_value=_mock_models_response(),
        )
        mock_chat_openai = mocker.patch(
            "lfx.components.litellm.litellm_proxy.ChatOpenAI",
            return_value=MagicMock(),
        )
        component.build_model()

        _args, kwargs = mock_chat_openai.call_args
        assert kwargs["api_key"] == "sk-secret-key"
        assert not isinstance(kwargs["api_key"], SecretStr)

    def test_build_model_max_tokens_zero(self, component_class, default_kwargs, mocker):
        default_kwargs["max_tokens"] = 0
        component = component_class(**default_kwargs)

        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            return_value=_mock_models_response(),
        )
        mock_chat_openai = mocker.patch(
            "lfx.components.litellm.litellm_proxy.ChatOpenAI",
            return_value=MagicMock(),
        )
        component.build_model()

        _args, kwargs = mock_chat_openai.call_args
        assert kwargs["max_tokens"] is None

    # --- Validation tests ---

    def test_validate_proxy_connection_success(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            return_value=_mock_models_response(),
        )
        # Should not raise
        component._validate_proxy_connection("sk-test-key")

    def test_validate_proxy_connection_auth_failure(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            return_value=_mock_models_response(status_code=401),
        )
        with pytest.raises(ValueError, match="Authentication failed"):
            component._validate_proxy_connection("sk-invalid-key")

    def test_validate_proxy_connection_model_not_found(self, component_class, default_kwargs, mocker):
        default_kwargs["model_name"] = "invalid-model-name"
        component = component_class(**default_kwargs)
        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            return_value=_mock_models_response(models=[{"id": "gpt-4o"}]),
        )
        with pytest.raises(ValueError, match=r"invalid-model-name.*not found"):
            component._validate_proxy_connection("sk-test-key")

    def test_validate_proxy_connection_connect_error(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        )
        with pytest.raises(ValueError, match="Could not connect"):
            component._validate_proxy_connection("sk-test-key")

    def test_validate_proxy_connection_timeout(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            side_effect=httpx.TimeoutException("Timed out"),
        )
        with pytest.raises(ValueError, match="timed out"):
            component._validate_proxy_connection("sk-test-key")

    def test_validate_proxy_connection_empty_models_list(self, component_class, default_kwargs, mocker):
        component = component_class(**default_kwargs)
        mocker.patch(
            "lfx.components.litellm.litellm_proxy.httpx.get",
            return_value=_mock_models_response(models=[]),
        )
        # Empty models list should not raise (proxy may not report models)
        component._validate_proxy_connection("sk-test-key")

    # --- Exception message tests ---

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

        with patch.dict("sys.modules", {"openai": None}):
            message = component._get_exception_message(Exception("test"))
            assert message is None
