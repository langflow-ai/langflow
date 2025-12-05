"""Tests for MCP cleanup utilities."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.utils.mcp_cleanup import (
    _kill_mcp_processes,
    _terminate_child_mcp_processes,
    _terminate_orphaned_mcp_processes,
    _try_terminate_mcp_process,
    cleanup_mcp_sessions,
)

pytestmark = pytest.mark.asyncio


class TestCleanupMcpSessions:
    """Tests for cleanup_mcp_sessions function."""

    async def test_cleanup_with_valid_session_manager(self):
        """Test cleanup when a valid MCPSessionManager exists in cache."""
        mock_session_manager = MagicMock()
        mock_session_manager.cleanup_all = AsyncMock()

        mock_cache_service = MagicMock()
        mock_cache_service.get.return_value = mock_session_manager

        with (
            patch(
                "langflow.services.deps.get_shared_component_cache_service",
                return_value=mock_cache_service,
            ),
            patch("langflow.utils.mcp_cleanup._kill_mcp_processes", new_callable=AsyncMock) as mock_kill,
            patch("lfx.base.mcp.util.MCPSessionManager", new=type(mock_session_manager)),
        ):
            await cleanup_mcp_sessions()

            mock_session_manager.cleanup_all.assert_called_once()
            mock_kill.assert_called_once()

    async def test_cleanup_with_cache_miss(self):
        """Test cleanup when no session manager exists (cache miss)."""
        mock_cache_service = MagicMock()

        cache_miss_sentinel = object()

        with (
            patch("lfx.services.cache.utils.CACHE_MISS", cache_miss_sentinel),
            patch(
                "langflow.services.deps.get_shared_component_cache_service",
                return_value=mock_cache_service,
            ),
            patch("langflow.utils.mcp_cleanup._kill_mcp_processes", new_callable=AsyncMock) as mock_kill,
        ):
            mock_cache_service.get.return_value = cache_miss_sentinel

            await cleanup_mcp_sessions()

            # Should still call the fallback kill function
            mock_kill.assert_called_once()

    async def test_cleanup_handles_import_error(self):
        """Test cleanup handles import errors gracefully."""
        with (
            patch.dict("sys.modules", {"lfx.base.mcp.util": None}),
            patch("langflow.utils.mcp_cleanup._kill_mcp_processes", new_callable=AsyncMock) as mock_kill,
        ):
            # Should not raise, should silently continue
            await cleanup_mcp_sessions()
            mock_kill.assert_called_once()

    async def test_cleanup_handles_exception_in_session_manager(self):
        """Test cleanup handles exceptions from session manager gracefully."""
        mock_session_manager = MagicMock()
        mock_session_manager.cleanup_all = AsyncMock(side_effect=Exception("Test error"))

        mock_cache_service = MagicMock()
        mock_cache_service.get.return_value = mock_session_manager

        with (
            patch(
                "langflow.services.deps.get_shared_component_cache_service",
                return_value=mock_cache_service,
            ),
            patch("langflow.utils.mcp_cleanup._kill_mcp_processes", new_callable=AsyncMock) as mock_kill,
            patch("lfx.base.mcp.util.MCPSessionManager", new=type(mock_session_manager)),
        ):
            # Should not raise
            await cleanup_mcp_sessions()
            # Fallback should still be called
            mock_kill.assert_called_once()


class TestKillMcpProcesses:
    """Tests for _kill_mcp_processes function."""

    async def test_skips_on_windows(self):
        """Test that the function skips on Windows."""
        with patch.object(sys, "platform", "win32"):
            # Should return immediately without doing anything
            await _kill_mcp_processes()

    async def test_skips_when_psutil_not_available(self):
        """Test that the function handles missing psutil gracefully."""
        with (
            patch.object(sys, "platform", "darwin"),
            patch.dict("sys.modules", {"psutil": None}),
        ):
            # Should not raise
            await _kill_mcp_processes()

    async def test_kills_child_and_orphaned_processes(self):
        """Test that both child and orphaned processes are terminated."""
        mock_psutil = MagicMock()

        with (
            patch.object(sys, "platform", "darwin"),
            patch.dict("sys.modules", {"psutil": mock_psutil}),
            patch(
                "langflow.utils.mcp_cleanup._terminate_child_mcp_processes",
                new_callable=AsyncMock,
                return_value=2,
            ) as mock_child,
            patch(
                "langflow.utils.mcp_cleanup._terminate_orphaned_mcp_processes",
                new_callable=AsyncMock,
                return_value=1,
            ) as mock_orphan,
        ):
            await _kill_mcp_processes()

            mock_child.assert_called_once()
            mock_orphan.assert_called_once()

    async def test_logs_killed_count(self):
        """Test that killed process count is logged."""
        mock_psutil = MagicMock()

        with (
            patch.object(sys, "platform", "darwin"),
            patch.dict("sys.modules", {"psutil": mock_psutil}),
            patch(
                "langflow.utils.mcp_cleanup._terminate_child_mcp_processes",
                new_callable=AsyncMock,
                return_value=3,
            ),
            patch(
                "langflow.utils.mcp_cleanup._terminate_orphaned_mcp_processes",
                new_callable=AsyncMock,
                return_value=2,
            ),
            patch("langflow.utils.mcp_cleanup.logger") as mock_logger,
        ):
            mock_logger.ainfo = AsyncMock()

            await _kill_mcp_processes()

            mock_logger.ainfo.assert_called_once()
            call_args = mock_logger.ainfo.call_args[0][0]
            assert "5" in call_args  # 3 + 2 = 5

    async def test_does_not_log_when_no_processes_killed(self):
        """Test that no log is made when no processes are killed."""
        mock_psutil = MagicMock()

        with (
            patch.object(sys, "platform", "darwin"),
            patch.dict("sys.modules", {"psutil": mock_psutil}),
            patch(
                "langflow.utils.mcp_cleanup._terminate_child_mcp_processes",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "langflow.utils.mcp_cleanup._terminate_orphaned_mcp_processes",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("langflow.utils.mcp_cleanup.logger") as mock_logger,
        ):
            mock_logger.ainfo = AsyncMock()

            await _kill_mcp_processes()

            mock_logger.ainfo.assert_not_called()


class TestTerminateChildMcpProcesses:
    """Tests for _terminate_child_mcp_processes function."""

    async def test_terminates_mcp_child_processes(self):
        """Test that MCP child processes are terminated."""
        mock_psutil = MagicMock()

        mock_mcp_proc = MagicMock()
        mock_mcp_proc.cmdline.return_value = ["python", "mcp-server-filesystem", "/tmp"]  # noqa: S108
        mock_mcp_proc.terminate = MagicMock()
        mock_mcp_proc.wait = MagicMock()

        mock_other_proc = MagicMock()
        mock_other_proc.cmdline.return_value = ["python", "other_script.py"]

        mock_current = MagicMock()
        mock_current.children.return_value = [mock_mcp_proc, mock_other_proc]

        mock_psutil.Process.return_value = mock_current
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception
        mock_psutil.TimeoutExpired = Exception

        with patch(
            "langflow.utils.mcp_cleanup._try_terminate_mcp_process",
            new_callable=AsyncMock,
            side_effect=[True, False],
        ):
            count = await _terminate_child_mcp_processes(mock_psutil)

        assert count == 1

    async def test_handles_no_such_process_on_children(self):
        """Test handling when current process doesn't exist."""
        mock_psutil = MagicMock()

        mock_current = MagicMock()
        mock_current.children.side_effect = mock_psutil.NoSuchProcess

        mock_psutil.Process.return_value = mock_current
        mock_psutil.NoSuchProcess = Exception

        count = await _terminate_child_mcp_processes(mock_psutil)

        assert count == 0


class TestTerminateOrphanedMcpProcesses:
    """Tests for _terminate_orphaned_mcp_processes function."""

    async def test_terminates_orphaned_mcp_processes(self):
        """Test that orphaned MCP processes (ppid=1) are terminated."""
        mock_psutil = MagicMock()

        # Orphaned MCP process (ppid=1)
        mock_orphan_mcp = MagicMock()
        mock_orphan_mcp.info = {
            "pid": 12345,
            "ppid": 1,
            "cmdline": ["python", "mcp-server-filesystem", "/tmp"],  # noqa: S108
        }

        # Non-orphaned MCP process
        mock_non_orphan = MagicMock()
        mock_non_orphan.info = {
            "pid": 12346,
            "ppid": 1000,
            "cmdline": ["python", "mcp-server-filesystem", "/tmp"],  # noqa: S108
        }

        # Orphaned non-MCP process
        mock_orphan_other = MagicMock()
        mock_orphan_other.info = {
            "pid": 12347,
            "ppid": 1,
            "cmdline": ["python", "other_script.py"],
        }

        mock_psutil.process_iter.return_value = [mock_orphan_mcp, mock_non_orphan, mock_orphan_other]
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception

        with patch(
            "langflow.utils.mcp_cleanup._try_terminate_mcp_process",
            new_callable=AsyncMock,
            side_effect=[True, False],  # Only first call (orphan_mcp) returns True
        ):
            count = await _terminate_orphaned_mcp_processes(mock_psutil)

        # Only the orphaned MCP process should be attempted (ppid=1)
        # The non-orphan (ppid=1000) should be skipped before _try_terminate is called
        assert count == 1

    async def test_skips_non_orphaned_processes(self):
        """Test that non-orphaned processes are skipped."""
        mock_psutil = MagicMock()

        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 12345,
            "ppid": 1000,  # Not orphaned
            "cmdline": ["python", "mcp-server-filesystem"],
        }

        mock_psutil.process_iter.return_value = [mock_proc]
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception

        with patch(
            "langflow.utils.mcp_cleanup._try_terminate_mcp_process",
            new_callable=AsyncMock,
        ) as mock_terminate:
            count = await _terminate_orphaned_mcp_processes(mock_psutil)

        assert count == 0
        mock_terminate.assert_not_called()

    async def test_handles_access_denied(self):
        """Test handling AccessDenied exception during iteration."""
        mock_psutil = MagicMock()

        mock_proc = MagicMock()
        mock_proc.info = property(lambda _: (_ for _ in ()).throw(mock_psutil.AccessDenied))

        # Make info raise AccessDenied
        type(mock_proc).info = property(lambda _: (_ for _ in ()).throw(mock_psutil.AccessDenied))

        mock_psutil.process_iter.return_value = [mock_proc]
        mock_psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
        mock_psutil.AccessDenied = type("AccessDenied", (Exception,), {})
        mock_psutil.ZombieProcess = type("ZombieProcess", (Exception,), {})

        # Should not raise
        count = await _terminate_orphaned_mcp_processes(mock_psutil)
        assert count == 0


class TestTryTerminateMcpProcess:
    """Tests for _try_terminate_mcp_process function."""

    async def test_terminates_mcp_server_process(self):
        """Test termination of mcp-server process."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception
        mock_psutil.TimeoutExpired = Exception

        mock_proc = MagicMock()
        mock_proc.cmdline.return_value = ["python", "mcp-server-filesystem", "/tmp"]  # noqa: S108
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is True
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=2)

    async def test_terminates_mcp_proxy_process(self):
        """Test termination of mcp-proxy process."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception
        mock_psutil.TimeoutExpired = Exception

        mock_proc = MagicMock()
        mock_proc.cmdline.return_value = ["mcp-proxy", "--port", "8080"]
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is True
        mock_proc.terminate.assert_called_once()

    async def test_skips_non_mcp_process(self):
        """Test that non-MCP processes are skipped."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception

        mock_proc = MagicMock()
        mock_proc.cmdline.return_value = ["python", "some_other_script.py"]

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is False
        mock_proc.terminate.assert_not_called()

    async def test_kills_process_on_timeout(self):
        """Test that process is killed when terminate times out."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception
        mock_psutil.TimeoutExpired = type("TimeoutExpired", (Exception,), {})

        mock_proc = MagicMock()
        mock_proc.cmdline.return_value = ["python", "mcp-server-test"]
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock(side_effect=mock_psutil.TimeoutExpired)
        mock_proc.kill = MagicMock()

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is True
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    async def test_handles_no_such_process(self):
        """Test handling when process no longer exists."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception

        mock_proc = MagicMock()
        mock_proc.cmdline.side_effect = mock_psutil.NoSuchProcess

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is False

    async def test_handles_access_denied(self):
        """Test handling when access is denied."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = type("AccessDenied", (Exception,), {})
        mock_psutil.ZombieProcess = Exception

        mock_proc = MagicMock()
        mock_proc.cmdline.side_effect = mock_psutil.AccessDenied

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is False

    async def test_handles_zombie_process(self):
        """Test handling zombie processes."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = type("ZombieProcess", (Exception,), {})

        mock_proc = MagicMock()
        mock_proc.cmdline.side_effect = mock_psutil.ZombieProcess

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is False

    async def test_handles_empty_cmdline(self):
        """Test handling when cmdline returns empty list."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception

        mock_proc = MagicMock()
        mock_proc.cmdline.return_value = []

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is False

    async def test_handles_none_cmdline(self):
        """Test handling when cmdline returns None."""
        mock_psutil = MagicMock()
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = Exception
        mock_psutil.ZombieProcess = Exception

        mock_proc = MagicMock()
        mock_proc.cmdline.return_value = None

        result = await _try_terminate_mcp_process(mock_proc, mock_psutil)

        assert result is False


class TestMcpCleanupIntegration:
    """Integration tests for MCP cleanup."""

    async def test_full_cleanup_flow_success(self):
        """Test the complete cleanup flow when everything works."""
        mock_session_manager = MagicMock()
        mock_session_manager.cleanup_all = AsyncMock()

        mock_cache_service = MagicMock()
        mock_cache_service.get.return_value = mock_session_manager

        with (
            patch(
                "langflow.services.deps.get_shared_component_cache_service",
                return_value=mock_cache_service,
            ),
            patch("langflow.utils.mcp_cleanup._kill_mcp_processes", new_callable=AsyncMock),
            patch("lfx.base.mcp.util.MCPSessionManager", new=type(mock_session_manager)),
        ):
            # Should complete without raising
            await cleanup_mcp_sessions()

    async def test_full_cleanup_flow_with_all_errors(self):
        """Test that cleanup continues even when everything fails."""
        mock_cache_service = MagicMock()
        mock_cache_service.get.side_effect = Exception("Cache error")

        with (
            patch(
                "langflow.services.deps.get_shared_component_cache_service",
                return_value=mock_cache_service,
            ),
            patch(
                "langflow.utils.mcp_cleanup._kill_mcp_processes",
                new_callable=AsyncMock,
                side_effect=Exception("Kill error"),
            ),
        ):
            # Should not raise even with all errors
            await cleanup_mcp_sessions()

    async def test_cleanup_is_silent_on_errors(self):
        """Test that cleanup doesn't log errors (silent failure during shutdown)."""
        mock_cache_service = MagicMock()
        mock_cache_service.get.side_effect = Exception("Some error")

        with (
            patch(
                "langflow.services.deps.get_shared_component_cache_service",
                return_value=mock_cache_service,
            ),
            patch("langflow.utils.mcp_cleanup._kill_mcp_processes", new_callable=AsyncMock),
            patch("langflow.utils.mcp_cleanup.logger") as mock_logger,
        ):
            mock_logger.awarning = AsyncMock()
            mock_logger.aerror = AsyncMock()

            await cleanup_mcp_sessions()

            # Should not log errors during cleanup (silent failure)
            mock_logger.awarning.assert_not_called()
            mock_logger.aerror.assert_not_called()
