"""Tests for local file-path containment (LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS)."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lfx.utils.file_path_security import (
    LocalFileAccessError,
    enforce_local_file_access,
    is_local_file_access_restricted,
)


@contextmanager
def mock_settings(*, restricted: bool, config_dir: str):
    with patch("lfx.utils.file_path_security.get_settings_service") as mock_get:
        settings = MagicMock()
        settings.settings.restrict_local_file_access = restricted
        settings.settings.config_dir = config_dir
        mock_get.return_value = settings
        yield


def test_disabled_is_noop(tmp_path):
    """When restriction is off, any path is allowed (single-tenant default)."""
    with mock_settings(restricted=False, config_dir=str(tmp_path)):
        assert is_local_file_access_restricted() is False
        # An obviously-outside path is returned unchanged.
        assert enforce_local_file_access("/etc/passwd") == Path("/etc/passwd")


def test_path_inside_storage_allowed(tmp_path):
    """A path inside the storage data dir is allowed when restricted."""
    inside = tmp_path / "flow-id" / "upload.txt"
    inside.parent.mkdir(parents=True)
    inside.write_text("hi")
    with mock_settings(restricted=True, config_dir=str(tmp_path)):
        assert enforce_local_file_access(str(inside)) == Path(str(inside))


def test_absolute_path_outside_blocked(tmp_path):
    """An absolute server path outside the storage dir is blocked when restricted."""
    with mock_settings(restricted=True, config_dir=str(tmp_path)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access("/etc/passwd")


def test_traversal_escape_blocked(tmp_path):
    """A traversal string escaping the storage dir is blocked when restricted."""
    escape = str(tmp_path / ".." / ".." / "etc" / "passwd")
    with mock_settings(restricted=True, config_dir=str(tmp_path)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access(escape)


def test_storage_dir_itself_allowed(tmp_path):
    """The storage dir root itself is allowed (a path is relative to itself)."""
    with mock_settings(restricted=True, config_dir=str(tmp_path)):
        assert enforce_local_file_access(str(tmp_path)) == Path(str(tmp_path))


def test_symlink_inside_storage_pointing_outside_blocked(tmp_path):
    """A symlink that lives inside the storage dir but resolves outside it is blocked.

    This guards the docstring promise that symlinks are resolved before the containment
    check. Without ``Path.resolve()`` (e.g. if it were replaced by ``Path.absolute()``,
    which does not follow symlinks) the link would appear to live inside storage and the
    escape would go undetected — so this test fails closed on that regression.
    """
    storage = tmp_path / "storage"
    storage.mkdir()
    outside_secret = tmp_path / "outside" / "secret.txt"
    outside_secret.parent.mkdir()
    outside_secret.write_text("top secret")
    link = storage / "escape.txt"
    link.symlink_to(outside_secret)
    with mock_settings(restricted=True, config_dir=str(storage)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access(str(link))


def test_symlink_inside_storage_pointing_inside_allowed(tmp_path):
    """A symlink inside storage that resolves to another in-storage file is allowed.

    Positive control proving the symlink test above blocks because of the escape, not
    merely because a symlink is present.
    """
    storage = tmp_path / "storage"
    storage.mkdir()
    real = storage / "real.txt"
    real.write_text("hi")
    link = storage / "link.txt"
    link.symlink_to(real)
    with mock_settings(restricted=True, config_dir=str(storage)):
        assert enforce_local_file_access(str(link)) == Path(str(link))
