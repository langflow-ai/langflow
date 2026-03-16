"""Unit tests for MCP Composer Service Windows-specific functionality."""

# ruff: noqa: SIM115, SIM117

import asyncio
import contextlib
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.services.mcp_composer.service import MCPComposerService, MCPComposerStartupError


@pytest.fixture
def mcp_service():
    """Create an MCP Composer service instance for testing."""
    return MCPComposerService()


class TestWindowsZombieProcessDetection:
    """Test Windows-specific zombie process detection using PowerShell."""

    @pytest.mark.asyncio
    async def test_kill_zombie_mcp_processes_windows_no_processes(self, mcp_service):
        """Test that PowerShell command runs when no zombie processes found."""
        with patch("platform.system", return_value="Windows"), patch("asyncio.to_thread") as mock_to_thread:
            # Mock PowerShell returning empty result (no processes)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_to_thread.return_value = mock_result

            result = await mcp_service._kill_zombie_mcp_processes(2000)

            # Should return False since no processes were killed
            assert result is False
            # Verify PowerShell was called (not wmic)
            assert mock_to_thread.called
            # Access args correctly - call_args is a tuple (args, kwargs)
            call_args = mock_to_thread.call_args.args
            assert call_args[1][0] == "powershell.exe"

    @pytest.mark.asyncio
    async def test_kill_zombie_mcp_processes_windows_single_process(self, mcp_service):
        """Test that single zombie process is detected and killed via PowerShell."""
        with patch("platform.system", return_value="Windows"), patch("asyncio.to_thread") as mock_to_thread:
            # Mock PowerShell returning single process as JSON object
            zombie_pid = 12345
            ps_output = json.dumps({"ProcessId": zombie_pid, "CommandLine": "python mcp-composer --port 2000"})

            # First call: netstat (no processes on port)
            mock_netstat_result = MagicMock()
            mock_netstat_result.returncode = 0
            mock_netstat_result.stdout = ""

            # Second call: PowerShell Get-WmiObject
            mock_ps_result = MagicMock()
            mock_ps_result.returncode = 0
            mock_ps_result.stdout = ps_output

            # Third call: taskkill
            mock_kill_result = MagicMock()
            mock_kill_result.returncode = 0

            mock_to_thread.side_effect = [mock_netstat_result, mock_ps_result, mock_kill_result]

            result = await mcp_service._kill_zombie_mcp_processes(2000)

            # Should return True since process was killed
            assert result is True
            # Verify three calls: netstat + PowerShell + taskkill
            assert mock_to_thread.call_count == 3

    @pytest.mark.asyncio
    async def test_kill_zombie_mcp_processes_windows_multiple_processes(self, mcp_service):
        """Test that multiple zombie processes are detected and killed."""
        with patch("platform.system", return_value="Windows"), patch("asyncio.to_thread") as mock_to_thread:
            # Mock PowerShell returning multiple processes as JSON array
            ps_output = json.dumps(
                [
                    {"ProcessId": 12345, "CommandLine": "python mcp-composer --port 2000"},
                    {"ProcessId": 67890, "CommandLine": "python mcp-composer --port=2000"},
                ]
            )

            # First call: netstat (no processes on port)
            mock_netstat_result = MagicMock()
            mock_netstat_result.returncode = 0
            mock_netstat_result.stdout = ""

            # Second call: PowerShell Get-WmiObject
            mock_ps_result = MagicMock()
            mock_ps_result.returncode = 0
            mock_ps_result.stdout = ps_output

            # Mock successful kills
            mock_kill_result = MagicMock()
            mock_kill_result.returncode = 0

            mock_to_thread.side_effect = [
                mock_netstat_result,
                mock_ps_result,
                mock_kill_result,
                mock_kill_result,
            ]

            result = await mcp_service._kill_zombie_mcp_processes(2000)

            assert result is True
            # Verify netstat + PowerShell + 2 taskkill calls
            assert mock_to_thread.call_count == 4

    @pytest.mark.asyncio
    async def test_kill_zombie_mcp_processes_windows_powershell_timeout(self, mcp_service):
        """Test that PowerShell timeout is handled gracefully."""
        with (
            patch("platform.system", return_value="Windows"),
            patch("asyncio.to_thread", side_effect=asyncio.TimeoutError("PowerShell timed out")),
        ):
            # Should not raise, just return False
            result = await mcp_service._kill_zombie_mcp_processes(2000)
            assert result is False

    @pytest.mark.asyncio
    async def test_kill_zombie_mcp_processes_windows_invalid_json(self, mcp_service):
        """Test that invalid JSON from PowerShell is handled gracefully."""
        with patch("platform.system", return_value="Windows"), patch("asyncio.to_thread") as mock_to_thread:
            mock_ps_result = MagicMock()
            mock_ps_result.returncode = 0
            mock_ps_result.stdout = "invalid json {{"
            mock_to_thread.return_value = mock_ps_result

            # Should not raise, just return False
            result = await mcp_service._kill_zombie_mcp_processes(2000)
            assert result is False

    @pytest.mark.asyncio
    async def test_kill_zombie_mcp_processes_windows_skips_tracked_pids(self, mcp_service):
        """Test that processes tracked by service are not killed."""
        with patch("platform.system", return_value="Windows"):
            tracked_pid = 12345
            # Register PID as tracked
            mcp_service._pid_to_project[tracked_pid] = "test-project"

            with patch("asyncio.to_thread") as mock_to_thread:
                ps_output = json.dumps({"ProcessId": tracked_pid, "CommandLine": "python mcp-composer --port 2000"})

                # First call: netstat (no processes on port)
                mock_netstat_result = MagicMock()
                mock_netstat_result.returncode = 0
                mock_netstat_result.stdout = ""

                # Second call: PowerShell Get-WmiObject
                mock_ps_result = MagicMock()
                mock_ps_result.returncode = 0
                mock_ps_result.stdout = ps_output

                mock_to_thread.side_effect = [mock_netstat_result, mock_ps_result]

                result = await mcp_service._kill_zombie_mcp_processes(2000)

                # Should return False since tracked PID was skipped
                assert result is False
                # netstat + PowerShell call, no taskkill (because PID is tracked)
                assert mock_to_thread.call_count == 2

    @pytest.mark.asyncio
    async def test_kill_zombie_mcp_processes_non_fatal_on_error(self, mcp_service):
        """Test that zombie cleanup errors are non-fatal (wrapped in try-catch)."""
        with (
            patch("platform.system", return_value="Windows"),
            patch("asyncio.to_thread", side_effect=Exception("Test error")),
        ):
            # Should not raise exception
            result = await mcp_service._kill_zombie_mcp_processes(2000)
            assert result is False


class TestWindowsTempFileHandling:
    """Test Windows-specific temp file handling for stdout/stderr."""

    @pytest.mark.asyncio
    async def test_windows_uses_temp_files_instead_of_pipes(self, mcp_service):
        """Test that Windows creates temp files for stdout/stderr instead of pipes."""
        project_id = "test-project"
        port = 2000

        with (
            patch("platform.system", return_value="Windows"),
            patch("subprocess.Popen") as mock_popen,
            patch("tempfile.NamedTemporaryFile") as mock_tempfile,
        ):
            # Mock temp file creation
            mock_stdout_file = MagicMock()
            mock_stdout_file.name = tempfile.gettempdir() + "/mcp_composer_test_stdout.log"
            mock_stderr_file = MagicMock()
            mock_stderr_file.name = tempfile.gettempdir() + "/mcp_composer_test_stderr.log"

            mock_tempfile.side_effect = [mock_stdout_file, mock_stderr_file]

            # Mock process
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Process running
            mock_popen.return_value = mock_process

            with patch.object(mcp_service, "_is_port_available", return_value=True):
                auth_config = {
                    "auth_type": "oauth",
                    "oauth_host": "localhost",
                    "oauth_port": str(port),
                    "oauth_server_url": f"http://localhost:{port}",
                    "oauth_client_id": "test",
                    "oauth_client_secret": "test",
                    "oauth_auth_url": "http://test",
                    "oauth_token_url": "http://test",
                }

                with contextlib.suppress(Exception):
                    await mcp_service._start_project_composer_process(
                        project_id=project_id,
                        host="localhost",
                        port=port,
                        streamable_http_url="http://test",
                        auth_config=auth_config,
                        max_startup_checks=1,
                        startup_delay=0.1,
                    )

                # Verify temp files were created
                assert mock_tempfile.call_count == 2
                # Verify Popen was called with file handles, not PIPE
                popen_call = mock_popen.call_args
                assert popen_call[1]["stdout"] == mock_stdout_file
                assert popen_call[1]["stderr"] == mock_stderr_file

    @pytest.mark.asyncio
    async def test_windows_temp_files_are_read_async(self, mcp_service):
        """Test that temp files are read using asyncio.to_thread (non-blocking)."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process died

        # Create real temp files to test reading
        stdout_file = tempfile.NamedTemporaryFile(mode="w+b", delete=False, suffix=".log")
        stderr_file = tempfile.NamedTemporaryFile(mode="w+b", delete=False, suffix=".log")

        try:
            # Write test data
            stdout_file.write(b"stdout test data")
            stderr_file.write(b"stderr test data")
            stdout_file.close()
            stderr_file.close()

            stdout, stderr, _error_msg = await mcp_service._read_process_output_and_extract_error(
                mock_process, oauth_server_url=None, timeout=2.0, stdout_file=stdout_file, stderr_file=stderr_file
            )

            # Verify content was read
            assert "stdout test data" in stdout
            assert "stderr test data" in stderr

            # Verify files were cleaned up
            assert not Path(stdout_file.name).exists()
            assert not Path(stderr_file.name).exists()

        finally:
            # Cleanup in case test fails
            for f in [stdout_file.name, stderr_file.name]:
                with contextlib.suppress(FileNotFoundError):
                    Path(f).unlink()

    @pytest.mark.asyncio
    async def test_windows_temp_files_cleanup_on_success(self, mcp_service):
        """Test that temp files are cleaned up when process starts successfully."""
        project_id = "test-project"
        port = 2000

        with patch("platform.system", return_value="Windows"):
            # Create real temp files
            stdout_file = tempfile.NamedTemporaryFile(mode="w+b", delete=False)
            stderr_file = tempfile.NamedTemporaryFile(mode="w+b", delete=False)
            stdout_file.close()
            stderr_file.close()

            try:
                with patch("subprocess.Popen") as mock_popen:
                    with patch("tempfile.NamedTemporaryFile") as mock_tempfile:
                        mock_tempfile.side_effect = [stdout_file, stderr_file]

                        # Mock successful process startup
                        mock_process = MagicMock()
                        mock_process.pid = 12345
                        mock_process.poll.return_value = None
                        mock_popen.return_value = mock_process

                        with patch.object(mcp_service, "_is_port_available") as mock_port:
                            # First checks: not bound, then bound
                            mock_port.side_effect = [True, False]

                            auth_config = {
                                "auth_type": "oauth",
                                "oauth_host": "localhost",
                                "oauth_port": str(port),
                                "oauth_server_url": f"http://localhost:{port}",
                                "oauth_client_id": "test",
                                "oauth_client_secret": "test",
                                "oauth_auth_url": "http://test",
                                "oauth_token_url": "http://test",
                            }

                            process = await mcp_service._start_project_composer_process(
                                project_id=project_id,
                                host="localhost",
                                port=port,
                                streamable_http_url="http://test",
                                auth_config=auth_config,
                                max_startup_checks=2,
                                startup_delay=0.1,
                            )

                            # Verify files were cleaned up
                            assert not Path(stdout_file.name).exists()
                            assert not Path(stderr_file.name).exists()
                            assert process == mock_process

            finally:
                # Cleanup
                for f in [stdout_file.name, stderr_file.name]:
                    with contextlib.suppress(FileNotFoundError):
                        Path(f).unlink()

    @pytest.mark.asyncio
    async def test_non_windows_uses_pipes(self, mcp_service):
        """Test that non-Windows systems still use pipes (not temp files)."""
        project_id = "test-project"
        port = 2000

        with patch("platform.system", return_value="Linux"), patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            with patch.object(mcp_service, "_is_port_available", return_value=True):
                auth_config = {
                    "auth_type": "oauth",
                    "oauth_host": "localhost",
                    "oauth_port": str(port),
                    "oauth_server_url": f"http://localhost:{port}",
                    "oauth_client_id": "test",
                    "oauth_client_secret": "test",
                    "oauth_auth_url": "http://test",
                    "oauth_token_url": "http://test",
                }

                with contextlib.suppress(Exception):
                    await mcp_service._start_project_composer_process(
                        project_id=project_id,
                        host="localhost",
                        port=port,
                        streamable_http_url="http://test",
                        auth_config=auth_config,
                        max_startup_checks=1,
                        startup_delay=0.1,
                    )

                # Verify Popen was called with subprocess.PIPE
                popen_call = mock_popen.call_args
                assert popen_call[1]["stdout"] == subprocess.PIPE
                assert popen_call[1]["stderr"] == subprocess.PIPE


class TestIncreasedStartupTimeout:
    """Test that startup timeout was increased for Windows."""

    @pytest.mark.asyncio
    async def test_startup_timeout_is_80_seconds(self, mcp_service):
        """Test that max_startup_checks default is 40 * 2s = 80 seconds."""
        # Check default parameters
        import inspect

        sig = inspect.signature(mcp_service.start_project_composer)
        assert sig.parameters["max_startup_checks"].default == 40
        assert sig.parameters["startup_delay"].default == 2.0

        # Verify total timeout is 80 seconds
        assert 40 * 2.0 == 80.0

    @pytest.mark.asyncio
    async def test_retry_with_increased_timeout(self, mcp_service):
        """Test that retries use increased timeout (80s total per attempt)."""
        project_id = "test-project"

        with patch.object(mcp_service, "_start_project_composer_process") as mock_start:
            # Simulate failure
            mock_start.side_effect = MCPComposerStartupError("Test error", project_id)

            with patch.object(mcp_service, "_kill_zombie_mcp_processes", new=AsyncMock()):
                with patch.object(mcp_service, "_is_port_available", return_value=True):
                    mcp_service._start_locks[project_id] = asyncio.Lock()

                    auth_config = {
                        "auth_type": "oauth",
                        "oauth_host": "localhost",
                        "oauth_port": "2000",
                        "oauth_server_url": "http://localhost:2000",
                        "oauth_client_id": "test",
                        "oauth_client_secret": "test",
                        "oauth_auth_url": "http://test",
                        "oauth_token_url": "http://test",
                    }

                    with contextlib.suppress(Exception):
                        await mcp_service._do_start_project_composer(
                            project_id=project_id,
                            streamable_http_url="http://test",
                            auth_config=auth_config,
                            max_retries=3,
                        )

                    # Verify _start_project_composer_process was called with correct defaults
                    assert mock_start.call_count == 3
                    for call in mock_start.call_args_list:
                        # Check positional arguments (args) and keyword arguments (kwargs)
                        # max_startup_checks is the 6th argument (index 5) or in kwargs
                        # startup_delay is the 7th argument (index 6) or in kwargs
                        if "max_startup_checks" in call.kwargs:
                            assert call.kwargs["max_startup_checks"] == 40
                        else:
                            assert call.args[5] == 40

                        if "startup_delay" in call.kwargs:
                            assert call.kwargs["startup_delay"] == 2.0
                        else:
                            assert call.args[6] == 2.0


class TestStreamReadingAvoidance:
    """Test that stream.peek() blocking issue is avoided on Windows."""

    @pytest.mark.asyncio
    async def test_read_stream_non_blocking_returns_empty_on_windows(self, mcp_service):
        """Test that _read_stream_non_blocking returns empty string on Windows."""
        with patch("platform.system", return_value="Windows"):
            mock_stream = MagicMock()

            result = await mcp_service._read_stream_non_blocking(mock_stream, "stdout")

            # Should return empty string without trying to read
            assert result == ""
            # Verify no peek() or readline() was called
            assert not mock_stream.peek.called
            assert not mock_stream.readline.called

    @pytest.mark.asyncio
    async def test_read_stream_non_blocking_uses_select_on_unix(self, mcp_service):
        """Test that Unix systems use select.select() for non-blocking read."""
        with patch("platform.system", return_value="Linux"):
            with patch("select.select", return_value=([True], [], [])) as mock_select:
                mock_stream = MagicMock()
                mock_stream.readline.return_value = b"test output\n"

                result = await mcp_service._read_stream_non_blocking(mock_stream, "stdout")

                # Should use select and read line
                assert mock_select.called
                assert "test output" in result


class TestRetryRobustness:
    """Test that retry logic handles Windows-specific errors gracefully."""

    @pytest.mark.asyncio
    async def test_zombie_cleanup_failure_is_non_fatal_during_retry(self, mcp_service):
        """Test that zombie cleanup failure during retry doesn't stop retry attempts."""
        project_id = "test-project"

        call_count = 0

        async def mock_start_raises_once(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "First attempt failed"
                raise MCPComposerStartupError(msg, project_id)
            # Second attempt succeeds
            mock_process = MagicMock()
            mock_process.pid = 12345
            return mock_process

        with patch.object(mcp_service, "_start_project_composer_process", side_effect=mock_start_raises_once):
            # Zombie cleanup raises error
            with patch.object(mcp_service, "_kill_zombie_mcp_processes", side_effect=Exception("PowerShell error")):
                with patch.object(mcp_service, "_is_port_available", return_value=True):
                    mcp_service._start_locks[project_id] = asyncio.Lock()

                    auth_config = {
                        "auth_type": "oauth",
                        "oauth_host": "localhost",
                        "oauth_port": "2000",
                        "oauth_server_url": "http://localhost:2000",
                        "oauth_client_id": "test",
                        "oauth_client_secret": "test",
                        "oauth_auth_url": "http://test",
                        "oauth_token_url": "http://test",
                    }

                    # Should succeed on second attempt despite zombie cleanup failure
                    await mcp_service._do_start_project_composer(
                        project_id=project_id,
                        streamable_http_url="http://test",
                        auth_config=auth_config,
                        max_retries=2,
                        max_startup_checks=1,
                        startup_delay=0.1,
                    )

                    # Verify it retried successfully
                    assert call_count == 2
                    assert project_id in mcp_service.project_composers


@pytest.mark.asyncio
async def test_windows_legacy_sse_url_passthrough(mcp_service):
    """Ensure Windows composer starts propagate explicit legacy SSE URLs."""
    project_id = "windows-legacy"
    auth_config = {
        "auth_type": "oauth",
        "oauth_host": "localhost",
        "oauth_port": "9300",
        "oauth_server_url": "http://localhost:9300",
        "oauth_client_id": "legacy",
        "oauth_client_secret": "secret",
        "oauth_auth_url": "http://auth",
        "oauth_token_url": "http://token",
    }
    mcp_service._start_locks[project_id] = asyncio.Lock()
    mock_process = MagicMock(pid=2468)

    with patch.object(
        mcp_service,
        "_start_project_composer_process",
        new=AsyncMock(return_value=mock_process),
    ) as mock_start:
        await mcp_service._do_start_project_composer(
            project_id=project_id,
            streamable_http_url="http://windows/streamable",
            auth_config=auth_config,
            legacy_sse_url="http://windows/sse",
            max_retries=1,
            max_startup_checks=1,
        )

    mock_start.assert_awaited()
    assert mock_start.call_args.kwargs["legacy_sse_url"] == "http://windows/sse"


@pytest.mark.asyncio
async def test_windows_legacy_sse_url_defaults(mcp_service):
    """Ensure default legacy SSE URLs are derived when none supplied on Windows."""
    project_id = "windows-legacy-default"
    streamable_url = "http://windows/default"
    auth_config = {
        "auth_type": "oauth",
        "oauth_host": "localhost",
        "oauth_port": "9400",
        "oauth_server_url": "http://localhost:9400",
        "oauth_client_id": "legacy",
        "oauth_client_secret": "secret",
        "oauth_auth_url": "http://auth",
        "oauth_token_url": "http://token",
    }
    mcp_service._start_locks[project_id] = asyncio.Lock()
    mock_process = MagicMock(pid=1357)

    with patch.object(
        mcp_service,
        "_start_project_composer_process",
        new=AsyncMock(return_value=mock_process),
    ) as mock_start:
        await mcp_service._do_start_project_composer(
            project_id=project_id,
            streamable_http_url=streamable_url,
            auth_config=auth_config,
            max_retries=1,
            max_startup_checks=1,
        )

    mock_start.assert_awaited()
    assert mock_start.call_args.kwargs["legacy_sse_url"] == f"{streamable_url}/sse"
