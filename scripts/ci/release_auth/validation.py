"""Validate authentication defaults before release publication."""

import zipfile
from pathlib import Path

from .constants import WHEEL_AUTH_PATH
from .parsing import parse_auto_login_default


def verify_release_source(path: Path) -> None:
    """Reject source archives whose tagged code still enables auto-login.

    Raises:
        ValueError: AUTO_LOGIN is enabled or its declaration is ambiguous.
    """
    if parse_auto_login_default(path.read_bytes()).value is not False:
        msg = "Release source must default AUTO_LOGIN to False. Run the Prepare Release Tag workflow first."
        raise ValueError(msg)


def verify_release_wheel(path: Path) -> None:
    """Refuse to publish an LFX wheel without the release authentication default.

    Raises:
        ValueError: The wheel is missing auth settings or does not disable auto-login.
        zipfile.BadZipFile: The artifact is not a readable wheel archive.
    """
    with zipfile.ZipFile(path) as wheel:
        try:
            source = wheel.read(WHEEL_AUTH_PATH)
        except KeyError as exc:
            msg = f"{path.name} does not contain {WHEEL_AUTH_PATH}"
            raise ValueError(msg) from exc
    if parse_auto_login_default(source).value is not False:
        msg = f"{path.name} must default AuthSettings.AUTO_LOGIN to False before release"
        raise ValueError(msg)
