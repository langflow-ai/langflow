"""Tests for credential resolution in the unified models system.

Bug: Desktop Global Variable OPENAI_API_KEY not injected at runtime.
When api_key parameter is None (Agent component default), get_api_key_for_provider
only attempts DB lookup but has no os.getenv() fallback and no error handling
for ValueError from get_variable(). This causes failures in Desktop where the
env var is not set and the DB lookup is the only path.
"""

from unittest.mock import patch
from uuid import uuid4


class TestGetApiKeyForProviderDbFallback:
    """Tests for get_api_key_for_provider when api_key param is None (second path)."""

    @patch("lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping")
    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_fallback_to_env_when_db_lookup_raises_value_error(self, mock_run, mock_mapping, monkeypatch):
        """When variable_service.get_variable raises ValueError (variable not found in DB).

        get_api_key_for_provider should fall back to os.getenv() instead of returning None.
        """
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        user_id = str(uuid4())
        mock_mapping.return_value = {"OpenAI": "OPENAI_API_KEY"}
        mock_run.side_effect = ValueError("OPENAI_API_KEY variable not found.")

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env-key")

        result = get_api_key_for_provider(user_id, "OpenAI", None)

        assert result == "sk-test-env-key"

    @patch("lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping")
    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_fallback_to_env_when_db_lookup_returns_empty_string(self, mock_run, mock_mapping, monkeypatch):
        """When decryption fails, get_variable returns empty string.

        get_api_key_for_provider should fall back to os.getenv().
        """
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        user_id = str(uuid4())
        mock_mapping.return_value = {"OpenAI": "OPENAI_API_KEY"}
        mock_run.return_value = ""

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env-key")

        result = get_api_key_for_provider(user_id, "OpenAI", None)

        assert result == "sk-test-env-key"

    @patch("lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping")
    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_fallback_to_env_when_variable_service_is_none(self, mock_run, mock_mapping, monkeypatch):
        """When variable_service is None (service not available in thread context).

        get_api_key_for_provider should fall back to os.getenv().
        """
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        user_id = str(uuid4())
        mock_mapping.return_value = {"OpenAI": "OPENAI_API_KEY"}
        mock_run.return_value = None

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env-key")

        result = get_api_key_for_provider(user_id, "OpenAI", None)

        assert result == "sk-test-env-key"

    @patch("lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping")
    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_return_none_when_both_db_and_env_unavailable(self, mock_run, mock_mapping, monkeypatch):
        """When both DB lookup and env var are unavailable, should return None."""
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        user_id = str(uuid4())
        mock_mapping.return_value = {"OpenAI": "OPENAI_API_KEY"}
        mock_run.return_value = None

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        result = get_api_key_for_provider(user_id, "OpenAI", None)

        assert result is None

    @patch("lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping")
    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_return_db_value_when_db_lookup_succeeds(self, mock_run, mock_mapping):
        """When DB lookup succeeds, should return the DB value (no env fallback needed)."""
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        user_id = str(uuid4())
        mock_mapping.return_value = {"OpenAI": "OPENAI_API_KEY"}
        mock_run.return_value = "sk-from-database"

        result = get_api_key_for_provider(user_id, "OpenAI", None)

        assert result == "sk-from-database"
