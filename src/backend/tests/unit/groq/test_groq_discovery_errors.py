"""Tests for error handling in Groq model discovery."""

import json
import sys
from unittest.mock import Mock, patch

import pytest
from lfx.base.models.groq_model_discovery import GroqModelDiscovery


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

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    def test_import_error_during_chat_test_returns_fallback(self, mock_get, mock_api_key, temp_cache_dir):
        """Test that get_models returns fallback models when groq is not installed.

        Both _test_chat_completion and _test_tool_calling re-raise ImportError when
        the groq package is absent. get_models catches it and falls back to hardcoded
        model metadata instead of crashing.
        """
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"id": "llama-3.1-8b-instant", "object": "model"}]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch.dict(sys.modules, {"groq": None}):
            discovery = GroqModelDiscovery(api_key=mock_api_key)
            discovery.CACHE_FILE = temp_cache_dir / ".cache" / "test_cache.json"
            models = discovery.get_models(force_refresh=True)

        # Should return the hardcoded fallback list, not an empty dict
        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models
        assert len(models) == 2  # exactly the two fallback models

    @patch("groq.Groq")
    def test_tool_calling_import_error_raises(self, mock_groq, mock_api_key):
        """Test that ImportError during tool calling test is re-raised."""
        mock_groq.side_effect = ImportError("groq module not found")

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        with pytest.raises(ImportError):
            discovery._test_tool_calling("test-model")

    @patch("groq.Groq")
    def test_tool_calling_rate_limit_returns_none(self, mock_groq, mock_api_key, mock_groq_client_rate_limit):
        """Test that rate limit errors return None (indeterminate)."""
        mock_groq.return_value = mock_groq_client_rate_limit()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_tool_calling("test-model")

        assert result is None
