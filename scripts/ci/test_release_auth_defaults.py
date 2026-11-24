"""Behavioral coverage for release source preparation and artifact validation."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.ci.release_auth.constants import AUTH_SOURCE
from scripts.ci.release_auth.preparation import prepare_release_auth
from scripts.ci.release_auth.validation import verify_release_source, verify_release_wheel

pytest_plugins = ("scripts.ci.release_auth_fixtures",)


def test_should_change_only_auto_login_when_preparing_release(tmp_path: Path, development_auth_source: bytes) -> None:
    repo_source = Path(__file__).resolve().parents[2] / AUTH_SOURCE
    original = repo_source.read_bytes()
    path = tmp_path / "auth.py"
    path.write_bytes(development_auth_source)

    prepare_release_auth(path)

    expected = development_auth_source.replace(
        b"AUTO_LOGIN: bool = Field(\n        default=True,", b"AUTO_LOGIN: bool = Field(\n        default=False,"
    )
    assert expected != development_auth_source
    assert path.read_bytes() == expected
    prepare_release_auth(path)
    assert path.read_bytes() == expected
    assert repo_source.read_bytes() == original


@pytest.mark.parametrize(
    "source",
    [
        "class AuthSettings:\n    AUTO_LOGIN: bool = True\n",
        "class AuthSettings:\n    AUTO_LOGIN: bool = Field(default_factory=bool)\n",
        "class AuthSettings:\n    AUTO_LOGIN: bool = Field(default='true')\n",
        "class AuthSettings:\n    AUTO_LOGIN: bool = Field(default=1)\n",
        "class AuthSettings:\n    OTHER: bool = Field(default=True)\n",
        "class OtherSettings:\n    AUTO_LOGIN: bool = Field(default=True)\n",
        "class AuthSettings: pass\nclass AuthSettings: pass\n",
        "class AuthSettings:\n    AUTO_LOGIN: bool = Field(default=True)\n"
        "    AUTO_LOGIN: bool = Field(default=False)\n",
    ],
)
def test_should_preserve_source_when_settings_shape_is_invalid(tmp_path: Path, source: str) -> None:
    path = tmp_path / "auth.py"
    path.write_text(source)

    with pytest.raises(ValueError, match="Expected"):
        prepare_release_auth(path)

    assert path.read_text() == source


def test_should_preserve_utf8_and_line_endings_when_preparing_release(tmp_path: Path) -> None:
    source = "class AuthSettings:\r\n    OTHER = 'é'; AUTO_LOGIN: bool = Field(default=True)\r\n".encode()
    path = tmp_path / "auth.py"
    path.write_bytes(source)

    prepare_release_auth(path)

    assert path.read_bytes() == source.replace(b"default=True", b"default=False")


def test_should_accept_wheel_when_auto_login_is_disabled(wheel_files: dict[bool, Path]) -> None:
    verify_release_wheel(wheel_files[True])


def test_should_reject_wheel_when_auto_login_is_enabled(wheel_files: dict[bool, Path]) -> None:
    with pytest.raises(ValueError, match=r"must default AuthSettings\.AUTO_LOGIN to False"):
        verify_release_wheel(wheel_files[False])


def test_should_reject_wheel_when_auth_settings_are_missing(tmp_path: Path) -> None:
    wheel = tmp_path / "lfx-1.13.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w"):
        pass

    with pytest.raises(ValueError, match="does not contain"):
        verify_release_wheel(wheel)


def test_should_reject_source_when_auto_login_is_enabled(tmp_path: Path, development_auth_source: bytes) -> None:
    path = tmp_path / "auth.py"
    path.write_bytes(development_auth_source)

    with pytest.raises(ValueError, match="Prepare Release Tag workflow"):
        verify_release_source(path)
