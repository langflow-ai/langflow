"""Tests for edge cases in Groq model discovery."""

from unittest.mock import MagicMock, Mock, patch

from lfx.base.models.groq_model_discovery import GroqModelDiscovery


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

        # Mock tool calling - each model goes through chat test then tool test
        # Call order: chat(llama), tool(llama), chat(gemma), tool(gemma)
        call_count = [0]

        def create_mock_client(*_args, **_kwargs):
            mock_client = MagicMock()
            if call_count[0] <= 2:
                # Calls 0-2: chat test for llama (success), tool test for llama (success),
                # chat test for gemma (success)
                mock_client.chat.completions.create.return_value = MagicMock()
            else:
                # Call 3: tool test for gemma (fails)
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
