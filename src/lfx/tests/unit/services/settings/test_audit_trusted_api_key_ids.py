"""The assertion allowlist is parsed as exact database credential UUIDs."""

from uuid import uuid4

import pytest
from lfx.services.settings.base import Settings
from pydantic import ValidationError


def test_no_credentials_are_trusted_by_default(monkeypatch):
    monkeypatch.delenv("LANGFLOW_AUDIT_TRUSTED_API_KEY_IDS", raising=False)
    assert Settings().audit_trusted_api_key_ids == []


def test_environment_supports_rotation_and_deduplicates_ids(monkeypatch):
    first, second = uuid4(), uuid4()
    monkeypatch.setenv("LANGFLOW_AUDIT_TRUSTED_API_KEY_IDS", f" {first}, {second},{first}")
    assert Settings().audit_trusted_api_key_ids == [first, second]


def test_invalid_record_ids_fail_configuration(monkeypatch):
    monkeypatch.setenv("LANGFLOW_AUDIT_TRUSTED_API_KEY_IDS", "not-a-record-id")
    with pytest.raises(ValidationError):
        Settings()


def test_secret_backed_trust_hides_key_value(monkeypatch):
    value = "local-test-service-key"  # pragma: allowlist secret
    monkeypatch.setenv("LANGFLOW_AUDIT_TRUSTED_API_KEY", value)
    settings = Settings()
    assert settings.audit_trusted_api_key.get_secret_value() == value
    assert value not in repr(settings)
    assert value not in settings.model_dump_json()


def test_trusted_key_is_not_written_to_settings_yaml(monkeypatch, tmp_path):
    from lfx.services.settings.base import save_settings_to_yaml

    value = "local-test-service-key"  # pragma: allowlist secret
    monkeypatch.setenv("LANGFLOW_AUDIT_TRUSTED_API_KEY", value)
    destination = tmp_path / "settings.yaml"
    save_settings_to_yaml(Settings(), str(destination))
    assert value not in destination.read_text()
    assert "audit_trusted_api_key:" not in destination.read_text()
