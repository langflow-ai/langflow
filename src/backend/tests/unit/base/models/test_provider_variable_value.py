"""Tests for lfx.base.models.model_utils.get_provider_variable_value (BUG-01).

Knowledge component retrieval crashed with ``ValueError: OLLAMA_BASE_URL
variable not found`` for any user that hadn't configured Ollama, even when
the KB embedding was Gemini / OpenAI / etc. The crash happened because
``variable_service.get_variable_object`` raises ValueError on miss, and the
raise propagated up through ``fetch_live_ollama_models`` past its
``if not base_url: return []`` guard. These regression tests pin the
contract: missing variables → ``None``, not an exception.

Lives in its own module (not test_model_utils.py) because that module
``pytest.skip``s at import time on Python 3.14+ when ``langchain-ibm`` is
unavailable — which would silently skip these tests too.
"""

from __future__ import annotations

from lfx.base.models import model_utils
from lfx.base.models.model_utils import get_provider_variable_value


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
