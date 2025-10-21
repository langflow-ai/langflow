"""Unit tests for MCP Composer Service port management and process killing."""

import asyncio
import contextlib
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.mcp_composer.service import MCPComposerPortError, MCPComposerService


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
            sock.bind(("0.0.0.0", test_port))  # noqa: S104
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
    async def test_port_change_triggers_old_port_kill(self, mcp_service):
        """Test that changing ports kills the process on the old port."""
        project_id = "test-project"
        old_port = 9000
        new_port = 9001

        # Set up existing composer
        mcp_service.project_composers[project_id] = {
            "process": MagicMock(poll=MagicMock(return_value=None)),  # Running process
            "host": "localhost",
            "port": old_port,
            "sse_url": "http://test",
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
            patch.object(mcp_service, "_do_stop_project_composer", new=AsyncMock()),
            patch.object(mcp_service, "_kill_process_on_port", new=AsyncMock(return_value=True)) as mock_kill,
            patch.object(mcp_service, "_is_port_available", return_value=True),
            patch.object(mcp_service, "_start_project_composer_process", new=AsyncMock()),
        ):
            # Initialize locks
            mcp_service._start_locks[project_id] = asyncio.Lock()

            # We're not testing full startup, just the port kill logic
            with contextlib.suppress(Exception):
                await mcp_service._do_start_project_composer(
                    project_id=project_id,
                    sse_url="http://test",
                    auth_config=new_auth_config,
                    max_retries=1,
                    max_startup_checks=1,
                    startup_delay=0.1,
                )

            # Verify old port was targeted for killing
            mock_kill.assert_called_with(old_port)

    @pytest.mark.asyncio
    async def test_port_in_use_triggers_kill(self, mcp_service):
        """Test that when new port is in use, it attempts to kill the process."""
        project_id = "test-project"
        test_port = 9001

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
                    sse_url="http://test",
                    auth_config=auth_config,
                    max_retries=1,
                    max_startup_checks=1,
                    startup_delay=0.1,
                )

            # Verify kill was attempted on the in-use port
            mock_kill.assert_called_with(test_port)

    @pytest.mark.asyncio
    async def test_port_still_in_use_after_kill_raises_error(self, mcp_service):
        """Test that error is raised when port is still in use after kill attempt."""
        project_id = "test-project"
        test_port = 9001

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
            patch.object(mcp_service, "_is_port_available", return_value=False),  # Port always in use
            patch.object(mcp_service, "_kill_process_on_port", new=AsyncMock(return_value=True)),
        ):
            # Initialize locks
            mcp_service._start_locks[project_id] = asyncio.Lock()

            with pytest.raises(MCPComposerPortError) as exc_info:
                await mcp_service._do_start_project_composer(
                    project_id=project_id,
                    sse_url="http://test",
                    auth_config=auth_config,
                    max_retries=1,
                    max_startup_checks=1,
                    startup_delay=0.1,
                )

            assert "still in use after killing process" in str(exc_info.value)
