"""Unit tests for IBM watsonx.ai component."""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from lfx.schema.dotdict import dotdict

# Mock the langchain_ibm module before importing the component
sys.modules["langchain_ibm"] = MagicMock()


# Create a mock SecretStr class
class MockSecretStr:
    """Mock SecretStr for testing."""

    def __init__(self, value):
        self._value = value

    def get_secret_value(self):
        return self._value


class TestWatsonxAIComponent:
    """Test suite for WatsonxAIComponent."""

    @pytest.fixture
    def wx_component(self):
        """Create a WatsonxAIComponent instance for testing."""
        from lfx.components.ibm.watsonx import WatsonxAIComponent

        return WatsonxAIComponent()

    @pytest.fixture
    def mock_response(self):
        """Create a mock response for API calls."""
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "resources": [
                {"model_id": "ibm/granite-3-2b-instruct"},
                {"model_id": "ibm/granite-3-8b-instruct"},
                {"model_id": "meta-llama/llama-3-70b-instruct"},
            ]
        }
        mock_resp.raise_for_status = Mock()
        return mock_resp

    def test_component_attributes(self, wx_component):
        """Test that component has correct attributes."""
        assert wx_component.display_name == "IBM watsonx.ai"
        assert wx_component.description == "Generate text using IBM watsonx.ai foundation models."
        assert wx_component.icon == "WatsonxAI"
        assert wx_component.name == "IBMwatsonxModel"
        assert wx_component.beta is False

    def test_default_models(self):
        """Test that default models are defined."""
        from lfx.components.ibm.watsonx import WatsonxAIComponent

        assert len(WatsonxAIComponent._default_models) == 3
        assert "ibm/granite-3-2b-instruct" in WatsonxAIComponent._default_models
        assert "ibm/granite-3-8b-instruct" in WatsonxAIComponent._default_models
        assert "ibm/granite-13b-instruct-v2" in WatsonxAIComponent._default_models

    def test_urls_defined(self):
        """Test that API URLs are defined."""
        from lfx.components.ibm.watsonx import WatsonxAIComponent

        assert len(WatsonxAIComponent._urls) > 0
        assert "https://us-south.ml.cloud.ibm.com" in WatsonxAIComponent._urls
        assert "https://eu-de.ml.cloud.ibm.com" in WatsonxAIComponent._urls

    def test_inputs_defined(self, wx_component):
        """Test that all required inputs are defined."""
        input_names = [inp.name for inp in wx_component.inputs]

        # Check for required inputs
        assert "base_url" in input_names
        assert "project_id" in input_names
        assert "space_id" in input_names
        assert "api_key" in input_names
        assert "model_name" in input_names
        assert "max_tokens" in input_names
        assert "temperature" in input_names
        assert "top_p" in input_names
        assert "stream" in input_names

    @patch("lfx.base.models.model_utils.requests.get")
    def test_fetch_models_success(self, mock_get, mock_response):
        """Test successful model fetching from API."""
        from lfx.components.ibm.watsonx import WatsonxAIComponent

        mock_get.return_value = mock_response

        models = WatsonxAIComponent.fetch_models("https://us-south.ml.cloud.ibm.com")

        assert len(models) == 3
        assert "ibm/granite-3-2b-instruct" in models
        assert "ibm/granite-3-8b-instruct" in models
        assert "meta-llama/llama-3-70b-instruct" in models

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "https://us-south.ml.cloud.ibm.com/ml/v1/foundation_model_specs" in call_args[0]

    @patch("lfx.base.models.model_utils.requests.get")
    def test_fetch_models_api_error(self, mock_get):
        """Test that default models are returned on API error."""
        from lfx.components.ibm.watsonx import WatsonxAIComponent

        mock_get.side_effect = Exception("API Error")

        models = WatsonxAIComponent.fetch_models("https://us-south.ml.cloud.ibm.com")

        # Should return default models on error
        assert models == WatsonxAIComponent._default_models

    @patch("lfx.base.models.model_utils.requests.get")
    def test_fetch_models_timeout(self, mock_get):
        """Test that default models are returned on timeout."""
        from lfx.components.ibm.watsonx import WatsonxAIComponent

        mock_get.side_effect = TimeoutError("Request timeout")

        models = WatsonxAIComponent.fetch_models("https://us-south.ml.cloud.ibm.com")

        assert models == WatsonxAIComponent._default_models

    @patch("lfx.components.ibm.watsonx.WatsonxAIComponent.fetch_models")
    def test_update_build_config_base_url(self, mock_fetch, wx_component):
        """Test update_build_config when base_url changes."""
        mock_fetch.return_value = ["model1", "model2", "model3"]

        build_config = dotdict({"model_name": {"options": [], "value": None}})

        result = wx_component.update_build_config(
            build_config, field_value="https://us-south.ml.cloud.ibm.com", field_name="base_url"
        )

        assert result["model_name"]["options"] == ["model1", "model2", "model3"]
        assert result["model_name"]["value"] == "model1"
        mock_fetch.assert_called_once_with(base_url="https://us-south.ml.cloud.ibm.com")

    @patch("lfx.components.ibm.watsonx.WatsonxAIComponent.fetch_models")
    def test_update_build_config_base_url_preserves_valid_model(self, mock_fetch, wx_component):
        """Test that valid model selection is preserved when updating base_url."""
        mock_fetch.return_value = ["model1", "model2", "model3"]

        build_config = dotdict({"model_name": {"options": ["model1"], "value": "model2"}})

        result = wx_component.update_build_config(
            build_config, field_value="https://us-south.ml.cloud.ibm.com", field_name="base_url"
        )

        # model2 is in the new list, so it should be preserved
        assert result["model_name"]["value"] == "model2"

    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    def test_build_model_with_project_id(self, mock_chatwatsonx, wx_component):
        """Test building model with ProjectID container scope."""
        wx_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = "test-project-id"
        wx_component.space_id = None
        wx_component.model_name = "ibm/granite-3-8b-instruct"
        wx_component.stream = False
        wx_component.max_tokens = 1000
        wx_component.temperature = 0.7
        wx_component.top_p = 0.9
        wx_component.frequency_penalty = 0.5
        wx_component.presence_penalty = 0.3
        wx_component.seed = 8
        wx_component.stop_sequence = None
        wx_component.logprobs = True
        wx_component.top_logprobs = 3
        wx_component.logit_bias = None

        wx_component.build_model()

        mock_chatwatsonx.assert_called_once()
        call_kwargs = mock_chatwatsonx.call_args[1]

        assert call_kwargs["apikey"] == "test-api-key"  # pragma: allowlist secret
        assert call_kwargs["url"] == "https://us-south.ml.cloud.ibm.com"
        assert call_kwargs["project_id"] == "test-project-id"
        assert call_kwargs["space_id"] is None
        assert call_kwargs["model_id"] == "ibm/granite-3-8b-instruct"
        assert call_kwargs["streaming"] is False

    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    def test_build_model_with_space_id(self, mock_chatwatsonx, wx_component):
        """Test building model with SpaceID container scope."""
        wx_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = None
        wx_component.space_id = "test-space-id"
        wx_component.model_name = "ibm/granite-3-8b-instruct"
        wx_component.stream = True
        wx_component.max_tokens = 2000
        wx_component.temperature = 0.5
        wx_component.top_p = 0.95
        wx_component.frequency_penalty = 0.0
        wx_component.presence_penalty = 0.0
        wx_component.seed = 42
        wx_component.stop_sequence = "END"
        wx_component.logprobs = False
        wx_component.top_logprobs = 5
        wx_component.logit_bias = None

        wx_component.build_model()

        mock_chatwatsonx.assert_called_once()
        call_kwargs = mock_chatwatsonx.call_args[1]

        assert call_kwargs["apikey"] == "test-api-key"  # pragma: allowlist secret
        assert call_kwargs["url"] == "https://us-south.ml.cloud.ibm.com"
        assert call_kwargs["project_id"] is None
        assert call_kwargs["space_id"] == "test-space-id"
        assert call_kwargs["model_id"] == "ibm/granite-3-8b-instruct"
        assert call_kwargs["streaming"] is True
        assert call_kwargs["params"]["stop"] == ["END"]

    @patch("lfx.components.ibm.watsonx.SecretStr", MockSecretStr)
    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    def test_build_model_with_secret_str_api_key(self, mock_chatwatsonx, wx_component):
        """Test that SecretStr API key is properly converted to string."""
        wx_component.api_key = MockSecretStr("secret-api-key")
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = "test-project-id"
        wx_component.space_id = None
        wx_component.model_name = "ibm/granite-3-8b-instruct"
        wx_component.stream = False
        wx_component.max_tokens = 1000
        wx_component.temperature = 0.7
        wx_component.top_p = 0.9
        wx_component.frequency_penalty = 0.5
        wx_component.presence_penalty = 0.3
        wx_component.seed = 8
        wx_component.stop_sequence = None
        wx_component.logprobs = True
        wx_component.top_logprobs = 3
        wx_component.logit_bias = None

        wx_component.build_model()

        call_kwargs = mock_chatwatsonx.call_args[1]
        assert call_kwargs["apikey"] == "secret-api-key"  # pragma: allowlist secret
        assert isinstance(call_kwargs["apikey"], str)

    @patch("lfx.components.ibm.watsonx.WatsonxAIComponent.fetch_models")
    @patch("lfx.components.ibm.watsonx.logger")
    def test_update_build_config_base_url_with_exception(self, mock_logger, mock_fetch, wx_component):
        """Test update_build_config handles exceptions when fetching models."""
        mock_fetch.side_effect = Exception("Network error")

        build_config = dotdict({"model_name": {"options": ["old_model"], "value": "old_model"}})

        result = wx_component.update_build_config(
            build_config, field_value="https://us-south.ml.cloud.ibm.com", field_name="base_url"
        )

        # Should log the exception but not crash
        mock_logger.exception.assert_called_once_with("Error updating model options.")
        # Original config should be preserved
        assert result["model_name"]["options"] == ["old_model"]
        assert result["model_name"]["value"] == "old_model"

    @patch("lfx.components.ibm.watsonx.WatsonxAIComponent.fetch_models")
    def test_update_build_config_base_url_empty_models_list(self, mock_fetch, wx_component):
        """Test update_build_config when fetch_models returns empty list."""
        mock_fetch.return_value = []

        build_config = dotdict({"model_name": {"options": ["old_model"], "value": "old_model"}})

        result = wx_component.update_build_config(
            build_config, field_value="https://us-south.ml.cloud.ibm.com", field_name="base_url"
        )

        assert result["model_name"]["options"] == []
        assert result["model_name"]["value"] is None

    @patch("lfx.components.ibm.watsonx.WatsonxAIComponent.fetch_models")
    def test_update_build_config_base_url_resets_invalid_model(self, mock_fetch, wx_component):
        """Test that invalid model value is reset when base_url changes."""
        mock_fetch.return_value = ["model1", "model2"]

        build_config = dotdict({"model_name": {"options": ["old_model"], "value": "old_model"}})

        result = wx_component.update_build_config(
            build_config, field_value="https://us-south.ml.cloud.ibm.com", field_name="base_url"
        )

        # old_model is not in new list, so should be reset to first model
        assert result["model_name"]["value"] == "model1"

    def test_update_build_config_base_url_empty_value(self, wx_component):
        """Test update_build_config with empty base_url value."""
        build_config = dotdict({"model_name": {"options": ["model1"], "value": "model1"}})

        result = wx_component.update_build_config(build_config, field_value="", field_name="base_url")

        # Should not update when field_value is empty
        assert result["model_name"]["options"] == ["model1"]
        assert result["model_name"]["value"] == "model1"

    def test_update_build_config_base_url_none_value(self, wx_component):
        """Test update_build_config with None base_url value."""
        build_config = dotdict({"model_name": {"options": ["model1"], "value": "model1"}})

        result = wx_component.update_build_config(build_config, field_value=None, field_name="base_url")

        # Should not update when field_value is None
        assert result["model_name"]["options"] == ["model1"]
        assert result["model_name"]["value"] == "model1"

    def test_update_build_config_unrelated_field(self, wx_component):
        """Test update_build_config with unrelated field name."""
        build_config = dotdict(
            {
                "model_name": {"options": ["model1"], "value": "model1"},
                "space_id": {"advanced": True, "required": False, "value": None},
                "project_id": {"advanced": True, "required": False, "value": None},
            }
        )

        result = wx_component.update_build_config(build_config, field_value="some_value", field_name="unrelated_field")

        # Should return config unchanged
        assert result["model_name"]["options"] == ["model1"]
        assert result["model_name"]["value"] == "model1"
        assert result["space_id"]["advanced"] is True
        assert result["project_id"]["advanced"] is True

    def test_update_build_config_none_field_name(self, wx_component):
        """Test update_build_config with None field_name."""
        build_config = dotdict(
            {
                "model_name": {"options": ["model1"], "value": "model1"},
                "space_id": {"advanced": True, "required": False, "value": None},
                "project_id": {"advanced": True, "required": False, "value": None},
            }
        )

        result = wx_component.update_build_config(build_config, field_value="some_value", field_name=None)

        # Should return config unchanged
        assert result["model_name"]["options"] == ["model1"]
        assert result["model_name"]["value"] == "model1"

    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    def test_build_model_with_logit_bias_json(self, mock_chatwatsonx, wx_component):
        """Test building model with logit_bias as JSON string."""
        wx_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = "test-project-id"
        wx_component.space_id = None
        wx_component.model_name = "ibm/granite-3-8b-instruct"
        wx_component.logprobs = True
        wx_component.top_logprobs = 3
        wx_component.logit_bias = '{"1003": -100, "1004": 100}'

        wx_component.build_model()

        call_kwargs = mock_chatwatsonx.call_args[1]
        assert call_kwargs["params"]["logit_bias"] == {"1003": -100, "1004": 100}

    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    @patch("lfx.components.ibm.watsonx.logger")
    def test_build_model_with_invalid_logit_bias_json(self, mock_logger, mock_chatwatsonx, wx_component):
        """Test that invalid logit_bias JSON uses default value."""
        wx_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = "test-project-id"
        wx_component.space_id = None
        wx_component.model_name = "ibm/granite-3-8b-instruct"
        wx_component.logprobs = True
        wx_component.top_logprobs = 3
        wx_component.logit_bias = "invalid json"

        wx_component.build_model()

        call_kwargs = mock_chatwatsonx.call_args[1]
        assert call_kwargs["params"]["logit_bias"] == {"1003": -100, "1004": -100}
        mock_logger.warning.assert_called_once()

    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    def test_build_model_params_structure(self, mock_chatwatsonx, wx_component):
        """Test that model params are structured correctly."""
        wx_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = "test-project-id"
        wx_component.space_id = None
        wx_component.model_name = "ibm/granite-3-8b-instruct"
        wx_component.stream = False
        wx_component.max_tokens = 1500
        wx_component.temperature = 0.8
        wx_component.top_p = 0.85
        wx_component.frequency_penalty = 0.6
        wx_component.presence_penalty = 0.4
        wx_component.seed = 123
        wx_component.stop_sequence = "STOP"
        wx_component.logprobs = True
        wx_component.top_logprobs = 10
        wx_component.logit_bias = None

        wx_component.build_model()

        call_kwargs = mock_chatwatsonx.call_args[1]
        params = call_kwargs["params"]

        assert params["max_tokens"] == 1500
        assert params["temperature"] == 0.8
        assert params["top_p"] == 0.85
        assert params["frequency_penalty"] == 0.6
        assert params["presence_penalty"] == 0.4
        assert params["seed"] == 123
        assert params["stop"] == ["STOP"]
        assert params["n"] == 1
        assert params["logprobs"] is True
        assert params["top_logprobs"] == 10
        assert params["time_limit"] == 600000
        assert params["logit_bias"] is None

    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    def test_build_model_with_both_project_and_space_id_raises_error(self, mock_chatwatsonx, wx_component):
        """Test that providing both project_id and space_id raises ValueError."""
        wx_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = "test-project-id"
        wx_component.space_id = "test-space-id"
        wx_component.model_name = "ibm/granite-3-8b-instruct"

        with pytest.raises(ValueError, match="Exactly one of Project_ID or Space_ID must be selected"):
            wx_component.build_model()

        # Ensure ChatWatsonx was not called
        mock_chatwatsonx.assert_not_called()

    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    def test_build_model_with_neither_project_nor_space_id_raises_error(self, mock_chatwatsonx, wx_component):
        """Test that providing neither project_id nor space_id raises ValueError."""
        wx_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = None
        wx_component.space_id = None
        wx_component.model_name = "ibm/granite-3-8b-instruct"

        with pytest.raises(ValueError, match="Exactly one of Project_ID or Space_ID must be selected"):
            wx_component.build_model()

        # Ensure ChatWatsonx was not called
        mock_chatwatsonx.assert_not_called()

    @patch("lfx.components.ibm.watsonx.ChatWatsonx")
    def test_build_model_with_empty_string_project_and_space_id_raises_error(self, mock_chatwatsonx, wx_component):
        """Test that providing empty strings for both project_id and space_id raises ValueError."""
        wx_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_component.base_url = "https://us-south.ml.cloud.ibm.com"
        wx_component.project_id = ""
        wx_component.space_id = ""
        wx_component.model_name = "ibm/granite-3-8b-instruct"

        with pytest.raises(ValueError, match="Exactly one of Project_ID or Space_ID must be selected"):
            wx_component.build_model()

        # Ensure ChatWatsonx was not called
        mock_chatwatsonx.assert_not_called()
