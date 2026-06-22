"""Tests for Alembic migration-log path resolution and read-only resilience.

Regression coverage for https://github.com/langflow-ai/langflow/issues/11143:
the default Alembic log path resolved into the installed package directory,
which is read-only in hardened container/Kubernetes deployments (non-root user
or read-only root filesystem). Opening it for writing raised an unhandled
``OSError: [Errno 30] Read-only file system`` and crashed startup
(CrashLoopBackOff).

The fix:
1. Relative log paths resolve against the writable ``config_dir`` instead of the
   package directory (root cause).
2. Opening the log and initializing it both degrade gracefully to stdout when
   the target is not writable, since the migration log is diagnostic-only and
   must never abort startup (defense in depth).
"""

import errno
import os
import stat
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.database.service import DatabaseService


def _make_service(
    *,
    config_dir: str,
    alembic_log_file: str = "alembic/alembic.log",
    alembic_log_to_stdout: bool = False,
) -> DatabaseService:
    """Construct a DatabaseService with a mocked settings service.

    The engine is patched out (mirrors the existing Windows/Postgres tests);
    only the settings relevant to log-path resolution are populated.
    """
    mock_settings_service = MagicMock()
    settings = mock_settings_service.settings
    settings.database_url = "sqlite:///test.db"
    settings.database_connection_retry = False
    settings.sqlite_pragmas = {}
    settings.db_driver_connection_settings = None
    settings.db_connection_settings = {}
    settings.alembic_log_file = alembic_log_file
    settings.alembic_log_to_stdout = alembic_log_to_stdout
    settings.config_dir = config_dir

    with patch("langflow.services.database.service.create_async_engine", return_value=MagicMock()):
        return DatabaseService(mock_settings_service)


# ---------------------------------------------------------------------------
# Path resolution (root cause)
# ---------------------------------------------------------------------------


class TestAlembicLogPathResolution:
    def test_relative_path_resolves_under_config_dir_not_package(self, tmp_path):
        """A relative log path must resolve under the writable config_dir.

        It must NOT resolve into the installed langflow package directory, which
        is the read-only location that caused the crash.
        """
        import langflow

        service = _make_service(config_dir=str(tmp_path), alembic_log_file="alembic/alembic.log")

        assert service.alembic_log_path == tmp_path / "alembic" / "alembic.log"
        # Guard against regressing to the package directory.
        package_dir = Path(langflow.__file__).parent.resolve()
        assert package_dir not in service.alembic_log_path.resolve().parents

    def test_absolute_path_is_preserved(self, tmp_path):
        """An absolute LANGFLOW_ALEMBIC_LOG_FILE is used verbatim."""
        absolute = tmp_path / "custom" / "alembic.log"
        service = _make_service(config_dir=str(tmp_path), alembic_log_file=str(absolute))
        assert service.alembic_log_path == absolute

    def test_stdout_mode_yields_no_path(self, tmp_path):
        """When logging to stdout, no file path is resolved."""
        service = _make_service(config_dir=str(tmp_path), alembic_log_to_stdout=True)
        assert service.alembic_log_path is None


# ---------------------------------------------------------------------------
# _open_alembic_log_buffer (the actual crash point)
# ---------------------------------------------------------------------------


class TestOpenAlembicLogBuffer:
    def test_writable_path_opens_real_file(self, tmp_path):
        """On a writable filesystem the buffer is the real log file, not stdout."""
        service = _make_service(config_dir=str(tmp_path), alembic_log_file="alembic/alembic.log")
        with service._open_alembic_log_buffer() as buffer:
            assert buffer is not sys.stdout
            buffer.write("hello\n")
        assert service.alembic_log_path.exists()
        assert service.alembic_log_path.read_text(encoding="utf-8") == "hello\n"

    def test_stdout_mode_returns_stdout(self, tmp_path):
        service = _make_service(config_dir=str(tmp_path), alembic_log_to_stdout=True)
        with service._open_alembic_log_buffer() as buffer:
            assert buffer is sys.stdout

    def test_oserror_falls_back_to_stdout(self, tmp_path):
        """A read-only filesystem (EROFS) must fall back to stdout, not raise.

        This is the deterministic regression test for issue #11143: it does not
        depend on real filesystem permissions (which root bypasses in CI).
        """
        service = _make_service(config_dir=str(tmp_path), alembic_log_file="alembic.log")
        path_type = type(service.alembic_log_path)
        with (
            patch.object(path_type, "mkdir", return_value=None),
            patch.object(path_type, "open", side_effect=OSError(errno.EROFS, "Read-only file system")),
        ):
            ctx = service._open_alembic_log_buffer()
        with ctx as buffer:
            assert buffer is sys.stdout

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits do not restrict directory writes on Windows")
    def test_readonly_directory_falls_back_to_stdout(self, tmp_path):
        """End-to-end repro: a real read-only directory must not crash startup."""
        readonly_dir = tmp_path / "ro"
        readonly_dir.mkdir()
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            if os.access(readonly_dir, os.W_OK):
                pytest.skip("Filesystem does not enforce write permission (likely running as root)")
            service = _make_service(config_dir=str(readonly_dir), alembic_log_file="alembic.log")
            # Must not raise OSError: [Errno 30] Read-only file system.
            with service._open_alembic_log_buffer() as buffer:
                assert buffer is sys.stdout
        finally:
            readonly_dir.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# initialize_alembic_log_file resilience
# ---------------------------------------------------------------------------


class TestInitializeAlembicLogFile:
    async def test_creates_log_file_when_writable(self, tmp_path):
        service = _make_service(config_dir=str(tmp_path), alembic_log_file="alembic/alembic.log")
        await service.initialize_alembic_log_file()
        assert service.alembic_log_path.exists()

    async def test_stdout_mode_is_noop(self, tmp_path):
        service = _make_service(config_dir=str(tmp_path), alembic_log_to_stdout=True)
        # Should return immediately without touching the filesystem.
        await service.initialize_alembic_log_file()

    async def test_oserror_is_swallowed(self, tmp_path):
        """A read-only filesystem during init must not abort startup."""
        service = _make_service(config_dir=str(tmp_path), alembic_log_file="alembic.log")
        with patch("langflow.services.database.service.anyio.Path") as mock_anyio_path:
            instance = mock_anyio_path.return_value
            instance.mkdir = AsyncMock(side_effect=OSError(errno.EROFS, "Read-only file system"))
            instance.touch = AsyncMock()
            # Must not raise.
            await service.initialize_alembic_log_file()
            instance.mkdir.assert_awaited()
