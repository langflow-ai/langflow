"""Tests for successful Groq model discovery operations."""

from unittest.mock import Mock, patch

from lfx.base.models.groq_model_discovery import GroqModelDiscovery


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
