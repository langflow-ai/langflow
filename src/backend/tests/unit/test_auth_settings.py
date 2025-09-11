from pathlib import Path

import pytest
from pydantic import SecretStr

from langflow.services.settings.auth import AuthSettings
from langflow.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD


@pytest.mark.parametrize("auto_login", [True, False])
def test_superuser_password_is_secretstr(auto_login, tmp_path: Path):
    cfg_dir = tmp_path.as_posix()
    settings = AuthSettings(CONFIG_DIR=cfg_dir, AUTO_LOGIN=auto_login)
    assert isinstance(settings.SUPERUSER_PASSWORD, SecretStr)


def test_auto_login_true_forces_defaults(tmp_path: Path):
    cfg_dir = tmp_path.as_posix()
    settings = AuthSettings(
        CONFIG_DIR=cfg_dir,
        AUTO_LOGIN=True,
        SUPERUSER="custom",
        SUPERUSER_PASSWORD=SecretStr("custom_password_changed"),
    )
    # Validator forces default username and scrubs password
    assert settings.SUPERUSER == DEFAULT_SUPERUSER
    assert isinstance(settings.SUPERUSER_PASSWORD, SecretStr)
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == DEFAULT_SUPERUSER_PASSWORD.get_secret_value()

    # reset_credentials keeps default username (AUTO_LOGIN on) and clears password
    settings.reset_credentials()
    assert settings.SUPERUSER == DEFAULT_SUPERUSER
    assert settings.SUPERUSER_PASSWORD.get_secret_value() == ""


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
