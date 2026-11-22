"""Scope enforcement and new-key issuance have separate rollout switches."""

from uuid import uuid4

from lfx.services.settings.auth import AuthSettings
from pydantic import SecretStr


def test_scoped_key_issuance_requires_explicit_enablement(tmp_path, monkeypatch):
    monkeypatch.delenv("LANGFLOW_API_KEY_SCOPES_ENABLED", raising=False)
    settings = AuthSettings(CONFIG_DIR=str(tmp_path), SECRET_KEY=SecretStr(uuid4().hex * 2))
    assert settings.API_KEY_SCOPES_ENABLED is False


def test_scoped_key_issuance_can_be_enabled_after_upgrade(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGFLOW_API_KEY_SCOPES_ENABLED", "true")
    settings = AuthSettings(CONFIG_DIR=str(tmp_path), SECRET_KEY=SecretStr(uuid4().hex * 2))
    assert settings.API_KEY_SCOPES_ENABLED is True
