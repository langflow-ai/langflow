"""MCP subprocess cleanup utilities for graceful shutdown.

This module provides functions to properly terminate MCP server subprocesses
spawned by stdio_client during Langflow shutdown.

Works on macOS and Linux only.
"""

from __future__ import annotations

import contextlib
import sys
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    import psutil as psutil_type


async def cleanup_mcp_sessions() -> None:
    """Cleanup all MCP sessions to ensure subprocesses are properly terminated.

    This function should be called at the very beginning of the shutdown sequence
    to ensure MCP subprocesses are killed even if shutdown is interrupted.
    """
    with contextlib.suppress(Exception):
        from lfx.base.mcp.util import MCPSessionManager
        from lfx.services.cache.utils import CACHE_MISS

        from langflow.services.deps import get_shared_component_cache_service

        cache_service = get_shared_component_cache_service()
        session_manager = cache_service.get("mcp_session_manager")

        if session_manager is not CACHE_MISS and isinstance(session_manager, MCPSessionManager):
            await session_manager.cleanup_all()

    # Fallback: Kill any MCP server processes (Unix only)
    with contextlib.suppress(Exception):
        await _kill_mcp_processes()


async def _kill_mcp_processes() -> None:
    """Kill MCP server subprocesses spawned by this Langflow process.

    This is a fallback for when the normal cleanup doesn't properly terminate
    subprocesses spawned by stdio_client.

    Works on macOS and Linux only.
    """
    if sys.platform == "win32":
        return

    try:
        import psutil
    except ImportError:
        return

    with contextlib.suppress(Exception):
        killed_count = await _terminate_child_mcp_processes(psutil)
        killed_count += await _terminate_orphaned_mcp_processes(psutil)

        if killed_count > 0:
            await logger.ainfo(f"Killed {killed_count} MCP processes")


async def _terminate_child_mcp_processes(psutil: psutil_type) -> int:
    """Terminate MCP processes that are children of this process."""
    killed_count = 0

    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
    except psutil.NoSuchProcess:
        return 0

    for proc in children:
        if await _try_terminate_mcp_process(proc, psutil):
            killed_count += 1

    return killed_count


async def _terminate_orphaned_mcp_processes(psutil: psutil_type) -> int:
    """Terminate orphaned MCP processes (ppid=1) on Unix systems."""
    killed_count = 0

    for proc in psutil.process_iter(["pid", "ppid", "cmdline"]):
        try:
            info = proc.info
            if info.get("ppid", 0) != 1:
                continue

            if await _try_terminate_mcp_process(proc, psutil):
                killed_count += 1

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return killed_count


async def _try_terminate_mcp_process(proc: psutil_type.Process, psutil: psutil_type) -> bool:
    """Try to terminate a process if it's an MCP server process.

    Returns True if the process was terminated, False otherwise.
    """
    try:
        cmdline = proc.cmdline()
        cmdline_str = " ".join(cmdline) if cmdline else ""

        if "mcp-server" not in cmdline_str and "mcp-proxy" not in cmdline_str:
            return False

        proc.terminate()
        try:
            proc.wait(timeout=2)
        except psutil.TimeoutExpired:
            proc.kill()

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    else:
        return True
