import asyncio
import contextlib
import os
import platform
from typing import Any, cast

import aiofiles
from anyio import Path
from loguru import logger
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from langflow.base.mcp.base_client import BaseMCPClient


class MCPStdioClient(BaseMCPClient[dict[str, Any]]):
    """MCP STDIO Client for process-based MCP servers.

    Features improved error handling, cancellation safety, and environment support.
    Inherits common functionality from BaseMCPClient while implementing STDIO-specific
    connection and tool execution logic.
    """

    def __init__(self) -> None:
        super().__init__()
        self.timeout_seconds = 30  # default timeout

    async def connect_to_server(self, command_str: str, env: dict[str, str] | None = None) -> list[types.Tool]:
        """Connect to an MCP server via STDIO transport.

        Args:
            command_str: Command to execute for the MCP server
            env: Optional environment variables dictionary

        Returns:
            List of available tools from the server

        Raises:
            ValueError: For invalid input or command not found
            ConnectionError: For connection failures or server errors
        """
        if env is None:
            env = {}

        command = command_str.split(" ")
        env_data: dict[str, str] = {"DEBUG": "true", "PATH": os.environ["PATH"], **env}

        # Create platform-specific command wrapper
        if platform.system() == "Windows":
            # For Windows, use cmd.exe with error reporting
            server_params = StdioServerParameters(
                command="cmd",
                args=[
                    "/c",
                    f"{command[0]} {' '.join(command[1:])} || echo Command failed with exit code %errorlevel% 1>&2",
                ],
                env=env_data,
            )
        else:
            # For Unix-like systems, use bash with error reporting
            server_params = StdioServerParameters(
                command="bash",
                args=["-c", f"{command_str} || echo 'Command failed with exit code $?' >&2"],
                env=env_data,
            )

        # Store connection parameters for later use
        self._connection_params = {
            "command_str": command_str,
            "env": env,
        }

        # Wrap the entire connection logic to handle cancellation properly
        try:
            tools = await self._execute_connection(server_params, command_str)
            self._connected = True
        except asyncio.CancelledError as e:
            # Ensure proper cleanup on cancellation
            await self._safe_cleanup()
            msg = f"MCP STDIO connection to '{command_str}' was cancelled"
            raise ConnectionError(msg) from e
        except Exception:
            # Ensure cleanup on any error
            await self._safe_cleanup()
            self._connection_params = None
            self._connected = False
            raise
        else:
            return tools

    async def _execute_connection(self, server_params: StdioServerParameters, command_str: str):
        """Execute the STDIO connection with proper task management."""
        # Create a temporary file to capture stderr
        errlog_path = ""
        async with aiofiles.tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False) as tmp:
            errlog_path = cast(str, tmp.name)
            # Ensure temp file is flushed and closed for cross-platform compatibility
            await tmp.flush()
            await tmp.close()

            watcher_task = None
            initializer_task = None

            try:
                # Reopen the temp file for stderr capture
                async with aiofiles.open(errlog_path, mode="w+", encoding="utf-8") as stderr_file:
                    stdio_transport = await self.exit_stack.enter_async_context(
                        stdio_client(server_params, errlog=stderr_file)
                    )
                    self.stdio, self.write = stdio_transport
                    self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

                    # Create a watcher task to monitor stderr
                    initialization_complete = asyncio.Event()

                    async def watch_stderr():
                        last_size = 0
                        full_log = ""
                        while not initialization_complete.is_set():  # Break when initialization completes
                            await asyncio.sleep(0.05)
                            try:
                                current = (await Path(errlog_path).stat()).st_size
                                if current > last_size:
                                    async with aiofiles.open(errlog_path, encoding="utf-8") as f:
                                        await f.seek(last_size)
                                        data = await f.read()
                                        full_log += data
                                        data = data.strip()

                                    # Check for our specific error message pattern
                                    if "Command failed with exit code" in data:
                                        msg = f"MCP server command '{command_str}' failed\nError log:\n{full_log}"
                                        raise ConnectionError(msg)
                                last_size = current
                            except (OSError, asyncio.CancelledError):
                                # Handle file access errors or cancellation gracefully
                                break

                    # Create tasks for both operations
                    watcher_task = asyncio.create_task(watch_stderr())
                    if self.session is None:
                        msg = "Session is None after initialization"
                        raise RuntimeError(msg)
                    initializer_task = asyncio.create_task(self.session.initialize())

                    # Race them: first to finish wins
                    try:
                        done, _pending = await asyncio.wait(
                            {watcher_task, initializer_task}, return_when=asyncio.FIRST_COMPLETED
                        )
                    except asyncio.CancelledError:
                        # Ensure both tasks are cancelled and drained
                        logger.debug("STDIO connection cancelled, cleaning up tasks...")
                        raise
                    finally:
                        # Always ensure tasks are properly cleaned up
                        initialization_complete.set()  # Signal watcher to stop
                        await self._cleanup_tasks(watcher_task, initializer_task)

                    if watcher_task in done:
                        # stderr watcher fired → initialization failed
                        watcher_task.result()  # re-raise ConnectionError from watcher
                    else:
                        # initialize succeeded
                        initializer_task.result()  # re-raise initialization errors if any

                    # If we get here, initialization succeeded
                    if self.session is None:
                        msg = "Session is None after successful initialization"
                        raise RuntimeError(msg)
                    response = await self.session.list_tools()
                    return response.tools

            except FileNotFoundError as e:
                # Command not found, provide clear error message
                msg = (
                    f"Command not found: '{command_str.split()[0]}'. "
                    "Please verify the command is installed and in your PATH."
                )
                raise ValueError(msg) from e
            except OSError as e:
                # Other OS errors (e.g., permission denied)
                msg = f"Failed to start command '{command_str.split()[0]}': {e}"
                raise ValueError(msg) from e
            except ConnectionError:
                # Re-raise ConnectionErrors as-is (from stderr watcher)
                raise
            except Exception as e:
                msg = f"Failed to initialize MCP STDIO session with command '{command_str}': {e}"
                logger.warning(msg)
                raise ConnectionError(msg) from e
            finally:
                # Clean up the temp file with proper error suppression
                await self._safe_file_cleanup(errlog_path)

    async def _cleanup_tasks(self, watcher_task, initializer_task):
        """Safely cleanup async tasks with proper cancellation handling."""
        tasks_to_cleanup = []

        if watcher_task is not None and not watcher_task.done():
            watcher_task.cancel()
            tasks_to_cleanup.append(watcher_task)

        if initializer_task is not None and not initializer_task.done():
            initializer_task.cancel()
            tasks_to_cleanup.append(initializer_task)

        if tasks_to_cleanup:
            # Wait for all tasks to complete (either successfully or cancelled)
            await asyncio.gather(*tasks_to_cleanup, return_exceptions=True)
            logger.debug(f"Cleaned up {len(tasks_to_cleanup)} STDIO tasks")

    async def _safe_file_cleanup(self, errlog_path: str):
        """Safely clean up temporary file, suppressing cancellation errors."""
        with contextlib.suppress(FileNotFoundError, PermissionError, asyncio.CancelledError, OSError):
            # The surrounding task may already be cancelled; ignore
            # cancellation during best-effort temp-file cleanup.
            await Path(errlog_path).unlink()

    async def _safe_cleanup(self):
        """Safely cleanup the exit stack, suppressing cancellation errors."""
        try:
            await self.exit_stack.aclose()
        except asyncio.CancelledError:
            # Suppress cancellation during cleanup
            pass
        except (OSError, ConnectionError, ValueError) as exc:
            logger.debug(f"Error during STDIO client cleanup: {exc}")

    async def _cleanup_transport(self):
        """Perform STDIO-specific cleanup operations."""
        # STDIO client doesn't have additional transport-specific cleanup beyond what _safe_cleanup does
        # But we can call it to ensure proper cleanup
        await self._safe_cleanup()

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        await self.close()

    async def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool using STDIO transport (creates new connection per tool).

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool

        Returns:
            Result of the tool execution

        Raises:
            ValueError: For invalid tool parameters or execution failures
        """
        try:
            params = self._connection_params
            if params is None:
                msg = "Connection parameters are None"
                raise ValueError(msg)

            command_str = params["command_str"]
            env = params["env"]

            # Create new connection for tool execution
            command = command_str.split(" ")
            env_data: dict[str, str] = {"DEBUG": "true", "PATH": os.environ["PATH"], **env}

            if platform.system() == "Windows":
                server_params = StdioServerParameters(
                    command="cmd",
                    args=["/c", f"{command[0]} {' '.join(command[1:])}"],
                    env=env_data,
                )
            else:
                server_params = StdioServerParameters(
                    command="bash",
                    args=["-c", command_str],
                    env=env_data,
                )

            async with stdio_client(server_params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)

                # Handle different response formats
                if hasattr(result, "content"):
                    return {"content": result.content}
                if isinstance(result, dict):
                    return result
                return {"result": result}

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            msg = f"Failed to run tool '{tool_name}': {e}"
            logger.error(msg)
            # Mark as disconnected on error
            self._connected = False
            raise ValueError(msg) from e
