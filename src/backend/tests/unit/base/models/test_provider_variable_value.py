"""Tests for lfx.base.models.model_utils.get_provider_variable_value (BUG-01).

Knowledge component retrieval crashed with ``ValueError: OLLAMA_BASE_URL
variable not found`` for any user that hadn't configured Ollama, even when
the KB embedding was Gemini / OpenAI / etc. The crash happened because
``variable_service.get_variable_object`` raises ValueError on miss, and the
raise propagated up through ``fetch_live_ollama_models`` past its
``if not base_url: return []`` guard. These regression tests pin the
contract: missing variables → ``None``, not an exception.

The lookup later gained an environment step behind the database read, so the
tests in this class delete the variable from the environment to assert the
database half on its own. ``TestEnvironmentFallback`` covers the env step.

Lives in its own module (not test_model_utils.py) because that module
``pytest.skip``s at import time on Python 3.14+ when ``langchain-ibm`` is
unavailable — which would silently skip these tests too.
"""

from __future__ import annotations

import pytest
from lfx.base.models import model_utils
from lfx.base.models.model_utils import get_provider_variable_value

_TOUCHED_VARIABLE_KEYS = ("OLLAMA_BASE_URL", "OPENAI_BASE_URL", "NOT_A_PROVIDER_VARIABLE")


@pytest.fixture(autouse=True)
def _isolate_provider_environment(monkeypatch):
    """Start every test from an environment that configures no provider.

    The lookup reads the environment behind the database, and accepts both the
    bare key and its ``LANGFLOW_`` alias, so a developer with Ollama exported
    would otherwise see the database-only assertions fail. Clearing both
    spellings keeps each test's own ``setenv`` the only source of truth.
    """
    for key in _TOUCHED_VARIABLE_KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(f"LANGFLOW_{key}", raising=False)


class TestGetProviderVariableValue:
    def test_returns_none_when_variable_service_raises_value_error(self, monkeypatch) -> None:
        """Missing variable must surface as ``None`` so callers' empty-guard fires."""
        import asyncio

        class _MissingVar:
            async def get_variable(self, **_kwargs):
                msg = "OLLAMA_BASE_URL variable not found."
                raise ValueError(msg)

        class _FakeSessionScope:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *_exc):
                return False

        def fake_run_until_complete(coro):
            return asyncio.new_event_loop().run_until_complete(coro)

        monkeypatch.setattr(model_utils, "session_scope", lambda: _FakeSessionScope())
        monkeypatch.setattr(model_utils, "get_variable_service", lambda: _MissingVar())
        monkeypatch.setattr(model_utils, "run_until_complete", fake_run_until_complete)

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OLLAMA_BASE_URL",
            )
            is None
        )

    def test_returns_none_for_none_user_id(self) -> None:
        assert get_provider_variable_value(None, "OLLAMA_BASE_URL") is None
        assert get_provider_variable_value("None", "OLLAMA_BASE_URL") is None

    def test_returns_value_when_variable_found(self, monkeypatch) -> None:
        """Sanity check: the happy path still returns the stored value as a string."""
        import asyncio

        class _PresentVar:
            async def get_variable(self, **_kwargs):
                return "http://ollama.example:11434"

        class _FakeSessionScope:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *_exc):
                return False

        def fake_run_until_complete(coro):
            return asyncio.new_event_loop().run_until_complete(coro)

        monkeypatch.setattr(model_utils, "session_scope", lambda: _FakeSessionScope())
        monkeypatch.setattr(model_utils, "get_variable_service", lambda: _PresentVar())
        monkeypatch.setattr(model_utils, "run_until_complete", fake_run_until_complete)

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OLLAMA_BASE_URL",
            )
            == "http://ollama.example:11434"
        )


class TestEnvironmentFallback:
    """A provider configured only through the process environment must be discoverable.

    Provider enablement accepts a database variable OR the process environment, and
    model instantiation reads connection config from the environment too. Live model
    discovery read the database alone, so an environment-configured Ollama (the Docker
    /compose shape) reported "connected" while its live fetch returned nothing — the
    assistant then offered the static catalog and defaulted to a model the user had
    never pulled, failing every turn with "model not found".
    """

    @staticmethod
    def _patch_empty_database(monkeypatch) -> None:
        import asyncio

        class _MissingVar:
            async def get_variable(self, **_kwargs):
                msg = "OLLAMA_BASE_URL variable not found."
                raise ValueError(msg)

        class _FakeSessionScope:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *_exc):
                return False

        monkeypatch.setattr(model_utils, "session_scope", lambda: _FakeSessionScope())
        monkeypatch.setattr(model_utils, "get_variable_service", lambda: _MissingVar())
        monkeypatch.setattr(
            model_utils,
            "run_until_complete",
            lambda coro: asyncio.new_event_loop().run_until_complete(coro),
        )

    def test_falls_back_to_environment_when_database_has_no_value(self, monkeypatch) -> None:
        self._patch_empty_database(monkeypatch)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OLLAMA_BASE_URL",
            )
            == "http://ollama:11434"
        )

    def test_database_value_wins_over_environment(self, monkeypatch) -> None:
        import asyncio

        class _PresentVar:
            async def get_variable(self, **_kwargs):
                return "http://from-database:11434"

        class _FakeSessionScope:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *_exc):
                return False

        monkeypatch.setattr(model_utils, "session_scope", lambda: _FakeSessionScope())
        monkeypatch.setattr(model_utils, "get_variable_service", lambda: _PresentVar())
        monkeypatch.setattr(
            model_utils,
            "run_until_complete",
            lambda coro: asyncio.new_event_loop().run_until_complete(coro),
        )
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://from-environment:11434")

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OLLAMA_BASE_URL",
            )
            == "http://from-database:11434"
        )

    def test_environment_is_not_read_when_request_disables_env_fallback(self, monkeypatch) -> None:
        """A flow served under ``no_env_fallback`` stays isolated from process env."""
        from lfx.services.variable.request_scope import activate_no_env_fallback, reset_no_env_fallback

        self._patch_empty_database(monkeypatch)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

        token = activate_no_env_fallback(disabled=True)
        try:
            assert (
                get_provider_variable_value(
                    user_id="00000000-0000-0000-0000-000000000001",
                    variable_key="OLLAMA_BASE_URL",
                )
                is None
            )
        finally:
            reset_no_env_fallback(token)

    def test_no_user_still_falls_back_to_environment(self, monkeypatch) -> None:
        """Discovery without a resolvable user must not lose an env-configured provider."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

        assert get_provider_variable_value(None, "OLLAMA_BASE_URL") == "http://ollama:11434"

    def test_optional_variable_is_not_read_from_environment(self, monkeypatch) -> None:
        """Only required variables fall back to env, so optional switches stay opt-in.

        ``OPENAI_BASE_URL`` is optional: setting it flips OpenAI to a compatible
        endpoint whose raw ``/models`` listing (whisper, tts, embeddings) would
        replace the curated chat catalog. Enablement never consults it, so
        discovery must not either.
        """
        self._patch_empty_database(monkeypatch)
        monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OPENAI_BASE_URL",
            )
            is None
        )

    def test_optional_variable_still_resolves_from_the_database(self, monkeypatch) -> None:
        """Narrowing the env fallback must not touch an explicitly stored value."""
        import asyncio

        class _PresentVar:
            async def get_variable(self, **_kwargs):
                return "https://proxy.example/v1"

        class _FakeSessionScope:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *_exc):
                return False

        monkeypatch.setattr(model_utils, "session_scope", lambda: _FakeSessionScope())
        monkeypatch.setattr(model_utils, "get_variable_service", lambda: _PresentVar())
        monkeypatch.setattr(
            model_utils,
            "run_until_complete",
            lambda coro: asyncio.new_event_loop().run_until_complete(coro),
        )

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OPENAI_BASE_URL",
            )
            == "https://proxy.example/v1"
        )

    def test_langflow_prefixed_alias_is_accepted(self, monkeypatch) -> None:
        """Discovery must read the same env shapes ``get_all_variables_for_provider`` does.

        Some .env templates prefix every key with ``LANGFLOW_``. Enablement's
        variable resolution accepts that alias, so a discovery helper that only
        read the bare name would recreate the connected-but-no-models split one
        env-name shape over.
        """
        self._patch_empty_database(monkeypatch)
        monkeypatch.setenv("LANGFLOW_OLLAMA_BASE_URL", "http://ollama:11434")

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OLLAMA_BASE_URL",
            )
            == "http://ollama:11434"
        )

    def test_bare_name_wins_over_the_prefixed_alias(self, monkeypatch) -> None:
        self._patch_empty_database(monkeypatch)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://bare:11434")
        monkeypatch.setenv("LANGFLOW_OLLAMA_BASE_URL", "http://prefixed:11434")

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OLLAMA_BASE_URL",
            )
            == "http://bare:11434"
        )

    def test_whitespace_only_environment_value_counts_as_absent(self, monkeypatch) -> None:
        """A blank value must not pass the caller's ``if not base_url`` guard."""
        self._patch_empty_database(monkeypatch)
        monkeypatch.setenv("OLLAMA_BASE_URL", "   ")

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="OLLAMA_BASE_URL",
            )
            is None
        )

    def test_unrecognized_variable_is_not_read_from_environment(self, monkeypatch) -> None:
        self._patch_empty_database(monkeypatch)
        monkeypatch.setenv("NOT_A_PROVIDER_VARIABLE", "value")

        assert (
            get_provider_variable_value(
                user_id="00000000-0000-0000-0000-000000000001",
                variable_key="NOT_A_PROVIDER_VARIABLE",
            )
            is None
        )
