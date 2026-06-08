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
def mock_settings(*, restricted: bool, config_dir: str, database_url: str = ""):
    with patch("lfx.utils.file_path_security.get_settings_service") as mock_get:
        settings = MagicMock()
        settings.settings.restrict_local_file_access = restricted
        settings.settings.config_dir = config_dir
        # Explicit string so the reserved-DB derivation in _reserved_secret_paths is deterministic.
        settings.settings.database_url = database_url
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


@pytest.mark.parametrize("name", ["secret_key", "private_key.pem", "public_key.pem"])
def test_reserved_secret_file_blocked(tmp_path, name):
    """The server-managed secret/key files in config_dir are denied even though they sit inside it."""
    (tmp_path / name).write_text("SENSITIVE")
    with mock_settings(restricted=True, config_dir=str(tmp_path)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access(str(tmp_path / name))


def test_reserved_secret_file_via_traversal_blocked(tmp_path):
    """A traversal that resolves back to a reserved secret file is denied.

    This is the actual exploit shape: a storage-path input like "<flow>/../secret_key" routes
    through build_full_path (no '..' check) to <config_dir>/<flow>/../secret_key, which resolves
    back inside the boundary.
    """
    (tmp_path / "secret_key").write_text("MASTER KEY")
    traversal = str(tmp_path / "some-flow" / ".." / "secret_key")
    with mock_settings(restricted=True, config_dir=str(tmp_path)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access(traversal)


def test_reserved_db_file_blocked(tmp_path):
    """The SQLite DB under config_dir (save_db_in_config_dir) is denied."""
    db = tmp_path / "langflow.db"
    db.write_text("db")
    with (
        mock_settings(restricted=True, config_dir=str(tmp_path), database_url=f"sqlite:///{db}"),
        pytest.raises(LocalFileAccessError),
    ):
        enforce_local_file_access(str(db))


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_reserved_db_sidecar_blocked(tmp_path, suffix):
    """SQLite WAL/SHM/journal sidecars hold un-checkpointed DB pages and are denied too."""
    db = tmp_path / "langflow.db"
    sidecar = tmp_path / f"langflow.db{suffix}"
    sidecar.write_text("pages")
    with (
        mock_settings(restricted=True, config_dir=str(tmp_path), database_url=f"sqlite:///{db}"),
        pytest.raises(LocalFileAccessError),
    ):
        enforce_local_file_access(str(sidecar))


def test_reserved_db_with_async_driver_and_query_blocked(tmp_path):
    """An async sqlite URL with a query string still resolves to the protected DB file."""
    db = tmp_path / "langflow.db"
    db.write_text("db")
    url = f"sqlite+aiosqlite:///{db}?check_same_thread=false"
    with (
        mock_settings(restricted=True, config_dir=str(tmp_path), database_url=url),
        pytest.raises(LocalFileAccessError),
    ):
        enforce_local_file_access(str(db))


def test_upload_named_like_secret_in_flow_subdir_allowed(tmp_path):
    """A tenant upload that merely shares a reserved name but lives in a flow subdir stays readable.

    Proves the denial matches the exact config_dir location, not the basename anywhere.
    """
    upload = tmp_path / "flow-id" / "secret_key"
    upload.parent.mkdir(parents=True)
    upload.write_text("just a user file named secret_key")
    with mock_settings(restricted=True, config_dir=str(tmp_path)):
        assert enforce_local_file_access(str(upload)) == Path(str(upload))
