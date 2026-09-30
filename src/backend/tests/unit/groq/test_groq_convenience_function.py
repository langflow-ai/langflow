"""Tests for the get_groq_models() convenience function."""

from unittest.mock import patch

from lfx.base.models.groq_model_discovery import GroqModelDiscovery, get_groq_models


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
