"""Regression tests for ``no_env_fallback`` in the post-DB-miss provider fallback.

``get_all_variables_for_provider`` has a post-async fallback loop that, after the
database lookup, fills any still-missing provider keys from ``os.environ`` (so a
``SECRET_KEY`` rotation that silently drops decrypted values doesn't leave the
assistant rejecting requests). That loop must honor the request's
``no_env_fallback`` contract — a served flow under ``no_env_fallback`` must stay
isolated from process-wide credentials.

These tests drive the ``user_id``-not-None path (the only one reaching the
post-async fallback) with a forced DB miss by monkeypatching ``run_until_complete``
to return an empty mapping, so no real database is required.
"""

import uuid
from contextlib import asynccontextmanager

import pytest
from lfx.base.models.unified_models import credentials
from lfx.services.variable.request_scope import activate_no_env_fallback, reset_no_env_fallback


def _force_db_miss(monkeypatch):
    """Make the in-function DB lookup return a miss without touching a database."""

    def _fake_run(coro):
        coro.close()  # avoid "coroutine was never awaited" warnings
        return {}

    monkeypatch.setattr(credentials, "run_until_complete", _fake_run)


def test_post_db_miss_fallback_respects_no_env_fallback(monkeypatch):
    """Under no_env_fallback, the post-DB-miss loop must NOT read os.environ."""
    monkeypatch.setenv("OPENAI_API_KEY", "env-secret")  # pragma: allowlist secret
    _force_db_miss(monkeypatch)

    token = activate_no_env_fallback(disabled=True)
    try:
        values = credentials.get_all_variables_for_provider(uuid.uuid4(), "OpenAI")
    finally:
        reset_no_env_fallback(token)

    assert "OPENAI_API_KEY" not in values  # gated: env not read under no_env_fallback


def test_post_db_miss_fallback_uses_env_when_fallback_enabled(monkeypatch):
    """With env fallback enabled (default), the post-DB-miss loop still reads os.environ.

    Guards against regressing the SECRET_KEY-rotation fix this fallback exists for.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "env-secret")  # pragma: allowlist secret
    _force_db_miss(monkeypatch)

    # no_env_fallback NOT active (default) -> env fallback is allowed.
    values = credentials.get_all_variables_for_provider(uuid.uuid4(), "OpenAI")

    assert values.get("OPENAI_API_KEY") == "env-secret"  # pragma: allowlist secret


def test_db_resolution_error_does_not_fall_back_to_process_environment(monkeypatch):
    """Only an actual missing variable may use the process-wide fallback."""

    class BrokenVariableService:
        async def get_variable(self, **_kwargs):
            msg = "credential decryption failed"
            raise ValueError(msg)

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(credentials, "session_scope", fake_session_scope)
    monkeypatch.setattr(credentials, "get_variable_service", BrokenVariableService)
    monkeypatch.setenv("OPENAI_API_KEY", "server-wide-key")  # pragma: allowlist secret

    with pytest.raises(ValueError, match="credential decryption failed"):
        credentials.get_all_variables_for_provider(uuid.uuid4(), "OpenAI")
