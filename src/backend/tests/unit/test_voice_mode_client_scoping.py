"""Regression tests for voice-mode dependency loading and cross-tenant client confusion.

The ElevenLabs client must be built per requesting user (no process-global
singleton), and the voice/TTS config caches must be keyed by the authenticated
user, not just the client-supplied session_id.
"""

import builtins
import importlib
import sys
import types
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import langflow.api.v1.voice_mode as vm
import pytest
from fastapi import HTTPException


def test_voice_mode_module_import_does_not_require_openai(monkeypatch):
    """The server must boot when the optional OpenAI voice SDK is absent."""
    real_import = builtins.__import__

    def import_without_openai(name, *args, **kwargs):
        if name == "openai" or name.startswith("openai."):
            error_message = "No module named 'openai'"
            raise ModuleNotFoundError(error_message, name="openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_openai)
    vm.__dict__.pop("OpenAI", None)

    importlib.reload(vm)


@pytest.mark.asyncio
async def test_get_or_create_elevenlabs_client_is_per_user(monkeypatch):
    """Each user gets an ElevenLabs client built from their OWN key (no shared singleton)."""
    keys = {"user-a": "key-a", "user-b": "key-b"}

    class FakeVariableService:
        async def get_variable(self, *, user_id, name, field, session):  # noqa: ARG002
            return keys[user_id]

    monkeypatch.setattr(vm, "get_variable_service", lambda: FakeVariableService())

    @asynccontextmanager
    async def read_scope():
        yield object()

    monkeypatch.setattr(vm, "session_scope_readonly", read_scope)

    captured: list[str] = []

    def fake_elevenlabs(*, api_key):
        captured.append(api_key)
        return f"client::{api_key}"

    monkeypatch.setattr(vm, "ElevenLabs", fake_elevenlabs)

    client_a = await vm.get_or_create_elevenlabs_client("user-a")
    client_b = await vm.get_or_create_elevenlabs_client("user-b")

    # Built from each user's own key — user-b is NOT served user-a's cached client.
    assert client_a == "client::key-a"
    assert client_b == "client::key-b"
    assert captured == ["key-a", "key-b"]


@pytest.mark.asyncio
async def test_get_or_create_elevenlabs_client_requires_user():
    """No user -> no client (avoids falling back to some other tenant's key)."""
    assert await vm.get_or_create_elevenlabs_client() is None
    assert await vm.get_or_create_elevenlabs_client(None) is None


@pytest.mark.asyncio
async def test_voice_catalog_denial_precedes_credential_and_provider_lookup(monkeypatch):
    """A revoked voice grant reaches neither the variable service nor ElevenLabs."""
    denied_guard = AsyncMock(side_effect=HTTPException(status_code=403, detail="denied"))
    client_lookup = AsyncMock()
    monkeypatch.setattr(vm, "ensure_voice_permission", denied_guard)
    monkeypatch.setattr(vm, "get_or_create_elevenlabs_client", client_lookup)

    with pytest.raises(HTTPException) as exc_info:
        await vm.get_elevenlabs_voice_ids(
            current_user=SimpleNamespace(id="revoked-user"),
            session=object(),
        )

    assert exc_info.value.status_code == 403
    denied_guard.assert_awaited_once()
    client_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_voice_catalog_releases_auth_transaction_before_provider_work(monkeypatch):
    calls = []

    async def allow_voice(*_args, **_kwargs):
        calls.append("authorization")

    async def commit():
        calls.append("release")

    def get_all():
        calls.append("provider")
        return SimpleNamespace(voices=[SimpleNamespace(voice_id="voice-1", name="First")])

    async def lookup(user_id):
        assert user_id == "catalog-user"
        assert calls == ["authorization", "release"]
        calls.append("credential")
        return SimpleNamespace(voices=SimpleNamespace(get_all=get_all))

    monkeypatch.setattr(vm, "ensure_voice_permission", allow_voice)
    monkeypatch.setattr(vm, "get_or_create_elevenlabs_client", lookup)
    result = await vm.get_elevenlabs_voice_ids(
        current_user=SimpleNamespace(id="catalog-user"), session=SimpleNamespace(commit=commit)
    )
    assert result == [{"voice_id": "voice-1", "name": "First"}]
    assert calls == ["authorization", "release", "credential", "provider"]


def test_get_voice_config_scoped_by_user():
    """Same client-supplied session_id but different users must not share a VoiceConfig."""
    vm.voice_config_cache.clear()

    a = vm.get_voice_config("shared-session", "user-a")
    b = vm.get_voice_config("shared-session", "user-b")
    a_again = vm.get_voice_config("shared-session", "user-a")

    assert a is not b
    assert a is a_again  # same (user, session) is still cached


def test_get_tts_config_scoped_by_user(monkeypatch):
    """Same session_id but different users must not share a TTSConfig / OpenAI client."""
    vm.tts_config_cache.clear()
    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = lambda *, api_key: {"api_key": api_key}
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    a = vm.get_tts_config("shared-session", "openai-key-a", "user-a")
    b = vm.get_tts_config("shared-session", "openai-key-b", "user-b")

    assert a is not b
    # The OpenAI client (built from each user's key) is not shared across users.
    assert a.get_openai_client() is not b.get_openai_client()
