"""Tests for the working-directory isolation strategies.

The shell MCP server is a single subprocess shared by every flow on a
Langflow backend. With a shared working directory (default ``shared``),
two tenants reading/writing the same path can leak files across each
other -- a critical issue for multi-user deployments. The ``ephemeral``
strategy hands every call its own ``tempfile.TemporaryDirectory`` under
the configured base, deleted after the call returns; tenants never see
each other's files.
"""

from __future__ import annotations

from pathlib import Path

from lfx.mcp.shell.working_directory_strategy import (
    EphemeralStrategy,
    SharedStrategy,
    build_strategy,
)


class TestSharedStrategy:
    def test_should_yield_configured_directory(self, tmp_path: Path) -> None:
        strategy = SharedStrategy(base_directory=str(tmp_path.resolve()))
        with strategy.acquire() as workdir:
            assert Path(workdir) == tmp_path.resolve()

    def test_should_persist_files_across_calls(self, tmp_path: Path) -> None:
        """A shared directory keeps files between calls.

        This is the whole point of ``shared`` (and the whole risk in multi-tenant).
        """
        strategy = SharedStrategy(base_directory=str(tmp_path.resolve()))
        with strategy.acquire() as workdir1:
            (Path(workdir1) / "marker.txt").write_text("hello")
        with strategy.acquire() as workdir2:
            assert (Path(workdir2) / "marker.txt").read_text() == "hello"


class TestEphemeralStrategy:
    def test_should_yield_directory_under_base(self, tmp_path: Path) -> None:
        strategy = EphemeralStrategy(base_directory=str(tmp_path.resolve()))
        with strategy.acquire() as workdir:
            wd_path = Path(workdir).resolve()
            assert wd_path != tmp_path.resolve()
            assert wd_path.parent == tmp_path.resolve()
            assert wd_path.is_dir()

    def test_should_delete_directory_after_release(self, tmp_path: Path) -> None:
        strategy = EphemeralStrategy(base_directory=str(tmp_path.resolve()))
        with strategy.acquire() as workdir:
            captured = Path(workdir)
            assert captured.is_dir()
        assert not captured.exists(), (
            "ephemeral working directory must be deleted after the call returns"
        )

    def test_should_isolate_files_between_calls(self, tmp_path: Path) -> None:
        """Two consecutive calls must NEVER see each other's files."""
        strategy = EphemeralStrategy(base_directory=str(tmp_path.resolve()))
        with strategy.acquire() as workdir1:
            (Path(workdir1) / "secret.txt").write_text("user-a-data")
        with strategy.acquire() as workdir2:
            assert not (Path(workdir2) / "secret.txt").exists()

    def test_should_isolate_concurrent_calls(self, tmp_path: Path) -> None:
        """Two parallel acquires must yield distinct directories."""
        strategy = EphemeralStrategy(base_directory=str(tmp_path.resolve()))
        with strategy.acquire() as wd1, strategy.acquire() as wd2:
            assert Path(wd1).resolve() != Path(wd2).resolve()
            (Path(wd1) / "a.txt").write_text("a")
            (Path(wd2) / "b.txt").write_text("b")
            assert not (Path(wd1) / "b.txt").exists()
            assert not (Path(wd2) / "a.txt").exists()


class TestBuildStrategy:
    def test_should_build_shared_by_default(self, tmp_path: Path) -> None:
        from lfx.mcp.shell.shell_config import IsolationMode

        strategy = build_strategy(IsolationMode.SHARED, base_directory=str(tmp_path))
        assert isinstance(strategy, SharedStrategy)

    def test_should_build_ephemeral_when_requested(self, tmp_path: Path) -> None:
        from lfx.mcp.shell.shell_config import IsolationMode

        strategy = build_strategy(IsolationMode.EPHEMERAL, base_directory=str(tmp_path))
        assert isinstance(strategy, EphemeralStrategy)
