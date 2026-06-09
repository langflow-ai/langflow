"""Integration tests for Groq component with dynamic model discovery.

Tests cover:
- Success paths: get_models with/without API key, tool_model_enabled filtering
- Error paths: invalid API key, discovery failures, missing dependencies
- Edge cases: empty results, build config updates
"""

from unittest.mock import patch

import pytest


class TestGroqModelIntegration:
    """Test the GroqModel component integration with dynamic discovery."""

    @pytest.fixture
    def groq_model_instance(self):
        """Create a GroqModel instance for testing."""
        from lfx.components.groq.groq import GroqModel

        return GroqModel()

    def test_groq_model_initialization(self, groq_model_instance):
        """Test GroqModel initializes with correct attributes."""
        assert groq_model_instance.display_name == "Groq"
        assert groq_model_instance.description == "Generate text using Groq."
        assert groq_model_instance.icon == "Groq"
        assert groq_model_instance.name == "GroqModel"

    def test_groq_model_has_required_inputs(self, groq_model_instance):
        """Test that GroqModel has all required inputs."""
        input_names = [inp.name for inp in groq_model_instance.inputs]

        assert "api_key" in input_names
        assert "base_url" in input_names
        assert "max_tokens" in input_names
        assert "temperature" in input_names
        assert "model_name" in input_names
        assert "tool_model_enabled" in input_names

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_with_api_key(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models() with valid API key."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
            "llama-3.3-70b-versatile": {"tool_calling": True, "not_supported": False},
            "gemma-7b-it": {"tool_calling": False, "not_supported": False},
            "whisper-large-v3": {"not_supported": True},
        }

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models()

        # Should exclude not_supported models
        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models
        assert "gemma-7b-it" in models
        assert "whisper-large-v3" not in models

        # Verify get_groq_models was called with api_key
        mock_get_groq_models.assert_called_once_with(api_key=mock_api_key)

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_without_api_key(self, mock_get_groq_models, groq_model_instance):
        """Test get_models() without API key."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
            "llama-3.3-70b-versatile": {"tool_calling": True, "not_supported": False},
        }

        models = groq_model_instance.get_models()

        assert len(models) > 0
        # Verify get_groq_models was called with None
        mock_get_groq_models.assert_called_once_with(api_key=None)

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_with_tool_model_enabled(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models() with tool_model_enabled=True filters correctly."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
            "llama-3.3-70b-versatile": {"tool_calling": True, "not_supported": False},
            "gemma-7b-it": {"tool_calling": False, "not_supported": False},
            "mixtral-8x7b-32768": {"tool_calling": True, "not_supported": False},
        }

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models(tool_model_enabled=True)

        # Should only include tool_calling models
        assert "llama-3.1-8b-instant" in models
        assert "llama-3.3-70b-versatile" in models
        assert "mixtral-8x7b-32768" in models
        assert "gemma-7b-it" not in models

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_with_tool_model_disabled(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models() with tool_model_enabled=False returns all models."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
            "gemma-7b-it": {"tool_calling": False, "not_supported": False},
        }

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models(tool_model_enabled=False)

        # Should include all non-unsupported models
        assert "llama-3.1-8b-instant" in models
        assert "gemma-7b-it" in models

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_error_falls_back_to_constants(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test that get_models() falls back to GROQ_MODELS on error."""
        # Simulate error in get_groq_models
        mock_get_groq_models.side_effect = ValueError("API error")

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models()

        # Should return fallback models from groq_constants.py
        assert isinstance(models, list)
        assert len(models) > 0

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_update_build_config_with_api_key(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test update_build_config updates model list when API key is provided."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
            "llama-3.3-70b-versatile": {"tool_calling": True, "not_supported": False},
        }

        groq_model_instance.api_key = mock_api_key
        groq_model_instance.tool_model_enabled = False

        build_config = {}
        result = groq_model_instance.update_build_config(build_config, mock_api_key, "api_key")

        assert "model_name" in result
        assert "options" in result["model_name"]
        assert "llama-3.1-8b-instant" in result["model_name"]["options"]
        assert "llama-3.3-70b-versatile" in result["model_name"]["options"]
        assert "value" in result["model_name"]

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_update_build_config_with_tool_model_enabled(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test update_build_config filters models when tool_model_enabled changes."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
            "gemma-7b-it": {"tool_calling": False, "not_supported": False},
        }

        groq_model_instance.api_key = mock_api_key
        groq_model_instance.tool_model_enabled = True

        build_config = {}
        result = groq_model_instance.update_build_config(build_config, "true", "tool_model_enabled")

        # When tool_model_enabled is True, should only show tool models
        assert "model_name" in result
        models = result["model_name"]["options"]
        # Note: The actual filtering happens in get_models(), so we need to check that too
        assert len(models) > 0

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_update_build_config_with_model_name(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test update_build_config when model_name field is updated."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
            "llama-3.3-70b-versatile": {"tool_calling": True, "not_supported": False},
        }

        groq_model_instance.api_key = mock_api_key
        groq_model_instance.tool_model_enabled = False

        build_config = {}
        result = groq_model_instance.update_build_config(build_config, "llama-3.1-8b-instant", "model_name")

        assert "model_name" in result
        assert "options" in result["model_name"]

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_update_build_config_with_base_url(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test update_build_config when base_url field is updated."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
        }

        groq_model_instance.api_key = mock_api_key
        groq_model_instance.tool_model_enabled = False

        build_config = {}
        result = groq_model_instance.update_build_config(build_config, "https://custom.groq.com", "base_url")

        assert "model_name" in result

    def test_update_build_config_with_empty_api_key(self, groq_model_instance):
        """Test update_build_config with empty API key doesn't update."""
        groq_model_instance.api_key = ""

        build_config = {}
        result = groq_model_instance.update_build_config(build_config, "", "api_key")

        # Should not update model_name when api_key is empty
        assert result == build_config

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_update_build_config_error_handling(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test update_build_config handles errors gracefully."""
        # Simulate error
        mock_get_groq_models.side_effect = ValueError("API error")

        groq_model_instance.api_key = mock_api_key
        groq_model_instance.tool_model_enabled = False

        build_config = {}
        result = groq_model_instance.update_build_config(build_config, mock_api_key, "api_key")

        # Should still return a build config with fallback models
        assert "model_name" in result
        assert "options" in result["model_name"]

    def test_build_model_success(self, groq_model_instance, mock_api_key):
        """Test build_model creates ChatGroq instance."""
        groq_model_instance.api_key = mock_api_key
        groq_model_instance.model_name = "llama-3.1-8b-instant"
        groq_model_instance.base_url = "https://api.groq.com"
        groq_model_instance.max_tokens = 1000
        groq_model_instance.temperature = 0.7
        groq_model_instance.n = 1
        groq_model_instance.stream = False

        with patch("langchain_groq.ChatGroq") as mock_chat_groq:
            groq_model_instance.build_model()

            mock_chat_groq.assert_called_once()
            call_kwargs = mock_chat_groq.call_args[1]

            assert call_kwargs["model"] == "llama-3.1-8b-instant"
            assert call_kwargs["max_tokens"] == 1000
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["base_url"] == "https://api.groq.com"
            assert call_kwargs["n"] == 1
            assert call_kwargs["streaming"] is False

    def test_build_model_without_langchain_groq(self, groq_model_instance, mock_api_key):
        """Test build_model raises ImportError when langchain-groq is not installed."""
        groq_model_instance.api_key = mock_api_key
        groq_model_instance.model_name = "llama-3.1-8b-instant"

        # Mock the import itself to raise ImportError
        import sys

        with (
            patch.dict(sys.modules, {"langchain_groq": None}),
            pytest.raises(ImportError, match="langchain-groq is not installed"),
        ):
            groq_model_instance.build_model()


class TestGroqModelEdgeCases:
    """Test edge cases in Groq component."""

    @pytest.fixture
    def groq_model_instance(self):
        """Create a GroqModel instance for testing."""
        from lfx.components.groq.groq import GroqModel

        return GroqModel()

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_with_all_models_filtered_out(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models when all models are filtered out by tool_model_enabled."""
        mock_get_groq_models.return_value = {
            "gemma-7b-it": {"tool_calling": False, "not_supported": False},
            "another-model": {"tool_calling": False, "not_supported": False},
        }

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models(tool_model_enabled=True)

        # Should return empty list when all models are filtered
        assert len(models) == 0

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_with_only_unsupported_models(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models when only unsupported models are returned."""
        mock_get_groq_models.return_value = {
            "whisper-large-v3": {"not_supported": True},
            "playai-tts": {"not_supported": True},
        }

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models()

        # Should filter out all not_supported models
        assert len(models) == 0

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_with_mixed_metadata(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models with mixed metadata (some fields missing)."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True},  # Missing not_supported
            "gemma-7b-it": {"not_supported": False},  # Missing tool_calling
            "mixtral-8x7b-32768": {"tool_calling": True, "not_supported": False},  # Complete
        }

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models()

        # Should handle missing fields gracefully
        assert "llama-3.1-8b-instant" in models
        assert "gemma-7b-it" in models
        assert "mixtral-8x7b-32768" in models

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_with_none_tool_model_enabled(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models with tool_model_enabled=None (default)."""
        mock_get_groq_models.return_value = {
            "llama-3.1-8b-instant": {"tool_calling": True, "not_supported": False},
            "gemma-7b-it": {"tool_calling": False, "not_supported": False},
        }

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models(tool_model_enabled=None)

        # Should return all models (not filter by tool_calling)
        assert "llama-3.1-8b-instant" in models
        assert "gemma-7b-it" in models

    def test_update_build_config_with_unrelated_field(self, groq_model_instance, mock_api_key):
        """Test update_build_config with field that doesn't trigger updates."""
        groq_model_instance.api_key = mock_api_key

        build_config = {"existing": "value"}
        result = groq_model_instance.update_build_config(build_config, "0.7", "temperature")

        # Should return unchanged build_config for unrelated fields
        assert result == build_config

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_key_error_falls_back(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models handles KeyError and falls back."""
        mock_get_groq_models.side_effect = KeyError("Missing key")

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models()

        # Should fall back to GROQ_MODELS
        assert isinstance(models, list)

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_type_error_falls_back(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models handles TypeError and falls back."""
        mock_get_groq_models.side_effect = TypeError("Type error")

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models()

        # Should fall back to GROQ_MODELS
        assert isinstance(models, list)

    @patch("lfx.components.groq.groq.get_groq_models")
    def test_get_models_import_error_falls_back(self, mock_get_groq_models, groq_model_instance, mock_api_key):
        """Test get_models handles ImportError and falls back."""
        mock_get_groq_models.side_effect = ImportError("Import error")

        groq_model_instance.api_key = mock_api_key

        models = groq_model_instance.get_models()

        # Should fall back to GROQ_MODELS
        assert isinstance(models, list)

    def test_build_model_with_none_max_tokens(self, groq_model_instance, mock_api_key):
        """Test build_model with max_tokens=None."""
        groq_model_instance.api_key = mock_api_key
        groq_model_instance.model_name = "llama-3.1-8b-instant"
        groq_model_instance.max_tokens = None
        groq_model_instance.temperature = 0.7
        groq_model_instance.base_url = "https://api.groq.com"
        groq_model_instance.n = None
        groq_model_instance.stream = False

        with patch("langchain_groq.ChatGroq") as mock_chat_groq:
            groq_model_instance.build_model()

            call_kwargs = mock_chat_groq.call_args[1]
            assert call_kwargs["max_tokens"] is None
            assert call_kwargs["n"] == 1  # Should default to 1


class TestGroqModelBackwardCompatibility:
    """Test backward compatibility with static GROQ_MODELS."""

    @pytest.fixture
    def groq_model_instance(self):
        """Create a GroqModel instance for testing."""
        from lfx.components.groq.groq import GroqModel

        return GroqModel()

    def test_groq_models_constant_available(self):
        """Test that GROQ_MODELS constant is still available for backward compatibility."""
        from lfx.base.models.groq_constants import GROQ_MODELS

        assert isinstance(GROQ_MODELS, list)
        assert len(GROQ_MODELS) > 0

    def test_fallback_to_groq_models_on_error(self, groq_model_instance, mock_api_key):
        """Test that component falls back to GROQ_MODELS constant on error."""
        from lfx.base.models.groq_constants import GROQ_MODELS

        groq_model_instance.api_key = mock_api_key

        # ValueError is one of the exceptions that's caught and triggers fallback
        with patch("lfx.components.groq.groq.get_groq_models", side_effect=ValueError("API error")):
            models = groq_model_instance.get_models()

            # Should return GROQ_MODELS
            assert models == GROQ_MODELS

    def test_model_name_input_has_default_options(self, groq_model_instance):
        """Test that model_name input has default options from GROQ_MODELS."""
        from lfx.base.models.groq_constants import GROQ_MODELS

        model_name_input = next(inp for inp in groq_model_instance.inputs if inp.name == "model_name")

        assert model_name_input.options == GROQ_MODELS
        assert model_name_input.value == GROQ_MODELS[0]
