import types

import pytest
from langflow.services.auth import api_key_codec
from langflow.services.auth.clerk_utils import auth_header_ctx


@pytest.fixture(autouse=True)
def reset_auth_context():
    token = auth_header_ctx.set({})
    try:
        yield
    finally:
        auth_header_ctx.reset(token)


def make_settings(*, clerk_enabled: bool):
    return types.SimpleNamespace(
        auth_settings=types.SimpleNamespace(CLERK_AUTH_ENABLED=clerk_enabled)
    )


def test_generate_api_key_without_clerk(monkeypatch):
    monkeypatch.setattr(api_key_codec, "get_settings_service", lambda: make_settings(clerk_enabled=False))
    monkeypatch.setattr(api_key_codec.secrets, "token_urlsafe", lambda _: "legacy-secret")

    api_key = api_key_codec.generate_api_key_for_user("user-123")

    assert api_key == "sk-legacy-secret"


def test_generate_api_key_with_clerk(monkeypatch):
    monkeypatch.setattr(api_key_codec, "get_settings_service", lambda: make_settings(clerk_enabled=True))
    monkeypatch.setattr(api_key_codec.secrets, "token_urlsafe", lambda _: "nonce")

    token = auth_header_ctx.set({"org_id": "org-456"})
    try:
        api_key = api_key_codec.generate_api_key_for_user("user-123")
    finally:
        auth_header_ctx.reset(token)

    payload = api_key_codec.decode_api_key(api_key)

    assert payload.is_encoded
    assert payload.organization_id == "org-456"
    assert payload.user_id == "user-123"
    assert payload.nonce == "nonce"


def test_apply_api_key_context_with_clerk(monkeypatch):
    monkeypatch.setattr(api_key_codec, "get_settings_service", lambda: make_settings(clerk_enabled=True))
    monkeypatch.setattr(api_key_codec.secrets, "token_urlsafe", lambda _: "nonce")

    key = api_key_codec.encode_api_key(user_id="user-123", organization_id="org-456")
    settings = make_settings(clerk_enabled=True)

    assert api_key_codec.apply_api_key_context(key, expected_user_id="user-123", settings_service=settings)

    context = auth_header_ctx.get()
    assert context["org_id"] == "org-456"
    assert context["uuid"] == "user-123"


def test_apply_api_key_context_rejects_user_mismatch(monkeypatch):
    monkeypatch.setattr(api_key_codec, "get_settings_service", lambda: make_settings(clerk_enabled=True))
    monkeypatch.setattr(api_key_codec.secrets, "token_urlsafe", lambda _: "nonce")

    key = api_key_codec.encode_api_key(user_id="user-123", organization_id="org-456")
    settings = make_settings(clerk_enabled=True)

    assert not api_key_codec.apply_api_key_context(key, expected_user_id="user-789", settings_service=settings)
    assert auth_header_ctx.get() == {}
