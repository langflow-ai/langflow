"""Tests for credential resolution in the unified models system.

Bug: Desktop Global Variable OPENAI_API_KEY not injected at runtime.
When api_key parameter is None (Agent component default), get_api_key_for_provider
only attempts DB lookup but has no os.getenv() fallback and no error handling
for ValueError from get_variable(). This causes failures in Desktop where the
env var is not set and the DB lookup is the only path.
"""

from unittest.mock import patch
from uuid import uuid4

from pydantic import SecretStr


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

    @patch("lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping")
    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_unwrap_secretstr_from_db_lookup(self, mock_run, mock_mapping):
        """DB credential variables are SecretStr and must be unwrapped before provider use."""
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        user_id = str(uuid4())
        mock_mapping.return_value = {"OpenAI": "OPENAI_API_KEY"}
        mock_run.return_value = SecretStr("sk-from-database")

        result = get_api_key_for_provider(user_id, "OpenAI", None)

        assert result == "sk-from-database"

    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_unwrap_secretstr_from_explicit_variable_name_lookup(self, mock_run, monkeypatch):
        """Explicit var-name inputs should resolve to the raw secret, not SecretStr's mask."""
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        user_id = str(uuid4())
        mock_run.return_value = SecretStr("sk-from-database")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        result = get_api_key_for_provider(user_id, "OpenAI", "OPENAI_API_KEY")

        assert result == "sk-from-database"

    def test_should_unwrap_secretstr_literal_api_key(self):
        """SecretStr inputs should be passed to provider clients as raw strings."""
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        result = get_api_key_for_provider(None, "OpenAI", SecretStr("sk-direct"))

        assert result == "sk-direct"

    @patch("lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping")
    def test_should_fallback_to_env_when_user_id_is_none(self, mock_mapping, monkeypatch):
        """No user_id (lfx run) must still resolve credentials from os.environ.

        Reproducer: a flow exported with empty api_key + load_from_db=False is executed
        via `lfx run`. user_id is None, api_key is empty/None — the function should still
        try the canonical env var (e.g. WATSONX_APIKEY) before giving up.
        """
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        mock_mapping.return_value = {"IBM WatsonX": "WATSONX_APIKEY"}
        monkeypatch.setenv("WATSONX_APIKEY", "shell-exported-key")

        result = get_api_key_for_provider(None, "IBM WatsonX", None)

        assert result == "shell-exported-key"

    @patch("lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping")
    def test_should_return_none_when_user_id_none_and_env_unset(self, mock_mapping, monkeypatch):
        """No user_id and no env var: nothing to return."""
        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        mock_mapping.return_value = {"IBM WatsonX": "WATSONX_APIKEY"}
        monkeypatch.delenv("WATSONX_APIKEY", raising=False)

        result = get_api_key_for_provider(None, "IBM WatsonX", None)

        assert result is None


class TestExplicitVarNameDbPrecedence:
    """A var-name api_key must resolve the user's DB global variable before env.

    Production bug (P2): .env held an old/revoked OPENAI_API_KEY; the user added
    a valid key as a DB global variable via Settings → Global Variables. A flow's
    Agent (which resolves via load_from_db) used the valid DB key, but the
    Assistant resolved the api_key NAME env-first and authenticated with the
    revoked .env key → 401. Global variables are per-user and encrypted; the
    env read silently bypassed that boundary.
    """

    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_prefer_db_global_variable_over_env_for_explicit_var_name(self, mock_run, monkeypatch):
        user_id = str(uuid4())
        # The user's valid key, stored as a DB global variable (SecretStr).
        mock_run.return_value = SecretStr("sk-db-valid")
        # The stale/revoked key in .env that must NOT win.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-revoked")

        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        result = get_api_key_for_provider(user_id, "OpenAI", "OPENAI_API_KEY")

        assert result == "sk-db-valid"

    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_fallback_to_env_for_var_name_when_db_has_no_value(self, mock_run, monkeypatch):
        # Regression guard: DB-first must still fall back to env when the user
        # has no such DB variable (the value the .env provides is the only one).
        user_id = str(uuid4())
        mock_run.return_value = None
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-fallback")

        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        result = get_api_key_for_provider(user_id, "OpenAI", "OPENAI_API_KEY")

        assert result == "sk-env-fallback"

    def test_should_use_env_for_var_name_when_no_user_id(self, monkeypatch):
        # lfx run (no user): no DB to consult, so the env var is the source.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-only")

        from lfx.base.models.unified_models.credentials import get_api_key_for_provider

        result = get_api_key_for_provider(None, "OpenAI", "OPENAI_API_KEY")

        assert result == "sk-env-only"


class TestGetAllVariablesForProviderDbFallback:
    """Tests for get_all_variables_for_provider when DB lookup yields nothing.

    Bug: Langflow Assistant rejects requests with
    `400 Missing required configuration for OpenAI: OPENAI_API_KEY` even when
    the env var is set, whenever a Variable row exists in the DB but its
    ciphertext was encrypted with a different SECRET_KEY (Fernet
    `InvalidToken`). `decrypt_api_key` swallows the exception and returns "".
    The current `_get_all_variables` only falls back to `os.environ` inside
    its `except` branch, so the empty-string return slips through and the
    required key is missing from the resulting dict.
    """

    @patch("lfx.base.models.unified_models.credentials.get_provider_all_variables")
    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_fallback_to_env_when_db_lookup_returns_empty_for_required_key(
        self, mock_run, mock_provider_vars, monkeypatch
    ):
        """DB returned no usable value for OPENAI_API_KEY → env value must populate result.

        The inner async function returns an empty dict when every
        `variable_service.get_variable(...)` call yields an empty value
        (decryption failed). The outer helper must then consult
        `os.environ` for the missing required keys, exactly mirroring the
        post-async env fallback used by `get_api_key_for_provider`.
        """
        from lfx.base.models.unified_models.credentials import get_all_variables_for_provider

        user_id = str(uuid4())
        mock_provider_vars.return_value = [{"variable_key": "OPENAI_API_KEY"}]
        # Decryption silently failed → inner loop produced an empty dict.
        mock_run.return_value = {}

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env-key")

        result = get_all_variables_for_provider(user_id, "OpenAI")

        assert result == {"OPENAI_API_KEY": "sk-test-env-key"}

    @patch("lfx.base.models.unified_models.credentials.get_provider_all_variables")
    @patch("lfx.base.models.unified_models.credentials.run_until_complete")
    def test_should_fallback_to_env_only_for_keys_missing_from_db(self, mock_run, mock_provider_vars, monkeypatch):
        """Keys returned by DB win; env only fills the gaps for missing keys.

        Guards against an over-broad fix that lets env values overwrite
        successfully decrypted DB values.
        """
        from lfx.base.models.unified_models.credentials import get_all_variables_for_provider

        user_id = str(uuid4())
        mock_provider_vars.return_value = [
            {"variable_key": "OPENAI_API_KEY"},
            {"variable_key": "OPENAI_ORG_ID"},
        ]
        mock_run.return_value = {"OPENAI_API_KEY": "sk-from-db"}

        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-should-not-win")
        monkeypatch.setenv("OPENAI_ORG_ID", "org-from-env")

        result = get_all_variables_for_provider(user_id, "OpenAI")

        assert result == {
            "OPENAI_API_KEY": "sk-from-db",
            "OPENAI_ORG_ID": "org-from-env",
        }
