"""Regression tests for voice-mode cross-tenant client confusion.

The ElevenLabs client must be built per requesting user (no process-global
singleton), and the voice/TTS config caches must be keyed by the authenticated
user, not just the client-supplied session_id.
"""

import langflow.api.v1.voice_mode as vm
import pytest


@pytest.mark.asyncio
async def test_get_or_create_elevenlabs_client_is_per_user(monkeypatch):
    """Each user gets an ElevenLabs client built from their OWN key (no shared singleton)."""
    keys = {"user-a": "key-a", "user-b": "key-b"}

    class FakeVariableService:
        async def get_variable(self, *, user_id, name, field, session):  # noqa: ARG002
            return keys[user_id]

    monkeypatch.setattr(vm, "get_variable_service", lambda: FakeVariableService())

    captured: list[str] = []

    def fake_elevenlabs(*, api_key):
        captured.append(api_key)
        return f"client::{api_key}"

    monkeypatch.setattr(vm, "ElevenLabs", fake_elevenlabs)

    client_a = await vm.get_or_create_elevenlabs_client("user-a", "sess")
    client_b = await vm.get_or_create_elevenlabs_client("user-b", "sess")

    # Built from each user's own key — user-b is NOT served user-a's cached client.
    assert client_a == "client::key-a"
    assert client_b == "client::key-b"
    assert captured == ["key-a", "key-b"]


@pytest.mark.asyncio
async def test_get_or_create_elevenlabs_client_requires_user_and_session():
    """No user/session -> no client (avoids falling back to some other tenant's key)."""
    assert await vm.get_or_create_elevenlabs_client(None, None) is None
    assert await vm.get_or_create_elevenlabs_client("user", None) is None


def test_get_voice_config_scoped_by_user():
    """Same client-supplied session_id but different users must not share a VoiceConfig."""
    vm.voice_config_cache.clear()

    a = vm.get_voice_config("shared-session", "user-a")
    b = vm.get_voice_config("shared-session", "user-b")
    a_again = vm.get_voice_config("shared-session", "user-a")

    assert a is not b
    assert a is a_again  # same (user, session) is still cached


def test_get_tts_config_scoped_by_user():
    """Same session_id but different users must not share a TTSConfig / OpenAI client."""
    vm.tts_config_cache.clear()

    a = vm.get_tts_config("shared-session", "openai-key-a", "user-a")
    b = vm.get_tts_config("shared-session", "openai-key-b", "user-b")

    assert a is not b
    # The OpenAI client (built from each user's key) is not shared across users.
    assert a.get_openai_client() is not b.get_openai_client()
