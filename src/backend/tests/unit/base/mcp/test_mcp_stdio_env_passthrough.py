"""Tests for OS-essential env var passthrough in MCP stdio connections.

Why this exists: child MCP servers (notably `@wonderwhy-er/desktop-commander`)
call Node's `os.homedir()` at module load. On Windows, `os.homedir()` reads
`USERPROFILE` (or `HOMEDRIVE`+`HOMEPATH`); on Unix it reads `HOME` first and
only then falls back to a `getpwuid()` lookup.

Before this fix, `MCPStdioClient._connect_to_server` passed only `{DEBUG, PATH}`
into the subprocess env. On Windows that left `os.homedir()` returning `null`,
which then crashed any server that built paths from `path.join(USER_HOME, ...)`.
The MCP SDK then surfaced the crash as an opaque "Connection closed" /
TaskGroup sub-exception — same error users saw for the shell-execution server.

This file pins the curated passthrough so the next person who tightens the env
list doesn't accidentally re-strip `USERPROFILE` / `HOME` and resurrect the
Windows bug.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.mcp.util import MCPStdioClient


@pytest.fixture
def stdio_client():
    return MCPStdioClient()


async def _connect_capturing_env(client: MCPStdioClient, *, command: str = "echo hi") -> dict[str, str]:
    """Capture the env dict the StdioServerParameters was built with.

    Drives `_connect_to_server` far enough that StdioServerParameters is built,
    then returns the env dict — without launching a subprocess.
    """
    with patch.object(
        client,
        "_get_or_create_session",
        new=AsyncMock(return_value=SimpleNamespace(list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])))),
    ):
        await client._connect_to_server(command)
    return dict(client._connection_params.env)


class TestWindowsEnvPassthrough:
    """When the host is Windows, `USERPROFILE` etc must reach the child."""

    async def test_should_pass_userprofile_when_present_on_windows(self, stdio_client):
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Windows"),
            patch.dict(
                "os.environ",
                {"PATH": "C:/Windows", "USERPROFILE": r"C:\Users\test"},
                clear=True,
            ),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert env.get("USERPROFILE") == r"C:\Users\test"

    async def test_should_pass_homedrive_and_homepath_fallbacks_on_windows(self, stdio_client):
        """`os.homedir()` falls back to HOMEDRIVE+HOMEPATH when USERPROFILE is absent."""
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Windows"),
            patch.dict(
                "os.environ",
                {"PATH": "C:/Windows", "HOMEDRIVE": "C:", "HOMEPATH": r"\Users\test"},
                clear=True,
            ),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert env.get("HOMEDRIVE") == "C:"
        assert env.get("HOMEPATH") == r"\Users\test"

    async def test_should_pass_appdata_and_temp_on_windows(self, stdio_client):
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Windows"),
            patch.dict(
                "os.environ",
                {
                    "PATH": "C:/Windows",
                    "APPDATA": r"C:\Users\test\AppData\Roaming",
                    "LOCALAPPDATA": r"C:\Users\test\AppData\Local",
                    "TEMP": r"C:\Users\test\AppData\Local\Temp",
                    "TMP": r"C:\Users\test\AppData\Local\Temp",
                },
                clear=True,
            ),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert env.get("APPDATA", "").endswith("Roaming")
        assert env.get("LOCALAPPDATA", "").endswith("Local")
        assert env.get("TEMP", "").endswith("Temp")
        assert env.get("TMP", "").endswith("Temp")

    async def test_should_pass_pathext_so_cmd_resolves_npx_cmd_on_windows(self, stdio_client):
        """Without PATHEXT, `cmd /c npx ...` can't find `npx.cmd` in PATH."""
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Windows"),
            patch.dict(
                "os.environ",
                {"PATH": "C:/Windows", "PATHEXT": ".COM;.EXE;.BAT;.CMD"},
                clear=True,
            ),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert ".CMD" in env.get("PATHEXT", "")

    async def test_should_omit_windows_vars_when_absent_from_host_environ(self, stdio_client):
        """Only forward what's actually present.

        If the host doesn't have a Windows var (e.g. running tests on Unix),
        we don't fabricate one.
        """
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Windows"),
            patch.dict("os.environ", {"PATH": "C:/Windows"}, clear=True),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert "USERPROFILE" not in env
        assert "APPDATA" not in env


class TestUnixEnvPassthrough:
    """Forward Unix-essential env vars to the subprocess.

    On Unix, `HOME` falls back to `getpwuid()` but many tools still read it
    from env first. Forwarding it avoids per-tool quirks.
    """

    async def test_should_pass_home_when_present_on_unix(self, stdio_client):
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Linux"),
            patch.dict("os.environ", {"PATH": "/usr/bin", "HOME": "/home/test"}, clear=True),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert env.get("HOME") == "/home/test"

    async def test_should_pass_lang_for_locale_aware_tools_on_unix(self, stdio_client):
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Darwin"),
            patch.dict(
                "os.environ",
                {"PATH": "/usr/bin", "HOME": "/Users/test", "LANG": "en_US.UTF-8"},
                clear=True,
            ),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert env.get("LANG") == "en_US.UTF-8"

    async def test_should_not_pass_windows_vars_when_running_on_unix(self, stdio_client):
        """Windows-only vars must not bleed through on Unix hosts."""
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Linux"),
            patch.dict(
                "os.environ",
                {"PATH": "/usr/bin", "HOME": "/h", "USERPROFILE": "should-not-leak"},
                clear=True,
            ),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert "USERPROFILE" not in env


class TestUserSuppliedEnvWins:
    """User-supplied env (from server config) must override host passthrough."""

    async def test_should_let_user_env_override_passthrough_value(self, stdio_client):
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Linux"),
            patch.dict(
                "os.environ",
                {"PATH": "/usr/bin", "HOME": "/host/home"},
                clear=True,
            ),
            patch.object(
                stdio_client,
                "_get_or_create_session",
                new=AsyncMock(
                    return_value=SimpleNamespace(list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])))
                ),
            ),
        ):
            await stdio_client._connect_to_server("echo hi", env={"HOME": "/user/override"})
        assert dict(stdio_client._connection_params.env).get("HOME") == "/user/override"


class TestLegacyEnvKeysPreserved:
    """Don't drop keys the previous behavior guaranteed (avoids silent regressions)."""

    async def test_should_still_pass_path_and_debug(self, stdio_client):
        with (
            patch("lfx.base.mcp.util.platform.system", return_value="Linux"),
            patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True),
        ):
            env = await _connect_capturing_env(stdio_client)
        assert env.get("PATH") == "/usr/bin"
        assert env.get("DEBUG") == "true"
