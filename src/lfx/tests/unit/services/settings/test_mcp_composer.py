"""Unit tests for MCP Composer Service port management and process killing."""

import asyncio
import contextlib
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.services.mcp_composer.service import MCPComposerPortError, MCPComposerService


@pytest.fixture
def mcp_service():
    """Create an MCP Composer service instance for testing."""
    return MCPComposerService()


class TestPortAvailability:
    """Test port availability checking."""

    def test_is_port_available_when_free(self, mcp_service):
        """Test that is_port_available returns True for an available port."""
        # Use a very high port number that's likely to be free
        test_port = 59999
        assert mcp_service._is_port_available(test_port) is True

    def test_is_port_available_when_in_use(self, mcp_service):
        """Test that is_port_available returns False when port is in use."""
        # Create a socket that binds to a port
        test_port = 59998
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("0.0.0.0", test_port))
            sock.listen(1)
            # Port should now be unavailable
            assert mcp_service._is_port_available(test_port) is False
        finally:
            sock.close()


class TestKillProcessOnPort:
    """Test process killing functionality."""

    @pytest.mark.asyncio
    async def test_kill_process_on_port_no_process(self, mcp_service):
        """Test that _kill_process_on_port returns False when no process is found."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock lsof returning no processes
            mock_result = MagicMock()
            mock_result.returncode = 1  # lsof returns 1 when no matches
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_to_thread.return_value = mock_result

            result = await mcp_service._kill_process_on_port(9999)
            assert result is False

    @pytest.mark.asyncio
    async def test_kill_process_on_port_success(self, mcp_service):
        """Test that _kill_process_on_port successfully kills a process."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock lsof returning a PID
            mock_lsof_result = MagicMock()
            mock_lsof_result.returncode = 0
            mock_lsof_result.stdout = "12345\n"
            mock_lsof_result.stderr = ""

            # Mock kill command succeeding
            mock_kill_result = MagicMock()
            mock_kill_result.returncode = 0
            mock_kill_result.stdout = ""
            mock_kill_result.stderr = ""

            # Set up side effects for two calls: lsof, then kill
            mock_to_thread.side_effect = [mock_lsof_result, mock_kill_result]

            result = await mcp_service._kill_process_on_port(9000)
            assert result is True
            assert mock_to_thread.call_count == 2

    @pytest.mark.asyncio
    async def test_kill_process_on_port_multiple_pids(self, mcp_service):
        """Test that _kill_process_on_port handles multiple PIDs."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock lsof returning multiple PIDs
            mock_lsof_result = MagicMock()
            mock_lsof_result.returncode = 0
            mock_lsof_result.stdout = "12345\n67890\n"
            mock_lsof_result.stderr = ""

            # Mock kill command succeeding for first PID
            mock_kill_result = MagicMock()
            mock_kill_result.returncode = 0

            mock_to_thread.side_effect = [mock_lsof_result, mock_kill_result]

            result = await mcp_service._kill_process_on_port(9000)
            assert result is True

    @pytest.mark.asyncio
    async def test_kill_process_on_port_kill_fails(self, mcp_service):
        """Test that _kill_process_on_port handles kill command failure."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Mock lsof returning a PID
            mock_lsof_result = MagicMock()
            mock_lsof_result.returncode = 0
            mock_lsof_result.stdout = "12345\n"
            mock_lsof_result.stderr = ""

            # Mock kill command failing
            mock_kill_result = MagicMock()
            mock_kill_result.returncode = 1

            mock_to_thread.side_effect = [mock_lsof_result, mock_kill_result]

            result = await mcp_service._kill_process_on_port(9000)
            assert result is False

    @pytest.mark.asyncio
    async def test_kill_process_on_port_exception_handling(self, mcp_service):
        """Test that _kill_process_on_port handles exceptions gracefully."""
        with patch("asyncio.to_thread", side_effect=Exception("Test error")):
            result = await mcp_service._kill_process_on_port(9000)
            assert result is False


class TestAuthConfigChanges:
    """Test authentication configuration change detection."""

    def test_has_auth_config_changed_port_changed(self, mcp_service):
        """Test that port change is detected."""
        existing_auth = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": "9000",
            "oauth_server_url": "http://localhost:9000",
        }
        new_auth = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": "9001",
            "oauth_server_url": "http://localhost:9001",
        }

        assert mcp_service._has_auth_config_changed(existing_auth, new_auth) is True

    def test_has_auth_config_changed_no_change(self, mcp_service):
        """Test that identical configs are not detected as changed."""
        existing_auth = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": "9000",
            "oauth_server_url": "http://localhost:9000",
        }
        new_auth = existing_auth.copy()

        assert mcp_service._has_auth_config_changed(existing_auth, new_auth) is False

    def test_has_auth_config_changed_auth_type_changed(self, mcp_service):
        """Test that auth type change is detected."""
        existing_auth = {"auth_type": "oauth", "oauth_port": "9000"}
        new_auth = {"auth_type": "apikey", "api_key": "test_key"}

        assert mcp_service._has_auth_config_changed(existing_auth, new_auth) is True

    def test_has_auth_config_changed_both_none(self, mcp_service):
        """Test that two None configs are not detected as changed."""
        assert mcp_service._has_auth_config_changed(None, None) is False

    def test_has_auth_config_changed_one_none(self, mcp_service):
        """Test that changing from None to config is detected."""
        existing_auth = None
        new_auth = {"auth_type": "oauth", "oauth_port": "9000"}

        assert mcp_service._has_auth_config_changed(existing_auth, new_auth) is True


class TestPortChangeHandling:
    """Test handling of port changes in composer restart."""

    @pytest.mark.asyncio
    async def test_port_change_triggers_restart(self, mcp_service):
        """Test that changing ports triggers a restart via auth config change detection."""
        project_id = "test-project"
        old_port = 9000
        new_port = 9001

        # Set up existing composer
        mock_process = MagicMock(poll=MagicMock(return_value=None), pid=12345)
        mcp_service.project_composers[project_id] = {
            "process": mock_process,
            "host": "localhost",
            "port": old_port,
            "streamable_http_url": "http://test",
            "legacy_sse_url": "http://test/sse",
            "auth_config": {
                "auth_type": "oauth",
                "oauth_host": "localhost",
                "oauth_port": str(old_port),
                "oauth_server_url": f"http://localhost:{old_port}",
                "oauth_client_id": "test",
                "oauth_client_secret": "test",
                "oauth_auth_url": "http://test",
                "oauth_token_url": "http://test",
            },
        }
        mcp_service._port_to_project[old_port] = project_id
        mcp_service._pid_to_project[12345] = project_id

        new_auth_config = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": str(new_port),
            "oauth_server_url": f"http://localhost:{new_port}",
            "oauth_client_id": "test",
            "oauth_client_secret": "test",
            "oauth_auth_url": "http://test",
            "oauth_token_url": "http://test",
        }

        with (
            patch.object(mcp_service, "_do_stop_project_composer", new=AsyncMock()) as mock_stop,
            patch.object(mcp_service, "_is_port_available", return_value=True),
            patch.object(mcp_service, "_start_project_composer_process", new=AsyncMock()),
        ):
            # Initialize locks
            mcp_service._start_locks[project_id] = asyncio.Lock()

            with contextlib.suppress(Exception):
                await mcp_service._do_start_project_composer(
                    project_id=project_id,
                    streamable_http_url="http://test",
                    auth_config=new_auth_config,
                    max_retries=1,
                    max_startup_checks=1,
                    startup_delay=0.1,
                )

            # Verify composer was stopped (because config changed)
            mock_stop.assert_called_once_with(project_id)

    @pytest.mark.asyncio
    async def test_port_in_use_by_own_project_triggers_kill(self, mcp_service):
        """Test that when port is in use by the current project, it kills the process."""
        project_id = "test-project"
        test_port = 9001

        # Register the port as owned by this project
        mcp_service._port_to_project[test_port] = project_id

        auth_config = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": str(test_port),
            "oauth_server_url": f"http://localhost:{test_port}",
            "oauth_client_id": "test",
            "oauth_client_secret": "test",
            "oauth_auth_url": "http://test",
            "oauth_token_url": "http://test",
        }

        with (
            patch.object(mcp_service, "_is_port_available") as mock_port_check,
            patch.object(mcp_service, "_kill_process_on_port", new=AsyncMock(return_value=True)) as mock_kill,
        ):
            # First check: port is in use, second check after kill: port is free
            mock_port_check.side_effect = [False, True]

            # Initialize locks
            mcp_service._start_locks[project_id] = asyncio.Lock()

            with (
                patch.object(mcp_service, "_start_project_composer_process", new=AsyncMock()),
                contextlib.suppress(Exception),
            ):
                await mcp_service._do_start_project_composer(
                    project_id=project_id,
                    streamable_http_url="http://test",
                    auth_config=auth_config,
                    max_retries=1,
                    max_startup_checks=1,
                    startup_delay=0.1,
                )

            # Verify kill was attempted on own project's port
            mock_kill.assert_called_with(test_port)

    @pytest.mark.asyncio
    async def test_port_in_use_by_unknown_process_raises_error(self, mcp_service):
        """Test that error is raised when port is in use by unknown process (security)."""
        project_id = "test-project"
        test_port = 9001

        # Port is NOT tracked (unknown process)
        # mcp_service._port_to_project does NOT contain test_port

        auth_config = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": str(test_port),
            "oauth_server_url": f"http://localhost:{test_port}",
            "oauth_client_id": "test",
            "oauth_client_secret": "test",
            "oauth_auth_url": "http://test",
            "oauth_token_url": "http://test",
        }

        with patch.object(mcp_service, "_is_port_available", return_value=False):  # Port in use
            # Initialize locks
            mcp_service._start_locks[project_id] = asyncio.Lock()

            with pytest.raises(MCPComposerPortError) as exc_info:
                await mcp_service._do_start_project_composer(
                    project_id=project_id,
                    streamable_http_url="http://test",
                    auth_config=auth_config,
                    max_retries=1,
                    max_startup_checks=1,
                    startup_delay=0.1,
                )

            # New security message: won't kill unknown processes
            assert "already in use by another application" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_legacy_sse_url_preserved_in_composer_state(self, mcp_service):
        """Ensure legacy SSE URLs are passed through to the composer process and stored."""
        project_id = "legacy-project"
        auth_config = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": "9100",
            "oauth_server_url": "http://localhost:9100",
            "oauth_client_id": "legacy",
            "oauth_client_secret": "secret",
            "oauth_auth_url": "http://auth",
            "oauth_token_url": "http://token",
        }
        legacy_url = "http://test/legacy-sse"
        streamable_url = "http://test/streamable"

        mcp_service._start_locks[project_id] = asyncio.Lock()

        mock_process = MagicMock(pid=4321)
        with (
            patch.object(mcp_service, "_is_port_available", return_value=True),
            patch.object(
                mcp_service,
                "_start_project_composer_process",
                new=AsyncMock(return_value=mock_process),
            ) as mock_start,
        ):
            await mcp_service._do_start_project_composer(
                project_id=project_id,
                streamable_http_url=streamable_url,
                auth_config=auth_config,
                max_retries=1,
                max_startup_checks=1,
                startup_delay=0.1,
                legacy_sse_url=legacy_url,
            )

        mock_start.assert_awaited()
        kwargs = mock_start.call_args.kwargs
        assert kwargs["legacy_sse_url"] == legacy_url
        assert mcp_service.project_composers[project_id]["legacy_sse_url"] == legacy_url
        assert mcp_service.project_composers[project_id]["streamable_http_url"] == streamable_url

    @pytest.mark.asyncio
    async def test_legacy_sse_url_defaults_when_not_provided(self, mcp_service):
        """Verify that a default SSE URL is derived when none is supplied."""
        project_id = "legacy-default"
        streamable_url = "http://test/default"
        auth_config = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": "9200",
            "oauth_server_url": "http://localhost:9200",
            "oauth_client_id": "legacy",
            "oauth_client_secret": "secret",
            "oauth_auth_url": "http://auth",
            "oauth_token_url": "http://token",
        }

        mcp_service._start_locks[project_id] = asyncio.Lock()

        mock_process = MagicMock(pid=9876)
        with (
            patch.object(mcp_service, "_is_port_available", return_value=True),
            patch.object(
                mcp_service,
                "_start_project_composer_process",
                new=AsyncMock(return_value=mock_process),
            ) as mock_start,
        ):
            await mcp_service._do_start_project_composer(
                project_id=project_id,
                streamable_http_url=streamable_url,
                auth_config=auth_config,
                max_retries=1,
                max_startup_checks=1,
                startup_delay=0.1,
            )

        mock_start.assert_awaited()
        kwargs = mock_start.call_args.kwargs
        assert kwargs["legacy_sse_url"] == f"{streamable_url}/sse"
