"""Tests for the platform-aware subprocess env allowlist."""

from __future__ import annotations

from lfx.mcp.shell.shell_constants import (
    SUBPROCESS_ENV_ALLOWLIST_POSIX,
    SUBPROCESS_ENV_ALLOWLIST_WINDOWS,
    current_env_allowlist,
)


def test_posix_allowlist_should_contain_path_and_home():
    assert "PATH" in SUBPROCESS_ENV_ALLOWLIST_POSIX
    assert "HOME" in SUBPROCESS_ENV_ALLOWLIST_POSIX
    assert "USER" in SUBPROCESS_ENV_ALLOWLIST_POSIX


def test_windows_allowlist_should_contain_user_profile_and_systemroot():
    assert "USERPROFILE" in SUBPROCESS_ENV_ALLOWLIST_WINDOWS
    assert "APPDATA" in SUBPROCESS_ENV_ALLOWLIST_WINDOWS
    assert "LOCALAPPDATA" in SUBPROCESS_ENV_ALLOWLIST_WINDOWS
    assert "SystemRoot" in SUBPROCESS_ENV_ALLOWLIST_WINDOWS
    assert "ComSpec" in SUBPROCESS_ENV_ALLOWLIST_WINDOWS
    assert "PATHEXT" in SUBPROCESS_ENV_ALLOWLIST_WINDOWS
    # PATH is needed on both — Windows uses it for binary lookup too
    assert "PATH" in SUBPROCESS_ENV_ALLOWLIST_WINDOWS


def test_windows_allowlist_should_not_leak_secrets_pattern():
    """Sanity check: no API_KEY-like names in either allowlist."""
    for name in (*SUBPROCESS_ENV_ALLOWLIST_POSIX, *SUBPROCESS_ENV_ALLOWLIST_WINDOWS):
        assert "KEY" not in name.upper()
        assert "SECRET" not in name.upper()
        assert "TOKEN" not in name.upper()


def test_current_env_allowlist_should_match_platform():
    import os

    result = current_env_allowlist()
    if os.name == "nt":
        assert result == SUBPROCESS_ENV_ALLOWLIST_WINDOWS
    else:
        assert result == SUBPROCESS_ENV_ALLOWLIST_POSIX
