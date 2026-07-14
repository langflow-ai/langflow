"""Tests for tenant-scoped local-file containment."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from lfx.utils.file_path_security import (
    LocalFileAccessError,
    component_file_access_scopes,
    enforce_local_file_access,
    is_local_file_access_restricted,
)


@contextmanager
def mock_settings(*, restricted: bool, config_dir: str, database_url: str = ""):
    with patch("lfx.utils.file_path_security.get_settings_service") as mock_get:
        service = MagicMock()
        service.settings.restrict_local_file_access = restricted
        service.settings.config_dir = config_dir
        service.settings.database_url = database_url
        mock_get.return_value = service
        yield


def test_disabled_is_noop(tmp_path):
    with mock_settings(restricted=False, config_dir=str(tmp_path)):
        assert is_local_file_access_restricted() is False
        assert enforce_local_file_access("/etc/passwd") == Path("/etc/passwd")


def test_component_scopes_include_user_and_flow():
    graph = SimpleNamespace(user_id="graph-user", flow_id="flow-id")
    component = SimpleNamespace(_user_id="component-user", _vertex=SimpleNamespace(graph=graph))
    assert component_file_access_scopes(component) == ("component-user", "flow-id")


def test_path_inside_flow_scope_allowed(tmp_path):
    upload = tmp_path / "flow-id" / "upload.txt"
    upload.parent.mkdir()
    upload.write_text("hi")
    with mock_settings(restricted=True, config_dir=str(tmp_path)):
        assert enforce_local_file_access(upload, scope_ids=["flow-id"]) == upload.resolve()


def test_single_string_scope_is_not_split(tmp_path):
    upload = tmp_path / "flow-id" / "upload.txt"
    upload.parent.mkdir()
    upload.write_text("hi")
    with mock_settings(restricted=True, config_dir=str(tmp_path)):
        assert enforce_local_file_access(upload, scope_ids="flow-id") == upload.resolve()


@pytest.mark.parametrize("scope", ["", ".", "..", "../victim", "victim/user", "victim\\user", "bad\x00id"])
def test_invalid_scope_blocked(tmp_path, scope):
    with mock_settings(restricted=True, config_dir=str(tmp_path)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access(tmp_path / "file.txt", scope_ids=[scope])


def test_missing_scope_fails_closed(tmp_path):
    with (
        mock_settings(restricted=True, config_dir=str(tmp_path)),
        pytest.raises(LocalFileAccessError, match="requires an authenticated user or flow scope"),
    ):
        enforce_local_file_access(tmp_path / "flow-id" / "upload.txt")


@pytest.mark.parametrize("candidate", ["/etc/passwd", "../outside.txt"])
def test_outside_path_blocked(tmp_path, candidate):
    path = Path(candidate) if Path(candidate).is_absolute() else tmp_path / "flow-id" / candidate
    with mock_settings(restricted=True, config_dir=str(tmp_path)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access(path, scope_ids=["flow-id"])


def test_other_tenant_scope_blocked(tmp_path):
    victim = tmp_path / "victim" / "secret.txt"
    victim.parent.mkdir()
    victim.write_text("secret")
    with mock_settings(restricted=True, config_dir=str(tmp_path)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access(victim, scope_ids=["attacker", "attacker-flow"])


def test_symlink_escape_blocked(tmp_path):
    scope = tmp_path / "flow-id"
    scope.mkdir()
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret")
    link = scope / "link.txt"
    link.symlink_to(outside)
    with mock_settings(restricted=True, config_dir=str(tmp_path)), pytest.raises(LocalFileAccessError):
        enforce_local_file_access(link, scope_ids=["flow-id"])


def test_symlink_within_scope_allowed(tmp_path):
    scope = tmp_path / "flow-id"
    scope.mkdir()
    target = scope / "target.txt"
    target.write_text("hi")
    link = scope / "link.txt"
    link.symlink_to(target)
    with mock_settings(restricted=True, config_dir=str(tmp_path)):
        assert enforce_local_file_access(link, scope_ids=["flow-id"]) == target.resolve()


@pytest.mark.parametrize("name", ["secret_key", "private_key.pem", "public_key.pem"])
def test_reserved_server_file_blocked_even_if_scope_widens(tmp_path, name):
    reserved = tmp_path / name
    reserved.write_text("secret")
    with (
        mock_settings(restricted=True, config_dir=str(tmp_path)),
        patch("lfx.utils.file_path_security._scope_roots", return_value=(tmp_path.resolve(),)),
        pytest.raises(LocalFileAccessError, match="server-managed file"),
    ):
        enforce_local_file_access(reserved, scope_ids=["flow-id"])


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
def test_reserved_sqlite_database_and_sidecars_blocked(tmp_path, suffix):
    db = tmp_path / "flow-id" / "langflow.db"
    db.parent.mkdir()
    candidate = Path(str(db) + suffix)
    candidate.write_text("db pages")
    with (
        mock_settings(restricted=True, config_dir=str(tmp_path), database_url=f"sqlite:///{db}"),
        pytest.raises(LocalFileAccessError, match="server-managed file"),
    ):
        enforce_local_file_access(candidate, scope_ids=["flow-id"])


def test_async_sqlite_url_with_query_is_reserved(tmp_path):
    db = tmp_path / "flow-id" / "langflow.db"
    db.parent.mkdir()
    db.write_text("db")
    url = f"sqlite+aiosqlite:///{db}?check_same_thread=false"
    with (
        mock_settings(restricted=True, config_dir=str(tmp_path), database_url=url),
        pytest.raises(LocalFileAccessError, match="server-managed file"),
    ):
        enforce_local_file_access(db, scope_ids=["flow-id"])


def test_tenant_upload_named_like_secret_is_allowed(tmp_path):
    upload = tmp_path / "flow-id" / "secret_key"
    upload.parent.mkdir()
    upload.write_text("tenant data")
    with mock_settings(restricted=True, config_dir=str(tmp_path)):
        assert enforce_local_file_access(upload, scope_ids=["flow-id"]) == upload.resolve()
