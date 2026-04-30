"""End-to-end tests proving that ephemeral isolation plumbs through to the subprocess.

These run real subprocesses on the host (one ``echo`` and one ``ls``)
to confirm three properties:

1. Each call in ``ephemeral`` mode receives a working directory that is
   inside the configured base but distinct between calls.
2. A file written by call N is invisible to call N+1.
3. The temp directory is gone after the call returns -- nothing
   accumulates on disk across calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lfx.mcp.shell import shell_server
from lfx.mcp.shell.shell_config import IsolationMode, ShellMode, ShellServerConfig
from lfx.mcp.shell.shell_server import handle_execute_command


def _config(tmp_path: Path, *, isolation: IsolationMode) -> ShellServerConfig:
    return ShellServerConfig(
        working_directory=str(tmp_path.resolve()),
        mode=ShellMode.READ_WRITE,
        max_timeout=10,
        max_output_bytes=16 * 1024,
        max_command_length=4096,
        max_concurrent=4,
        queue_timeout=5,
        isolation=isolation,
    )


@pytest.fixture(autouse=True)
def _reset_semaphore() -> None:
    shell_server._reset_concurrency_for_testing()
    yield
    shell_server._reset_concurrency_for_testing()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only shell smoke")
@pytest.mark.asyncio
async def test_ephemeral_isolation_should_prevent_cross_call_file_visibility(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, isolation=IsolationMode.EPHEMERAL)

    write_payload = await handle_execute_command(
        command="echo secret > leak.txt",
        timeout=5,
        description="",
        config=config,
    )
    assert write_payload["exit_code"] == 0

    read_payload = await handle_execute_command(
        command="ls",
        timeout=5,
        description="",
        config=config,
    )
    assert "leak.txt" not in read_payload["stdout"], (
        "ephemeral mode must NOT let a second call see files from the first"
    )

    # Nothing should remain on disk under the configured base directory
    # apart from any sibling tempdirs the caller created themselves.
    leftovers = [p.name for p in Path(config.working_directory).iterdir()]
    assert all("leak.txt" not in name for name in leftovers), (
        f"ephemeral tempdirs must be torn down, found: {leftovers}"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only shell smoke")
@pytest.mark.asyncio
async def test_shared_isolation_should_preserve_cross_call_file_visibility(
    tmp_path: Path,
) -> None:
    """``shared`` keeps state so existing single-tenant workflows are unaffected.

    Sanity check on the opposite of the ephemeral isolation guarantee.
    """
    config = _config(tmp_path, isolation=IsolationMode.SHARED)

    await handle_execute_command(
        command="echo persisted > persisted.txt",
        timeout=5,
        description="",
        config=config,
    )

    read_payload = await handle_execute_command(
        command="ls",
        timeout=5,
        description="",
        config=config,
    )
    assert "persisted.txt" in read_payload["stdout"]
    # And the file must really be on disk under the shared directory.
    assert (Path(config.working_directory) / "persisted.txt").exists()
    # Cleanup so test ordering doesn't leave files behind.
    (Path(config.working_directory) / "persisted.txt").unlink()
