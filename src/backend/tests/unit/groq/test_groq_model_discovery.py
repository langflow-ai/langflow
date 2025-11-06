"""Comprehensive tests for Groq model discovery system.

Tests cover:
- Success paths: API fetching, caching, tool calling detection
- Error paths: API failures, network errors, invalid responses
- Edge cases: expired cache, corrupted cache, missing API key
"""

import json
from unittest.mock import MagicMock, Mock, patch

from lfx.base.models.groq_model_discovery import GroqModelDiscovery, get_groq_models


class TestGroqModelDiscoverySuccess:
    """Test successful model discovery operations."""

    def test_init_with_api_key(self, mock_api_key):
        """Test initialization with API key."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)
        assert discovery.api_key == mock_api_key
        assert discovery.base_url == "https://api.groq.com"

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        discovery = GroqModelDiscovery()
        assert discovery.api_key is None
        assert discovery.base_url == "https://api.groq.com"

    def test_init_with_custom_base_url(self, mock_api_key):
        """Test initialization with custom base URL."""
        custom_url = "https://custom.groq.com"
        discovery = GroqModelDiscovery(api_key=mock_api_key, base_url=custom_url)
        assert discovery.base_url == custom_url

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    @patch("groq.Groq")
    def test_fetch_available_models_success(
        self, mock_groq, mock_get, mock_api_key, mock_groq_models_response, mock_groq_client_tool_calling_success
    ):
        """Test successfully fetching models from API."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_groq_models_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock tool calling tests
        mock_groq.return_value = mock_groq_client_tool_calling_success()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        models = discovery._fetch_available_models()

        assert isinstance(models, list)
        assert len(models) == 8
        assert "llama-3.1-8b-instant" in models
        assert "whisper-large-v3" in models
        mock_get.assert_called_once()

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    @patch("groq.Groq")
    def test_get_models_categorizes_llm_and_non_llm(
        self,
        mock_groq,
        mock_get,
        mock_api_key,
        mock_groq_models_response,
        mock_groq_client_tool_calling_success,
        temp_cache_dir,
    ):
        """Test that models are correctly categorized as LLM vs non-LLM."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = mock_groq_models_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock tool calling tests to always succeed
        mock_groq.return_value = mock_groq_client_tool_calling_success()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = temp_cache_dir / ".cache" / "test_cache.json"

        models = discovery.get_models(force_refresh=True)

        # LLM models should be in the result
        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models
        assert "mixtral-8x7b-32768" in models
        assert "gemma-7b-it" in models

        # Non-LLM models should be marked as not_supported
        assert models["whisper-large-v3"]["not_supported"] is True
        assert models["distil-whisper-large-v3-en"]["not_supported"] is True
        assert models["meta-llama/llama-guard-4-12b"]["not_supported"] is True
        assert models["meta-llama/llama-prompt-guard-2-86m"]["not_supported"] is True

        # LLM models should have tool_calling field
        assert "tool_calling" in models["llama-3.1-8b-instant"]
        assert "tool_calling" in models["mixtral-8x7b-32768"]

    @patch("groq.Groq")
    def test_tool_calling_detection_success(self, mock_groq, mock_api_key, mock_groq_client_tool_calling_success):
        """Test successful tool calling detection."""
        mock_groq.return_value = mock_groq_client_tool_calling_success()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_tool_calling("llama-3.1-8b-instant")

        assert result is True

    @patch("groq.Groq")
    def test_tool_calling_detection_not_supported(self, mock_groq, mock_api_key, mock_groq_client_tool_calling_failure):
        """Test tool calling detection when model doesn't support tools."""
        mock_groq.return_value = mock_groq_client_tool_calling_failure()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_tool_calling("gemma-7b-it")

        assert result is False

    def test_cache_save_and_load(self, mock_api_key, sample_models_metadata, temp_cache_dir):
        """Test saving and loading cache."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = temp_cache_dir / ".cache" / "test_cache.json"

        # Save cache
        discovery._save_cache(sample_models_metadata)

        # Verify file was created
        assert discovery.CACHE_FILE.exists()

        # Load cache
        loaded = discovery._load_cache()

        assert loaded is not None
        assert len(loaded) == len(sample_models_metadata)
        assert "llama-3.1-8b-instant" in loaded
        assert loaded["llama-3.1-8b-instant"]["tool_calling"] is True

    def test_cache_respects_expiration(self, mock_api_key, mock_expired_cache_file):
        """Test that expired cache returns None."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = mock_expired_cache_file

        loaded = discovery._load_cache()

        assert loaded is None

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    @patch("groq.Groq")
    def test_get_models_uses_cache_when_available(self, mock_groq, mock_get, mock_api_key, mock_cache_file):
        """Test that get_models uses cache when available and not expired."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = mock_cache_file

        models = discovery.get_models(force_refresh=False)

        # Should use cache, not call API
        mock_get.assert_not_called()
        mock_groq.assert_not_called()

        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    @patch("groq.Groq")
    def test_force_refresh_bypasses_cache(
        self,
        mock_groq,
        mock_get,
        mock_api_key,
        mock_groq_models_response,
        mock_groq_client_tool_calling_success,
        mock_cache_file,
    ):
        """Test that force_refresh bypasses cache and fetches fresh data."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = mock_groq_models_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock tool calling
        mock_groq.return_value = mock_groq_client_tool_calling_success()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = mock_cache_file

        models = discovery.get_models(force_refresh=True)

        # Should call API despite cache
        mock_get.assert_called()
        assert len(models) > 0

    def test_provider_name_extraction(self, mock_api_key):
        """Test provider name extraction from model IDs."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)

        # Models with slash notation
        assert discovery._get_provider_name("meta-llama/llama-3.1-8b") == "Meta"
        assert discovery._get_provider_name("openai/gpt-oss-safeguard-20b") == "OpenAI"
        assert discovery._get_provider_name("qwen/qwen3-32b") == "Alibaba Cloud"
        assert discovery._get_provider_name("moonshotai/moonshot-v1") == "Moonshot AI"
        assert discovery._get_provider_name("groq/groq-model") == "Groq"

        # Models with prefixes
        assert discovery._get_provider_name("llama-3.1-8b-instant") == "Meta"
        assert discovery._get_provider_name("llama3-70b-8192") == "Meta"
        assert discovery._get_provider_name("qwen-2.5-32b") == "Alibaba Cloud"
        assert discovery._get_provider_name("allam-1-13b") == "SDAIA"

        # Unknown providers default to Groq
        assert discovery._get_provider_name("unknown-model") == "Groq"

    def test_skip_patterns(self, mock_api_key):
        """Test that SKIP_PATTERNS correctly identify non-LLM models."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)

        skip_models = [
            "whisper-large-v3",
            "whisper-large-v3-turbo",
            "distil-whisper-large-v3-en",
            "playai-tts",
            "playai-tts-arabic",
            "meta-llama/llama-guard-4-12b",
            "meta-llama/llama-prompt-guard-2-86m",
            "openai/gpt-oss-safeguard-20b",
            "mistral-saba-24b",  # safeguard model
        ]

        for model in skip_models:
            should_skip = any(pattern in model.lower() for pattern in discovery.SKIP_PATTERNS)
            assert should_skip, f"Model {model} should be skipped but wasn't"

        # LLM models should not be skipped
        llm_models = ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma-7b-it"]
        for model in llm_models:
            should_skip = any(pattern in model.lower() for pattern in discovery.SKIP_PATTERNS)
            assert not should_skip, f"Model {model} should not be skipped"


class TestGroqModelDiscoveryErrors:
    """Test error handling in model discovery."""

    def test_no_api_key_returns_fallback(self):
        """Test that missing API key returns fallback models."""
        discovery = GroqModelDiscovery(api_key=None)
        models = discovery.get_models(force_refresh=True)

        # Should return minimal fallback list
        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models
        assert len(models) == 2

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    def test_api_connection_error_returns_fallback(self, mock_get, mock_api_key, mock_requests_get_failure):
        """Test that API connection errors return fallback models."""
        mock_get.side_effect = mock_requests_get_failure

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        models = discovery.get_models(force_refresh=True)

        # Should return fallback models
        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    def test_api_timeout_returns_fallback(self, mock_get, mock_api_key, mock_requests_get_timeout):
        """Test that API timeouts return fallback models."""
        mock_get.side_effect = mock_requests_get_timeout

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        models = discovery.get_models(force_refresh=True)

        # Should return fallback models
        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    def test_api_unauthorized_returns_fallback(self, mock_get, mock_api_key, mock_requests_get_unauthorized):
        """Test that unauthorized API requests return fallback models."""
        mock_get.side_effect = mock_requests_get_unauthorized

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        models = discovery.get_models(force_refresh=True)

        # Should return fallback models
        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    def test_invalid_api_response_returns_fallback(self, mock_get, mock_api_key):
        """Test that invalid API response structure returns fallback models."""
        # Mock response with missing 'data' field
        mock_response = Mock()
        mock_response.json.return_value = {"error": "invalid"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        models = discovery.get_models(force_refresh=True)

        # Should return fallback models
        assert "llama-3.1-8b-instant" in models

    def test_corrupted_cache_returns_none(self, mock_api_key, mock_corrupted_cache_file):
        """Test that corrupted cache file returns None."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = mock_corrupted_cache_file

        loaded = discovery._load_cache()

        assert loaded is None

    def test_cache_missing_fields_returns_none(self, mock_api_key, temp_cache_dir):
        """Test that cache with missing required fields returns None."""
        cache_file = temp_cache_dir / ".cache" / "invalid_cache.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Cache missing 'cached_at' field
        cache_data = {"models": {"llama-3.1-8b-instant": {}}}

        with cache_file.open("w") as f:
            json.dump(cache_data, f)

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = cache_file

        loaded = discovery._load_cache()

        assert loaded is None

    def test_cache_save_failure_logs_warning(self, mock_api_key, temp_cache_dir, sample_models_metadata):
        """Test that cache save failures are logged but don't crash."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)
        # Set cache file to a path that can't be written (directory instead of file)
        discovery.CACHE_FILE = temp_cache_dir

        # This should not raise an exception
        discovery._save_cache(sample_models_metadata)

    @patch("groq.Groq")
    def test_tool_calling_import_error_returns_false(self, mock_groq, mock_api_key):
        """Test that ImportError during tool calling test returns False."""
        mock_groq.side_effect = ImportError("groq module not found")

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_tool_calling("test-model")

        assert result is False

    @patch("groq.Groq")
    def test_tool_calling_rate_limit_returns_false(self, mock_groq, mock_api_key, mock_groq_client_rate_limit):
        """Test that rate limit errors return False conservatively."""
        mock_groq.return_value = mock_groq_client_rate_limit()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_tool_calling("test-model")

        assert result is False


class TestGroqModelDiscoveryEdgeCases:
    """Test edge cases in model discovery."""

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    def test_empty_model_list_from_api(self, mock_get, mock_api_key, temp_cache_dir):
        """Test handling of empty model list from API."""
        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = temp_cache_dir / ".cache" / "test_cache.json"

        models = discovery.get_models(force_refresh=True)

        # Should return empty dict (or potentially fallback)
        assert isinstance(models, dict)

    def test_cache_file_not_exists(self, mock_api_key, temp_cache_dir):
        """Test loading cache when file doesn't exist."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = temp_cache_dir / ".cache" / "nonexistent.json"

        loaded = discovery._load_cache()

        assert loaded is None

    def test_cache_directory_created_on_save(self, mock_api_key, temp_cache_dir, sample_models_metadata):
        """Test that cache directory is created if it doesn't exist."""
        cache_file = temp_cache_dir / "new_dir" / ".cache" / "test_cache.json"

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = cache_file

        # Directory shouldn't exist yet
        assert not cache_file.parent.exists()

        # Save cache
        discovery._save_cache(sample_models_metadata)

        # Directory should be created
        assert cache_file.parent.exists()
        assert cache_file.exists()

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    @patch("groq.Groq")
    def test_preview_model_detection(
        self,
        mock_groq,
        mock_get,
        mock_api_key,
        mock_groq_client_tool_calling_success,
        temp_cache_dir,
    ):
        """Test detection of preview models."""
        # Mock API with preview models
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"id": "llama-3.2-1b-preview", "object": "model"},
                {"id": "meta-llama/llama-3.2-90b-preview", "object": "model"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        mock_groq.return_value = mock_groq_client_tool_calling_success()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = temp_cache_dir / ".cache" / "test_cache.json"

        models = discovery.get_models(force_refresh=True)

        # Models with "preview" in name should be marked as preview
        assert models["llama-3.2-1b-preview"]["preview"] is True

        # Models with "/" should be marked as preview
        assert models["meta-llama/llama-3.2-90b-preview"]["preview"] is True

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    @patch("groq.Groq")
    def test_mixed_tool_calling_support(
        self,
        mock_groq,
        mock_get,
        mock_api_key,
        temp_cache_dir,
    ):
        """Test models with mixed tool calling support."""
        # Mock API
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"id": "llama-3.1-8b-instant", "object": "model"},
                {"id": "gemma-7b-it", "object": "model"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock tool calling - first succeeds, second fails
        call_count = [0]

        def create_mock_client(*_args, **_kwargs):
            mock_client = MagicMock()
            if call_count[0] == 0:
                # First call succeeds
                mock_client.chat.completions.create.return_value = MagicMock()
            else:
                # Second call fails with tool error
                mock_client.chat.completions.create.side_effect = ValueError("tool calling not supported")
            call_count[0] += 1
            return mock_client

        mock_groq.side_effect = create_mock_client

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = temp_cache_dir / ".cache" / "test_cache.json"

        models = discovery.get_models(force_refresh=True)

        # First model should support tools
        assert models["llama-3.1-8b-instant"]["tool_calling"] is True

        # Second model should not support tools
        assert models["gemma-7b-it"]["tool_calling"] is False

    def test_fallback_models_structure(self, mock_api_key):
        """Test that fallback models have the correct structure."""
        discovery = GroqModelDiscovery(api_key=mock_api_key)
        fallback = discovery._get_fallback_models()

        assert isinstance(fallback, dict)
        assert len(fallback) == 2

        for metadata in fallback.values():
            assert "name" in metadata
            assert "provider" in metadata
            assert "tool_calling" in metadata
            assert "preview" in metadata
            assert metadata["tool_calling"] is True  # Fallback models should support tools


class TestGetGroqModelsConvenienceFunction:
    """Test the convenience function get_groq_models()."""

    @patch.object(GroqModelDiscovery, "get_models")
    def test_get_groq_models_with_api_key(self, mock_get_models, mock_api_key):
        """Test get_groq_models() function with API key."""
        mock_get_models.return_value = {"llama-3.1-8b-instant": {}}

        models = get_groq_models(api_key=mock_api_key)

        assert "llama-3.1-8b-instant" in models
        mock_get_models.assert_called_once_with(force_refresh=False)

    @patch.object(GroqModelDiscovery, "get_models")
    def test_get_groq_models_without_api_key(self, mock_get_models):
        """Test get_groq_models() function without API key."""
        mock_get_models.return_value = {"llama-3.1-8b-instant": {}}

        models = get_groq_models()

        assert "llama-3.1-8b-instant" in models
        mock_get_models.assert_called_once_with(force_refresh=False)

    @patch.object(GroqModelDiscovery, "get_models")
    def test_get_groq_models_force_refresh(self, mock_get_models, mock_api_key):
        """Test get_groq_models() with force_refresh."""
        mock_get_models.return_value = {"llama-3.1-8b-instant": {}}

        models = get_groq_models(api_key=mock_api_key, force_refresh=True)

        assert "llama-3.1-8b-instant" in models
        mock_get_models.assert_called_once_with(force_refresh=True)
