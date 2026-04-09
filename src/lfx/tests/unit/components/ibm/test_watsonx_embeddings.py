"""Unit tests for IBM watsonx.ai embeddings component."""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from lfx.schema.dotdict import dotdict

# Mock the required modules before importing the component
sys.modules["langchain_ibm"] = MagicMock()
sys.modules["ibm_watsonx_ai"] = MagicMock()
sys.modules["ibm_watsonx_ai.metanames"] = MagicMock()


# Create a mock SecretStr class
class MockSecretStr:
    """Mock SecretStr for testing."""

    def __init__(self, value):
        self._value = value

    def get_secret_value(self):
        return self._value


class TestWatsonxEmbeddingsComponent:
    """Test suite for WatsonxEmbeddingsComponent."""

    @pytest.fixture
    def wx_embeddings_component(self):
        """Create a WatsonxEmbeddingsComponent instance for testing."""
        # Import here to ensure mocks are in place
        from lfx.components.ibm.watsonx_embeddings import WatsonxEmbeddingsComponent

        return WatsonxEmbeddingsComponent()

    @pytest.fixture
    def mock_response(self):
        """Create a mock response for API calls."""
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "resources": [
                {"model_id": "sentence-transformers/all-minilm-l12-v2"},
                {"model_id": "ibm/slate-125m-english-rtrvr-v2"},
                {"model_id": "ibm/slate-30m-english-rtrvr-v2"},
                {"model_id": "intfloat/multilingual-e5-large"},
            ]
        }
        mock_resp.raise_for_status = Mock()
        return mock_resp

    def test_component_attributes(self, wx_embeddings_component):
        """Test that component has correct attributes."""
        assert wx_embeddings_component.display_name == "IBM watsonx.ai Embeddings"
        assert wx_embeddings_component.description == "Generate embeddings using IBM watsonx.ai models."
        assert wx_embeddings_component.icon == "WatsonxAI"
        assert wx_embeddings_component.name == "WatsonxEmbeddingsComponent"

    def test_default_models(self):
        """Test that default models are defined."""
        from lfx.components.ibm.watsonx_embeddings import WatsonxEmbeddingsComponent

        assert len(WatsonxEmbeddingsComponent._default_models) == 4
        assert "sentence-transformers/all-minilm-l12-v2" in WatsonxEmbeddingsComponent._default_models
        assert "ibm/slate-125m-english-rtrvr-v2" in WatsonxEmbeddingsComponent._default_models
        assert "ibm/slate-30m-english-rtrvr-v2" in WatsonxEmbeddingsComponent._default_models
        assert "intfloat/multilingual-e5-large" in WatsonxEmbeddingsComponent._default_models

    def test_inputs_defined(self, wx_embeddings_component):
        """Test that all required inputs are defined."""
        input_names = [inp.name for inp in wx_embeddings_component.inputs]

        # Check for required inputs
        assert "url" in input_names
        assert "project_id" in input_names
        assert "space_id" in input_names
        assert "api_key" in input_names
        assert "model_name" in input_names
        assert "truncate_input_tokens" in input_names
        assert "input_text" in input_names

    def test_url_options_defined(self, wx_embeddings_component):
        """Test that URL options are defined."""
        url_input = next(inp for inp in wx_embeddings_component.inputs if inp.name == "url")

        assert "https://us-south.ml.cloud.ibm.com" in url_input.options
        assert "https://eu-de.ml.cloud.ibm.com" in url_input.options
        assert "https://eu-gb.ml.cloud.ibm.com" in url_input.options
        assert "https://au-syd.ml.cloud.ibm.com" in url_input.options
        assert "https://jp-tok.ml.cloud.ibm.com" in url_input.options
        assert "https://ca-tor.ml.cloud.ibm.com" in url_input.options
        assert "https://ap-south-1.aws.wxai.ibm.com" in url_input.options

    @patch("lfx.base.models.model_utils.requests.get")
    def test_fetch_models_success(self, mock_get, mock_response):
        """Test successful model fetching from API."""
        from lfx.components.ibm.watsonx_embeddings import WatsonxEmbeddingsComponent

        mock_get.return_value = mock_response

        models = WatsonxEmbeddingsComponent.fetch_models("https://us-south.ml.cloud.ibm.com")

        assert len(models) == 4
        assert "sentence-transformers/all-minilm-l12-v2" in models
        assert "ibm/slate-125m-english-rtrvr-v2" in models
        assert "ibm/slate-30m-english-rtrvr-v2" in models
        assert "intfloat/multilingual-e5-large" in models

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "https://us-south.ml.cloud.ibm.com/ml/v1/foundation_model_specs" in call_args[0]
        assert call_args[1]["params"]["version"] == "2024-09-16"
        assert call_args[1]["params"]["filters"] == "function_embedding,!lifecycle_withdrawn:and"
        assert call_args[1]["timeout"] == 10

    @patch("lfx.base.models.model_utils.requests.get")
    def test_fetch_models_sorted(self, mock_get):
        """Test that fetched models are sorted."""
        from lfx.components.ibm.watsonx_embeddings import WatsonxEmbeddingsComponent

        mock_resp = Mock()
        mock_resp.json.return_value = {
            "resources": [
                {"model_id": "zebra-model"},
                {"model_id": "alpha-model"},
                {"model_id": "beta-model"},
            ]
        }
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        models = WatsonxEmbeddingsComponent.fetch_models("https://us-south.ml.cloud.ibm.com")

        assert models == ["alpha-model", "beta-model", "zebra-model"]

    @patch("lfx.base.models.model_utils.requests.get")
    def test_fetch_models_empty_resources(self, mock_get):
        """Test handling of empty resources in API response."""
        from lfx.components.ibm.watsonx_embeddings import WatsonxEmbeddingsComponent

        mock_resp = Mock()
        mock_resp.json.return_value = {"resources": []}
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        models = WatsonxEmbeddingsComponent.fetch_models("https://us-south.ml.cloud.ibm.com")

        assert models == []

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddingsComponent.fetch_models")
    def test_update_build_config_url(self, mock_fetch, wx_embeddings_component):
        """Test update_build_config when url changes."""
        mock_fetch.return_value = ["model1", "model2", "model3"]

        build_config = dotdict(
            {"url": {"value": "https://us-south.ml.cloud.ibm.com"}, "model_name": {"options": [], "value": "old_model"}}
        )

        result = wx_embeddings_component.update_build_config(
            build_config, field_value="https://us-south.ml.cloud.ibm.com", field_name="url"
        )

        assert result["model_name"]["options"] == ["model1", "model2", "model3"]
        assert result["model_name"]["value"] == "model1"
        mock_fetch.assert_called_once_with(base_url="https://us-south.ml.cloud.ibm.com")

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddingsComponent.fetch_models")
    def test_update_build_config_url_resets_model_on_url_change(self, mock_fetch, wx_embeddings_component):
        """Test that model selection is reset to the first available model when URL changes."""
        mock_fetch.return_value = ["model1", "model2", "model3"]

        build_config = dotdict(
            {
                "url": {"value": "https://us-south.ml.cloud.ibm.com"},
                "model_name": {"options": ["model1"], "value": "model2"},
            }
        )

        result = wx_embeddings_component.update_build_config(
            build_config, field_value="https://us-south.ml.cloud.ibm.com", field_name="url"
        )

        # model2 is in the new list, so value should be reset to first model
        assert result["model_name"]["value"] == "model1"

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddingsComponent.fetch_models")
    @patch("lfx.components.ibm.watsonx_embeddings.logger")
    def test_update_build_config_url_with_exception(self, mock_logger, mock_fetch, wx_embeddings_component):
        """Test update_build_config handles exceptions when fetching models."""
        mock_fetch.side_effect = Exception("Network error")

        build_config = dotdict(
            {
                "url": {"value": "https://us-south.ml.cloud.ibm.com"},
                "model_name": {"options": ["old_model"], "value": "old_model"},
            }
        )

        result = wx_embeddings_component.update_build_config(
            build_config, field_value="https://us-south.ml.cloud.ibm.com", field_name="url"
        )

        # Should log the exception but not crash
        mock_logger.exception.assert_called_once_with("Error updating model options.")
        # Original config should be preserved
        assert result["model_name"]["options"] == ["old_model"]
        assert result["model_name"]["value"] == "old_model"

    def test_update_build_config_url_empty_value(self, wx_embeddings_component):
        """Test update_build_config with empty url value."""
        build_config = dotdict({"url": {"value": ""}, "model_name": {"options": ["model1"], "value": "model1"}})

        result = wx_embeddings_component.update_build_config(build_config, field_value="", field_name="url")

        # Should not update when field_value is empty
        assert result["model_name"]["options"] == ["model1"]
        assert result["model_name"]["value"] == "model1"

    def test_update_build_config_url_none_value(self, wx_embeddings_component):
        """Test update_build_config with None url value."""
        build_config = dotdict({"url": {"value": None}, "model_name": {"options": ["model1"], "value": "model1"}})

        result = wx_embeddings_component.update_build_config(build_config, field_value=None, field_name="url")

        # Should not update when field_value is None
        assert result["model_name"]["options"] == ["model1"]
        assert result["model_name"]["value"] == "model1"

    def test_update_build_config_unrelated_field(self, wx_embeddings_component):
        """Test update_build_config with unrelated field name."""
        build_config = dotdict(
            {
                "url": {"value": "https://us-south.ml.cloud.ibm.com"},
                "model_name": {"options": ["model1"], "value": "model1"},
            }
        )

        result = wx_embeddings_component.update_build_config(
            build_config, field_value="some_value", field_name="unrelated_field"
        )

        # Should return config unchanged
        assert result["model_name"]["options"] == ["model1"]
        assert result["model_name"]["value"] == "model1"

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_project_id(self, mock_watsonx_embeddings, wx_embeddings_component):
        """Test building embeddings with ProjectID container scope."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = "test-project-id"
        wx_embeddings_component.space_id = None
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 200
        wx_embeddings_component.input_text = True

        wx_embeddings_component.build_embeddings()

        mock_watsonx_embeddings.assert_called_once()
        call_kwargs = mock_watsonx_embeddings.call_args[1]

        assert call_kwargs["apikey"] == "test-api-key"  # pragma: allowlist secret
        assert call_kwargs["url"] == "https://us-south.ml.cloud.ibm.com"
        assert call_kwargs["project_id"] == "test-project-id"
        assert call_kwargs["space_id"] is None
        assert call_kwargs["model_id"] == "ibm/slate-125m-english-rtrvr-v2"

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_space_id(self, mock_watsonx_embeddings, wx_embeddings_component):
        """Test building embeddings with SpaceID container scope."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://eu-de.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = None
        wx_embeddings_component.space_id = "test-space-id"
        wx_embeddings_component.model_name = "sentence-transformers/all-minilm-l12-v2"
        wx_embeddings_component.truncate_input_tokens = 300
        wx_embeddings_component.input_text = False

        wx_embeddings_component.build_embeddings()

        mock_watsonx_embeddings.assert_called_once()
        call_kwargs = mock_watsonx_embeddings.call_args[1]

        assert call_kwargs["apikey"] == "test-api-key"  # pragma: allowlist secret
        assert call_kwargs["url"] == "https://eu-de.ml.cloud.ibm.com"
        assert call_kwargs["project_id"] is None
        assert call_kwargs["space_id"] == "test-space-id"
        assert call_kwargs["model_id"] == "sentence-transformers/all-minilm-l12-v2"

    @patch("lfx.components.ibm.watsonx_embeddings.SecretStr", MockSecretStr)
    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_secret_str_api_key(self, mock_watsonx_embeddings, wx_embeddings_component):
        """Test that SecretStr API key is properly converted to string."""
        wx_embeddings_component.api_key = MockSecretStr("secret-api-key")
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = "test-project-id"
        wx_embeddings_component.space_id = None
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 200
        wx_embeddings_component.input_text = True

        wx_embeddings_component.build_embeddings()

        call_kwargs = mock_watsonx_embeddings.call_args[1]
        assert call_kwargs["apikey"] == "secret-api-key"  # pragma: allowlist secret
        assert isinstance(call_kwargs["apikey"], str)

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_params_structure(self, mock_watsonx_embeddings, wx_embeddings_component):
        """Test that embeddings params are structured correctly."""
        from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames

        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = "test-project-id"
        wx_embeddings_component.space_id = None
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 250
        wx_embeddings_component.input_text = False

        wx_embeddings_component.build_embeddings()

        call_kwargs = mock_watsonx_embeddings.call_args[1]
        params = call_kwargs["params"]

        # Verify params structure
        assert EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS in params
        assert params[EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS] == 250
        assert EmbedTextParamsMetaNames.RETURN_OPTIONS in params
        assert params[EmbedTextParamsMetaNames.RETURN_OPTIONS] == {"input_text": False}

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_both_project_and_space_id_raises_error(
        self, mock_watsonx_embeddings, wx_embeddings_component
    ):
        """Test that providing both project_id and space_id raises ValueError."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = "test-project-id"
        wx_embeddings_component.space_id = "test-space-id"
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 200
        wx_embeddings_component.input_text = True

        with pytest.raises(ValueError, match="Exactly one of Project_ID or Space_ID must be selected"):
            wx_embeddings_component.build_embeddings()

        # Ensure WatsonxEmbeddings was not called
        mock_watsonx_embeddings.assert_not_called()

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_neither_project_nor_space_id_raises_error(
        self, mock_watsonx_embeddings, wx_embeddings_component
    ):
        """Test that providing neither project_id nor space_id raises ValueError."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = None
        wx_embeddings_component.space_id = None
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 200
        wx_embeddings_component.input_text = True

        with pytest.raises(ValueError, match="Exactly one of Project_ID or Space_ID must be selected"):
            wx_embeddings_component.build_embeddings()

        # Ensure WatsonxEmbeddings was not called
        mock_watsonx_embeddings.assert_not_called()

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_empty_string_project_and_space_id_raises_error(
        self, mock_watsonx_embeddings, wx_embeddings_component
    ):
        """Test that providing empty strings for both project_id and space_id raises ValueError."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = ""
        wx_embeddings_component.space_id = ""
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 200
        wx_embeddings_component.input_text = True

        with pytest.raises(ValueError, match="Exactly one of Project_ID or Space_ID must be selected"):
            wx_embeddings_component.build_embeddings()

        # Ensure WatsonxEmbeddings was not called
        mock_watsonx_embeddings.assert_not_called()

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_default_truncate_input_tokens(
        self, mock_watsonx_embeddings, wx_embeddings_component
    ):
        """Test building embeddings with default truncate_input_tokens value."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = "test-project-id"
        wx_embeddings_component.space_id = None
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 200  # default value
        wx_embeddings_component.input_text = True

        wx_embeddings_component.build_embeddings()

        call_kwargs = mock_watsonx_embeddings.call_args[1]
        params = call_kwargs["params"]

        from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames

        assert params[EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS] == 200

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_custom_truncate_input_tokens(self, mock_watsonx_embeddings, wx_embeddings_component):
        """Test building embeddings with custom truncate_input_tokens value."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = "test-project-id"
        wx_embeddings_component.space_id = None
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 500
        wx_embeddings_component.input_text = True

        wx_embeddings_component.build_embeddings()

        call_kwargs = mock_watsonx_embeddings.call_args[1]
        params = call_kwargs["params"]

        from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames

        assert params[EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS] == 500

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_input_text_true(self, mock_watsonx_embeddings, wx_embeddings_component):
        """Test building embeddings with input_text set to True."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = "test-project-id"
        wx_embeddings_component.space_id = None
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 200
        wx_embeddings_component.input_text = True

        wx_embeddings_component.build_embeddings()

        call_kwargs = mock_watsonx_embeddings.call_args[1]
        params = call_kwargs["params"]

        from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames

        assert params[EmbedTextParamsMetaNames.RETURN_OPTIONS]["input_text"] is True

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_input_text_false(self, mock_watsonx_embeddings, wx_embeddings_component):
        """Test building embeddings with input_text set to False."""
        wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
        wx_embeddings_component.url = "https://us-south.ml.cloud.ibm.com"
        wx_embeddings_component.project_id = "test-project-id"
        wx_embeddings_component.space_id = None
        wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
        wx_embeddings_component.truncate_input_tokens = 200
        wx_embeddings_component.input_text = False

        wx_embeddings_component.build_embeddings()

        call_kwargs = mock_watsonx_embeddings.call_args[1]
        params = call_kwargs["params"]

        from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames

        assert params[EmbedTextParamsMetaNames.RETURN_OPTIONS]["input_text"] is False

    @patch("lfx.components.ibm.watsonx_embeddings.WatsonxEmbeddings")
    def test_build_embeddings_with_different_urls(self, mock_watsonx_embeddings, wx_embeddings_component):
        """Test building embeddings with different API endpoint URLs."""
        urls = [
            "https://us-south.ml.cloud.ibm.com",
            "https://eu-de.ml.cloud.ibm.com",
            "https://eu-gb.ml.cloud.ibm.com",
            "https://au-syd.ml.cloud.ibm.com",
            "https://jp-tok.ml.cloud.ibm.com",
            "https://ca-tor.ml.cloud.ibm.com",
            "https://ap-south-1.aws.wxai.ibm.com",
        ]

        for url in urls:
            mock_watsonx_embeddings.reset_mock()

            wx_embeddings_component.api_key = "test-api-key"  # pragma: allowlist secret
            wx_embeddings_component.url = url
            wx_embeddings_component.project_id = "test-project-id"
            wx_embeddings_component.space_id = None
            wx_embeddings_component.model_name = "ibm/slate-125m-english-rtrvr-v2"
            wx_embeddings_component.truncate_input_tokens = 200
            wx_embeddings_component.input_text = True

            wx_embeddings_component.build_embeddings()

            call_kwargs = mock_watsonx_embeddings.call_args[1]
            assert call_kwargs["url"] == url
