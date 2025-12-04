from pathlib import Path

import pytest
from lfx.services.settings.auth import AuthSettings
from lfx.services.settings.constants import DEFAULT_SUPERUSER
from pydantic import SecretStr, ValidationError


@pytest.mark.parametrize("auto_login", [True, False])
def test_superuser_password_is_secretstr(auto_login, tmp_path: Path):
    cfg_dir = tmp_path.as_posix()
    settings = AuthSettings(CONFIG_DIR=cfg_dir, AUTO_LOGIN=auto_login)
    assert isinstance(settings.SUPERUSER_PASSWORD, SecretStr)


def test_auto_login_true_forces_default_and_scrubs_password(tmp_path: Path):
    cfg_dir = tmp_path.as_posix()
    settings = AuthSettings(
        CONFIG_DIR=cfg_dir,
        AUTO_LOGIN=True,
        SUPERUSER="custom",
        SUPERUSER_PASSWORD=SecretStr("_changed"),
    )
    # Validator forces default username and scrubs password
    assert settings.SUPERUSER == DEFAULT_SUPERUSER
    assert isinstance(settings.SUPERUSER_PASSWORD, SecretStr)
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == "langflow"

    # reset_credentials keeps default username (AUTO_LOGIN on) and keeps password scrubbed
    settings.reset_credentials()
    assert settings.SUPERUSER == DEFAULT_SUPERUSER
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == "langflow"


def test_auto_login_false_preserves_username_and_scrubs_password_on_reset(tmp_path: Path):
    cfg_dir = tmp_path.as_posix()
    settings = AuthSettings(
        CONFIG_DIR=cfg_dir,
        AUTO_LOGIN=False,
        SUPERUSER="admin",
        SUPERUSER_PASSWORD=SecretStr("strongpass"),
    )
    # Values preserved at init
    assert settings.SUPERUSER == "admin"
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == "strongpass"

    # After reset, username preserved, password scrubbed
    settings.reset_credentials()
    assert settings.SUPERUSER == "admin"
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == ""


# ============================================================================
# API_KEY_SOURCE Settings Tests
# ============================================================================


class TestApiKeySourceSettings:
    """Tests for API_KEY_SOURCE configuration setting."""

    def test_api_key_source_default_is_db(self, tmp_path: Path):
        """Default API_KEY_SOURCE should be 'db' for backward compatibility."""
        cfg_dir = tmp_path.as_posix()
        settings = AuthSettings(CONFIG_DIR=cfg_dir)
        assert settings.API_KEY_SOURCE == "db"

    def test_api_key_source_accepts_db(self, tmp_path: Path):
        """API_KEY_SOURCE should accept 'db' value."""
        cfg_dir = tmp_path.as_posix()
        settings = AuthSettings(CONFIG_DIR=cfg_dir, API_KEY_SOURCE="db")
        assert settings.API_KEY_SOURCE == "db"

    def test_api_key_source_accepts_env(self, tmp_path: Path):
        """API_KEY_SOURCE should accept 'env' value."""
        cfg_dir = tmp_path.as_posix()
        settings = AuthSettings(CONFIG_DIR=cfg_dir, API_KEY_SOURCE="env")
        assert settings.API_KEY_SOURCE == "env"

    def test_api_key_source_rejects_invalid_value(self, tmp_path: Path):
        """API_KEY_SOURCE should reject invalid values."""
        cfg_dir = tmp_path.as_posix()
        with pytest.raises(ValidationError) as exc_info:
            AuthSettings(CONFIG_DIR=cfg_dir, API_KEY_SOURCE="invalid")
        assert "API_KEY_SOURCE" in str(exc_info.value)

    def test_api_key_source_rejects_empty_string(self, tmp_path: Path):
        """API_KEY_SOURCE should reject empty string."""
        cfg_dir = tmp_path.as_posix()
        with pytest.raises(ValidationError):
            AuthSettings(CONFIG_DIR=cfg_dir, API_KEY_SOURCE="")


class TestApiKeySourceEnvironmentVariables:
    """Tests for API_KEY_SOURCE loaded from environment variables."""

    def test_api_key_source_from_env_var(self, tmp_path: Path, monkeypatch):
        """API_KEY_SOURCE should be loaded from LANGFLOW_API_KEY_SOURCE env var."""
        cfg_dir = tmp_path.as_posix()
        monkeypatch.setenv("LANGFLOW_API_KEY_SOURCE", "env")
        settings = AuthSettings(CONFIG_DIR=cfg_dir)
        assert settings.API_KEY_SOURCE == "env"

    def test_explicit_value_overrides_env_var(self, tmp_path: Path, monkeypatch):
        """Explicit parameter should override environment variable."""
        cfg_dir = tmp_path.as_posix()
        monkeypatch.setenv("LANGFLOW_API_KEY_SOURCE", "env")
        settings = AuthSettings(CONFIG_DIR=cfg_dir, API_KEY_SOURCE="db")
        assert settings.API_KEY_SOURCE == "db"

    def test_invalid_api_key_source_from_env_var(self, tmp_path: Path, monkeypatch):
        """Invalid API_KEY_SOURCE from env var should raise ValidationError."""
        cfg_dir = tmp_path.as_posix()
        monkeypatch.setenv("LANGFLOW_API_KEY_SOURCE", "invalid")
        with pytest.raises(ValidationError):
            AuthSettings(CONFIG_DIR=cfg_dir)
