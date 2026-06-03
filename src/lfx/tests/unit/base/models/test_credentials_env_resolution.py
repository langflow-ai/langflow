"""Bug #5 (PR-12575): LANGFLOW_GOOGLE_API_KEY is not recognized as a Google credential.

A user who prefixes their provider key with ``LANGFLOW_`` (a common .env
convention — Langflow reads its own settings under that prefix) gets the
provider treated as unconfigured: e.g. Gemini never appears in the assistant
model selector even with a valid key, because the credential resolver only read
the bare variable name (``GOOGLE_API_KEY``) from the environment.

These tests use the env-only path (``user_id=None``) so they are deterministic
and need no database.
"""

from __future__ import annotations

from lfx.base.models.unified_models.credentials import get_all_variables_for_provider


class TestLangflowPrefixedProviderKeys:
    def test_should_resolve_google_key_from_langflow_prefixed_env_var(self, monkeypatch):
        # GIVEN only the LANGFLOW_-prefixed variant is set.
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("LANGFLOW_GOOGLE_API_KEY", "AIza-test-key")

        result = get_all_variables_for_provider(None, "Google Generative AI")

        # THEN it resolves under the CANONICAL name so downstream detection
        # (available_model_providers, get_llm) finds it.
        assert result.get("GOOGLE_API_KEY") == "AIza-test-key"

    def test_should_prefer_unprefixed_key_when_both_are_set(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "canonical")
        monkeypatch.setenv("LANGFLOW_GOOGLE_API_KEY", "prefixed")

        result = get_all_variables_for_provider(None, "Google Generative AI")

        # The bare canonical name keeps precedence (no behavior change for it).
        assert result.get("GOOGLE_API_KEY") == "canonical"

    def test_should_still_resolve_unprefixed_key_alone(self, monkeypatch):
        # Regression guard: the existing GOOGLE_API_KEY path must keep working.
        monkeypatch.delenv("LANGFLOW_GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "canonical-only")

        result = get_all_variables_for_provider(None, "Google Generative AI")

        assert result.get("GOOGLE_API_KEY") == "canonical-only"

    def test_should_resolve_openai_key_from_langflow_prefix_too(self, monkeypatch):
        # The alias is provider-agnostic, not a Google special case.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("LANGFLOW_OPENAI_API_KEY", "sk-test")

        result = get_all_variables_for_provider(None, "OpenAI")

        assert result.get("OPENAI_API_KEY") == "sk-test"
