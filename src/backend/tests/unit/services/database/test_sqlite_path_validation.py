"""Tests for the SQLite database-path diagnostics.

Regression coverage for issue #13634 (Bug 1, diagnostics half): a relative
``LANGFLOW_DATABASE_URL`` pointing at a missing subdirectory used to crash with
an opaque ``RuntimeError: Error creating DB and tables``. ``check_sqlite_database_path``
fails fast with an actionable message instead. These helpers only improve
diagnostics -- they never create directories nor change which URLs are accepted.

Issue: https://github.com/langflow-ai/langflow/issues/13634
"""

from pathlib import Path

import pytest
from langflow.services.database import service as database_service_module
from langflow.services.database.service import (
    check_sqlite_database_path,
    get_sqlite_database_file_path,
)


class TestGetSqliteDatabaseFilePath:
    """``get_sqlite_database_file_path`` extracts the on-disk path, or ``None``."""

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql+psycopg://localhost:5432/langflow",
            "postgresql://localhost/langflow",
            "mysql://localhost/langflow",
            "sqlitecloud+aiosqlite://localhost/langflow",
        ],
    )
    def test_non_sqlite_urls_return_none(self, url):
        assert get_sqlite_database_file_path(url) is None

    @pytest.mark.parametrize(
        "url",
        [
            "sqlite://",  # default in-memory
            "sqlite+aiosqlite://",
            "sqlite:///:memory:",
            "sqlite+aiosqlite:///:memory:",
            "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true",
            "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared&uri=true",
            "sqlite+aiosqlite:///file:memdb2?mode=memory&cache=shared&uri=1",
            "sqlite+aiosqlite:///file:memdb3?mode=memory&cache=shared&uri=%20true%20",
            "sqlite+aiosqlite:///file:memdup?mode=memory&cache=shared&uri=false&uri=false",
            "sqlite+aiosqlite:///file:memdb-vfs?vfs=memdb&uri=true",
            "sqlite+aiosqlite:///file:%3Amemory%3A?uri=true",
            "sqlite+aiosqlite:///file:%3amemory%3a?uri=true",
            "sqlite+aiosqlite:///file:encoded-mode?mode=%256demory&uri=true",
            "sqlite+aiosqlite:///file:encoded-vfs?vfs=%256demdb&uri=true",
            "sqlite+aiosqlite:///file:encoded-mode-key?%256dode=memory&uri=true",
            "sqlite+aiosqlite:///file:encoded-vfs-key?%2576fs=memdb&uri=true",
            "sqlite+aiosqlite:///file:delimited-mode?x=%26mode%3Dmemory&uri=true",
            "sqlite+aiosqlite:///file:delimited-vfs?x=%26vfs%3Dmemdb&uri=true",
            "sqlite+aiosqlite:///file:fragment-mode?mode=memory%23ignored&uri=true",
            "sqlite+aiosqlite:///file:nul-mode?mode%2500suffix=memory&uri=true",
            "sqlite+aiosqlite:///file:%3Amemory%3A%00suffix?uri=true",
            "sqlite+aiosqlite:///file://localhost?uri=true",
        ],
    )
    def test_in_memory_urls_return_none(self, url):
        assert get_sqlite_database_file_path(url) is None

    def test_relative_path_is_returned_verbatim(self):
        # The path is intentionally NOT resolved here so callers can echo it back.
        assert get_sqlite_database_file_path("sqlite:///db/langflow.db") == Path("db/langflow.db")

    def test_relative_dot_path_is_returned_verbatim(self):
        assert get_sqlite_database_file_path("sqlite:///./langflow.db") == Path("./langflow.db")

    def test_absolute_path_is_returned(self):
        assert get_sqlite_database_file_path("sqlite:////var/data/langflow.db") == Path("/var/data/langflow.db")

    def test_sanitized_async_driver_is_recognized(self):
        # ``_sanitize_database_url`` rewrites ``sqlite`` -> ``sqlite+aiosqlite``.
        assert get_sqlite_database_file_path("sqlite+aiosqlite:///db/langflow.db") == Path("db/langflow.db")

    @pytest.mark.parametrize(
        ("database_url", "expected"),
        [
            ("sqlite+aiosqlite:///relative.db?mode=memory&uri=true", Path("relative.db?mode=memory")),
            (
                "sqlite+aiosqlite:///:memory:?mode=memory&cache=shared&uri=true",
                Path(":memory:?cache=shared&mode=memory"),
            ),
            ("sqlite+aiosqlite:///?mode=memory&uri=true", Path("?mode=memory")),
            ("sqlite+aiosqlite://?uri=true", Path("None")),
        ],
    )
    def test_non_file_uri_options_remain_part_of_the_filename(self, database_url, expected):
        assert get_sqlite_database_file_path(database_url) == expected

    @pytest.mark.parametrize(
        ("database_url", "expected"),
        [
            ("sqlite+aiosqlite:///file:upper-mode.db?Mode=memory&uri=true", Path("upper-mode.db")),
            ("sqlite+aiosqlite:///file:upper-vfs.db?Vfs=memdb&uri=true", Path("upper-vfs.db")),
            (
                "sqlite+aiosqlite:///file:encoded-upper-mode.db?%254Dode=memory&uri=true",
                Path("encoded-upper-mode.db"),
            ),
            (
                "sqlite+aiosqlite:///file:encoded-upper-vfs.db?%2556fs=memdb&uri=true",
                Path("encoded-upper-vfs.db"),
            ),
            (
                "sqlite+aiosqlite:///file:mode-override.db?%256dode=memory&mode=rwc&uri=true",
                Path("mode-override.db"),
            ),
            (
                "sqlite+aiosqlite:///file:vfs-override.db?%2576fs=memdb&vfs=unix&uri=true",
                Path("vfs-override.db"),
            ),
            ("sqlite+aiosqlite:///file:tab-mode.db?mo%09de=memory&uri=true", Path("tab-mode.db")),
            ("sqlite+aiosqlite:///file:cr-mode.db?mo%0Dde=memory&uri=true", Path("cr-mode.db")),
            ("sqlite+aiosqlite:///file:lf-vfs.db?v%0Afs=memdb&uri=true", Path("lf-vfs.db")),
            ("sqlite+aiosqlite:///file:path\tname.db?uri=true", Path("path\tname.db")),
        ],
    )
    def test_file_uri_memory_options_are_case_sensitive_and_last_value_wins(self, database_url, expected):
        assert get_sqlite_database_file_path(database_url) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("sqlite+aiosqlite:///file:/var/data/langflow%20prod.db?uri=yes", Path("/var/data/langflow prod.db")),
            ("sqlite+aiosqlite:///file://localhost/var/data/langflow.db?uri=true", Path("/var/data/langflow.db")),
            (
                "sqlite+aiosqlite:///file://LOCALHOST/var/data/langflow.db?uri=true",
                Path("//LOCALHOST/var/data/langflow.db"),
            ),
            (
                "sqlite+aiosqlite:///file://local%68ost/var/data/langflow.db?uri=true",
                Path("//localhost/var/data/langflow.db"),
            ),
            (
                "sqlite+aiosqlite:///file://server%00suffix/share/langflow.db?uri=true",
                Path("//server"),
            ),
        ],
    )
    def test_file_uri_returns_the_underlying_absolute_path(self, url, expected):
        assert get_sqlite_database_file_path(url) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("sqlite+aiosqlite:///file:///C%3A/data/langflow.db?uri=true", r"C:\data\langflow.db"),
            ("sqlite+aiosqlite:///file:///C%3A/data%2520literal.db?uri=true", r"C:\data%20literal.db"),
            ("sqlite+aiosqlite:///file:path%09name.db?uri=true", "path\tname.db"),
            ("sqlite+aiosqlite:///file://server/share/langflow.db?uri=true", r"\\server\share\langflow.db"),
            (
                "sqlite+aiosqlite:///file:%2F%2Flocalhost%2Fshare%2Flangflow.db?uri=true",
                r"\\localhost\share\langflow.db",
            ),
        ],
    )
    def test_file_uri_decodes_before_windows_path_conversion(self, monkeypatch, url, expected):
        monkeypatch.setattr(database_service_module.sys, "platform", "win32")

        assert str(get_sqlite_database_file_path(url)) == expected


class TestCheckSqliteDatabasePath:
    """``check_sqlite_database_path`` is a no-op unless a SQLite parent dir is missing."""

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql+psycopg://localhost:5432/langflow",
            "sqlite://",
            "sqlite:///:memory:",
        ],
    )
    def test_no_raise_for_non_file_urls(self, url):
        # Should not raise even though e.g. the postgres "database" name has no
        # parent directory on disk.
        check_sqlite_database_path(url)

    def test_no_raise_when_absolute_parent_exists(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'langflow.db'}"
        check_sqlite_database_path(url)

    def test_no_raise_for_relative_existing_parent(self, tmp_path, monkeypatch):
        # The documented default ``sqlite:///./langflow.db`` resolves its parent
        # to the CWD, which always exists -- it must keep working.
        monkeypatch.chdir(tmp_path)
        check_sqlite_database_path("sqlite:///./langflow.db")

    def test_raises_for_absolute_missing_parent(self, tmp_path):
        missing = tmp_path / "does_not_exist" / "langflow.db"
        url = f"sqlite:///{missing}"
        with pytest.raises(ValueError, match="parent directory") as exc_info:
            check_sqlite_database_path(url)
        message = str(exc_info.value)
        assert str(missing) in message
        assert "Create the directory" in message
        # The absolute branch must not talk about the working directory.
        assert "working directory" not in message

    def test_raises_for_relative_missing_subdirectory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="parent directory") as exc_info:
            check_sqlite_database_path("sqlite:///db/langflow.db")
        message = str(exc_info.value)
        # The message must point at the resolved location and explain CWD anchoring.
        assert str(tmp_path / "db") in message
        assert "working directory" in message
        assert str(tmp_path) in message
        assert "absolute" in message

    def test_does_not_create_directories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError):  # noqa: PT011 - message asserted elsewhere
            check_sqlite_database_path("sqlite:///db/langflow.db")
        # The diagnostic must be side-effect free.
        assert not (tmp_path / "db").exists()


class TestInitializeDatabaseWiring:
    """``initialize_database`` runs the diagnostic before attempting creation."""

    async def test_relative_missing_dir_fails_fast_instead_of_opaque_error(self, tmp_path, monkeypatch):
        from langflow.services.database import utils as db_utils

        monkeypatch.chdir(tmp_path)

        class _StubDatabaseService:
            database_url = "sqlite+aiosqlite:///db/langflow.db"

            async def ensure_postgresql_version(self):
                return None

            async def create_db_and_tables(self):  # pragma: no cover - must not be reached
                pytest.fail("create_db_and_tables should not run when the path is invalid")

        monkeypatch.setattr("langflow.services.deps.get_db_service", lambda: _StubDatabaseService())

        # Fails fast with the clear diagnostic, not the opaque "Error creating DB and tables".
        with pytest.raises(ValueError, match="parent directory") as exc_info:
            await db_utils.initialize_database()
        assert "Error creating DB and tables" not in str(exc_info.value)
