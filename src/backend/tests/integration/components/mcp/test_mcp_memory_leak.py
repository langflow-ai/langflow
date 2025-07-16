"""Integration tests for MCP memory leak fix.

These tests verify that the MCP session manager properly handles session reuse
and cleanup to prevent subprocess leaks.
"""

import asyncio
import contextlib
import os
import platform
import shutil

import psutil
import pytest
from langflow.base.mcp.util import MCPSessionManager
from loguru import logger
from mcp import StdioServerParameters


@pytest.fixture
def mcp_server_params():
    """Create MCP server parameters for testing."""
    command = ["npx", "-y", "@modelcontextprotocol/server-everything"]
    env_data = {"DEBUG": "true", "PATH": os.environ["PATH"]}

    if platform.system() == "Windows":
        return StdioServerParameters(
            command="cmd",
            args=["/c", f"{command[0]} {' '.join(command[1:])}"],
            env=env_data,
        )
    return StdioServerParameters(
        command="bash",
        args=["-c", f"exec {' '.join(command)}"],
        env=env_data,
    )


@pytest.fixture
def process_tracker():
    """Track subprocess count for memory leak detection."""
    process = psutil.Process()
    initial_count = len(process.children(recursive=True))

    yield process, initial_count

    # Cleanup any remaining child processes
    try:
        for child in process.children(recursive=True):
            try:
                child.terminate()
                child.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                with contextlib.suppress(psutil.NoSuchProcess):
                    child.kill()
    except Exception as e:  # noqa: BLE001
        logger.exception("Error cleaning up child processes: %s", e)



@pytest.mark.asyncio
@pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
async def test_session_reuse_prevents_subprocess_leak(mcp_server_params, process_tracker):
    """Test that session reuse prevents subprocess proliferation."""
    process, initial_count = process_tracker

    session_manager = MCPSessionManager()

    try:
        # Create multiple sessions with different context IDs but same server
        sessions = []
        for i in range(3):
            context_id = f"test_context_{i}"
            session = await session_manager.get_session(context_id, mcp_server_params, "stdio")
            sessions.append(session)

            # Verify session is working
            tools_response = await session.list_tools()
            assert len(tools_response.tools) > 0

        # Check subprocess count after creating sessions
        current_count = len(process.children(recursive=True))
        subprocess_increase = current_count - initial_count

        # With the fix, we should have minimal subprocess increase
        # (ideally 2 subprocesses max for the MCP server)
        assert subprocess_increase <= 4, f"Too many subprocesses created: {subprocess_increase}"

        # Verify all sessions are functional
        for session in sessions:
            tools_response = await session.list_tools()
            assert len(tools_response.tools) > 0

    finally:
        await session_manager.cleanup_all()
        await asyncio.sleep(2)  # Allow cleanup to complete


@pytest.mark.asyncio
@pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
async def test_session_cleanup_removes_subprocesses(mcp_server_params, process_tracker):
    """Test that session cleanup properly removes subprocesses."""
    process, initial_count = process_tracker

    session_manager = MCPSessionManager()

    try:
        # Create a session
        session = await session_manager.get_session("cleanup_test", mcp_server_params, "stdio")
        tools_response = await session.list_tools()
        assert len(tools_response.tools) > 0

        # Verify subprocess was created
        after_creation_count = len(process.children(recursive=True))
        assert after_creation_count > initial_count

    finally:
        # Clean up session
        await session_manager.cleanup_all()
        await asyncio.sleep(2)  # Allow cleanup to complete

        # Verify subprocess was cleaned up
        after_cleanup_count = len(process.children(recursive=True))
        # Allow some tolerance for cleanup timing and system processes
        assert after_cleanup_count <= initial_count + 1, f"Subprocesses not cleaned up properly: {after_cleanup_count} vs {initial_count}"


@pytest.mark.asyncio
@pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
async def test_session_health_check_and_recovery(mcp_server_params, process_tracker):
    """Test that unhealthy sessions are properly detected and recreated."""
    process, initial_count = process_tracker

    session_manager = MCPSessionManager()

    try:
        # Create a session
        session1 = await session_manager.get_session("health_test", mcp_server_params, "stdio")
        tools_response = await session1.list_tools()
        assert len(tools_response.tools) > 0

        # Simulate session becoming unhealthy by accessing internal state
        # This is a bit of a hack but necessary for testing
        server_key = session_manager._get_server_key(mcp_server_params, "stdio")
        if hasattr(session_manager, "sessions_by_server"):
            # For the fixed version
            sessions = session_manager.sessions_by_server.get(server_key, {})
            if sessions:
                session_id = next(iter(sessions.keys()))
                session_info = sessions[session_id]
                if "task" in session_info:
                    task = session_info["task"]
                    if not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task
        elif hasattr(session_manager, "sessions"):
            # For the original version
            for session_info in session_manager.sessions.values():
                if "task" in session_info:
                    task = session_info["task"]
                    if not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

        # Wait a bit for the task to be cancelled
        await asyncio.sleep(1)

        # Try to get a session again - should create a new healthy one
        session2 = await session_manager.get_session("health_test_2", mcp_server_params, "stdio")
        tools_response = await session2.list_tools()
        assert len(tools_response.tools) > 0

    finally:
        await session_manager.cleanup_all()
        await asyncio.sleep(2)


@pytest.mark.asyncio
@pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
async def test_multiple_servers_isolation(process_tracker):
    """Test that different servers get separate sessions."""
    process, initial_count = process_tracker

    session_manager = MCPSessionManager()

    # Create parameters for different servers
    server1_params = StdioServerParameters(
        command="bash",
        args=["-c", "exec npx -y @modelcontextprotocol/server-everything"],
        env={"DEBUG": "true", "PATH": os.environ["PATH"]},
    )

    server2_params = StdioServerParameters(
        command="bash",
        args=["-c", "exec npx -y @modelcontextprotocol/server-everything"],
        env={"DEBUG": "false", "PATH": os.environ["PATH"]},  # Different env
    )

    try:
        # Create sessions for different servers
        session1 = await session_manager.get_session("server1_test", server1_params, "stdio")
        session2 = await session_manager.get_session("server2_test", server2_params, "stdio")

        # Verify both sessions work
        tools1 = await session1.list_tools()
        tools2 = await session2.list_tools()

        assert len(tools1.tools) > 0
        assert len(tools2.tools) > 0

        # Sessions should be different objects for different servers (different environments)
        # Since the servers have different environments, they should get different server keys
        server_key1 = session_manager._get_server_key(server1_params, "stdio")
        server_key2 = session_manager._get_server_key(server2_params, "stdio")
        assert server_key1 != server_key2, "Different server environments should generate different keys"
        assert session1 is not session2

    finally:
        await session_manager.cleanup_all()
        await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_session_manager_server_key_generation():
    """Test that server key generation works correctly."""
    session_manager = MCPSessionManager()

    # Test stdio server key
    stdio_params = StdioServerParameters(
        command="test_command",
        args=["arg1", "arg2"],
        env={"TEST": "value"},
    )

    key1 = session_manager._get_server_key(stdio_params, "stdio")
    key2 = session_manager._get_server_key(stdio_params, "stdio")

    # Same parameters should generate same key
    assert key1 == key2
    assert key1.startswith("stdio_")

    # Different parameters should generate different keys
    stdio_params2 = StdioServerParameters(
        command="different_command",
        args=["arg1", "arg2"],
        env={"TEST": "value"},
    )

    key3 = session_manager._get_server_key(stdio_params2, "stdio")
    assert key1 != key3

    # Test SSE server key
    sse_params = {
        "url": "http://example.com/sse",
        "headers": {"Authorization": "Bearer token"},
        "timeout_seconds": 30,
        "sse_read_timeout_seconds": 30,
    }

    sse_key1 = session_manager._get_server_key(sse_params, "sse")
    sse_key2 = session_manager._get_server_key(sse_params, "sse")

    assert sse_key1 == sse_key2
    assert sse_key1.startswith("sse_")

    # Different URL should generate different key
    sse_params2 = sse_params.copy()
    sse_params2["url"] = "http://different.com/sse"

    sse_key3 = session_manager._get_server_key(sse_params2, "sse")
    assert sse_key1 != sse_key3


@pytest.mark.asyncio
async def test_session_manager_connectivity_validation():
    """Test session connectivity validation."""
    session_manager = MCPSessionManager()

    # Mock a session that responds to list_tools
    class MockSession:
        def __init__(self, should_fail=False):  # noqa: FBT002
            self.should_fail = should_fail

        async def list_tools(self):
            if self.should_fail:
                msg = "Connection failed"
                raise Exception(msg)  # noqa: TRY002

            class MockResponse:
                def __init__(self):
                    self.tools = ["tool1", "tool2"]

            return MockResponse()

    # Test healthy session
    healthy_session = MockSession(should_fail=False)
    is_healthy = await session_manager._validate_session_connectivity(healthy_session)
    assert is_healthy is True

    # Test unhealthy session
    unhealthy_session = MockSession(should_fail=True)
    is_healthy = await session_manager._validate_session_connectivity(unhealthy_session)
    assert is_healthy is False

    # Test session that returns None
    class MockNoneSession:
        async def list_tools(self):
            return None

    none_session = MockNoneSession()
    is_healthy = await session_manager._validate_session_connectivity(none_session)
    assert is_healthy is False


@pytest.mark.asyncio
async def test_session_manager_cleanup_all():
    """Test that cleanup_all properly cleans up all sessions."""
    session_manager = MCPSessionManager()

    # Mock some sessions using the correct structure
    session_manager.sessions_by_server = {
        "server1": {
            "sessions": {
                "session1": {
                    "session": "mock_session",
                    "task": asyncio.create_task(asyncio.sleep(10)),
                    "type": "stdio",
                    "last_used": asyncio.get_event_loop().time(),
                }
            }
        },
        "server2": {
            "sessions": {
                "session2": {
                    "session": "mock_session",
                    "task": asyncio.create_task(asyncio.sleep(10)),
                    "type": "sse",
                    "last_used": asyncio.get_event_loop().time(),
                }
            }
        },
    }

    # Add some background tasks
    task1 = asyncio.create_task(asyncio.sleep(10))
    task2 = asyncio.create_task(asyncio.sleep(10))
    session_manager._background_tasks = {task1, task2}

    # Cleanup all
    await session_manager.cleanup_all()

    # Verify cleanup
    if hasattr(session_manager, "sessions_by_server"):
        # For fixed version
        assert len(session_manager.sessions_by_server) == 0
    elif hasattr(session_manager, "sessions"):
        # For original version
        assert len(session_manager.sessions) == 0

    # Verify background tasks were cancelled
    assert task1.done()
    assert task2.done()
