from pathlib import Path

import pytest
from lfx.services.settings.auth import AuthSettings
from lfx.services.settings.constants import DEFAULT_SUPERUSER
from pydantic import SecretStr


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
