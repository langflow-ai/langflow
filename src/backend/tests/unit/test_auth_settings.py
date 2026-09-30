from pathlib import Path
from unittest.mock import patch

import pytest
from lfx.services.settings.auth import AuthSettings
from lfx.services.settings.constants import (
    DEFAULT_SUPERUSER,
    DEFAULT_SUPERUSER_PASSWORD,
    SHORT_SECRET_KEY_WARNING,
)
from pydantic import SecretStr, ValidationError


@pytest.mark.parametrize("auto_login", [True, False])
def test_superuser_password_is_secretstr(auto_login, tmp_path: Path):
    cfg_dir = tmp_path.as_posix()
    settings = AuthSettings(CONFIG_DIR=cfg_dir, AUTO_LOGIN=auto_login)
    assert isinstance(settings.SUPERUSER_PASSWORD, SecretStr)


def test_auto_login_true_preserves_configured_credentials_and_scrubs_password(tmp_path: Path):
    cfg_dir = tmp_path.as_posix()
    settings = AuthSettings(
        CONFIG_DIR=cfg_dir,
        AUTO_LOGIN=True,
        SUPERUSER="custom",
        SUPERUSER_PASSWORD=SecretStr("_changed"),
    )
    assert settings.SUPERUSER == "custom"
    assert isinstance(settings.SUPERUSER_PASSWORD, SecretStr)
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == "_changed"

    # reset_credentials preserves the username and scrubs the password even in AUTO_LOGIN mode.
    settings.reset_credentials()
    assert settings.SUPERUSER == "custom"
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == ""


def test_default_superuser_password_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # conftest load_dotenv() can inject a developer .env (e.g. LANGFLOW_SUPERUSER=admin);
    # this test asserts AuthSettings defaults, so clear any process overrides.
    monkeypatch.delenv("LANGFLOW_SUPERUSER", raising=False)
    monkeypatch.delenv("LANGFLOW_SUPERUSER_PASSWORD", raising=False)

    cfg_dir = tmp_path.as_posix()
    settings = AuthSettings(CONFIG_DIR=cfg_dir)
    assert settings.SUPERUSER == DEFAULT_SUPERUSER
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == ""
    assert DEFAULT_SUPERUSER_PASSWORD.get_secret_value() == ""


def test_short_secret_key_logs_upgrade_warning(tmp_path: Path):
    with patch("lfx.services.settings.auth.logger") as mock_logger:
        AuthSettings(CONFIG_DIR=tmp_path.as_posix(), SECRET_KEY=SecretStr("shortkey123"))

    mock_logger.warning.assert_called_once_with(SHORT_SECRET_KEY_WARNING)


def test_generated_secret_key_does_not_log_upgrade_warning(tmp_path: Path):
    with patch("lfx.services.settings.auth.logger") as mock_logger:
        settings = AuthSettings(CONFIG_DIR=tmp_path.as_posix())

    assert len(settings.SECRET_KEY.get_secret_value()) >= 32
    mock_logger.warning.assert_not_called()


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


class TestSsoRedirectUrlSettings:
    def test_sso_redirect_url_is_declared_with_description(self, tmp_path: Path):
        settings = AuthSettings(CONFIG_DIR=tmp_path.as_posix())

        assert settings.SSO_REDIRECT_URL is None
        assert AuthSettings.model_fields["SSO_REDIRECT_URL"].description

    def test_sso_redirect_url_loads_relative_path_from_environment(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSO_REDIRECT_URL", "/api/v1/sso/callback")

        settings = AuthSettings(CONFIG_DIR=tmp_path.as_posix())

        assert settings.SSO_REDIRECT_URL == "/api/v1/sso/callback"

    @pytest.mark.parametrize("blank_url", ["", "   ", "\t\r\n"])
    def test_sso_redirect_url_normalizes_blank_values_to_none(self, blank_url: str, tmp_path: Path):
        settings = AuthSettings(CONFIG_DIR=tmp_path.as_posix(), SSO_REDIRECT_URL=blank_url)

        assert settings.SSO_REDIRECT_URL is None

    @pytest.mark.parametrize(
        "control_character_url",
        [
            "/api/v1/sso/\x00callback",
            "/api/v1/sso/callback\nnext",
            "/api/v1/sso/\x7fcallback",
            "\t/api/v1/sso/callback",
        ],
    )
    def test_sso_redirect_url_rejects_control_characters(self, control_character_url: str, tmp_path: Path):
        with pytest.raises(ValidationError, match="control characters"):
            AuthSettings(CONFIG_DIR=tmp_path.as_posix(), SSO_REDIRECT_URL=control_character_url)

    @pytest.mark.parametrize(
        "off_origin_url",
        [
            "https://attacker.example/sso",
            "//attacker.example/sso",
            "///attacker.example/sso",
            "\\\\attacker.example\\sso",
        ],
    )
    def test_sso_redirect_url_rejects_absolute_off_origin_url(self, off_origin_url: str, tmp_path: Path):
        with pytest.raises(ValidationError, match="SSO_REDIRECT_URL"):
            AuthSettings(CONFIG_DIR=tmp_path.as_posix(), SSO_REDIRECT_URL=off_origin_url)
