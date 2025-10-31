"""MCP Composer service for proxying and orchestrating MCP servers."""

import asyncio
import os
import platform
import re
import select
import socket
import subprocess
from collections.abc import Callable
from functools import wraps
from typing import Any

from langflow.logging import logger
from langflow.services.base import Service
from langflow.services.deps import get_settings_service

GENERIC_STARTUP_ERROR_MSG = (
    "MCP Composer startup failed. Check OAuth configuration and check logs for more information."
)


class MCPComposerError(Exception):
    """Base exception for MCP Composer errors."""

    def __init__(self, message: str | None, project_id: str | None = None):
        if not message:
            message = GENERIC_STARTUP_ERROR_MSG
        self.message = message
        self.project_id = project_id
        super().__init__(message)


class MCPComposerPortError(MCPComposerError):
    """Port is already in use or unavailable."""


class MCPComposerConfigError(MCPComposerError):
    """Invalid configuration provided."""


class MCPComposerDisabledError(MCPComposerError):
    """MCP Composer is disabled in settings."""


class MCPComposerStartupError(MCPComposerError):
    """Failed to start MCP Composer process."""


def require_composer_enabled(func: Callable) -> Callable:
    """Decorator that checks if MCP Composer is enabled before executing the method."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not get_settings_service().settings.mcp_composer_enabled:
            project_id = kwargs.get("project_id")
            error_msg = "MCP Composer is disabled in settings"
            raise MCPComposerDisabledError(error_msg, project_id)

        return func(self, *args, **kwargs)

    return wrapper


class MCPComposerService(Service):
    """Service for managing per-project MCP Composer instances."""

    name = "mcp_composer_service"

    def __init__(self):
        super().__init__()
        self.project_composers: dict[str, dict] = {}  # project_id -> {process, host, port, sse_url, auth_config}
        self._start_locks: dict[
            str, asyncio.Lock
        ] = {}  # Lock to prevent concurrent start operations for the same project
        self._active_start_tasks: dict[
            str, asyncio.Task
        ] = {}  # Track active start tasks to cancel them when new request arrives
        self._port_to_project: dict[int, str] = {}  # Track which project is using which port
        self._pid_to_project: dict[int, str] = {}  # Track which PID belongs to which project
        self._last_errors: dict[str, str] = {}  # Track last error message per project for UI display

    def get_last_error(self, project_id: str) -> str | None:
        """Get the last error message for a project, if any."""
        return self._last_errors.get(project_id)

    def set_last_error(self, project_id: str, error_message: str) -> None:
        """Set the last error message for a project."""
        self._last_errors[project_id] = error_message

    def clear_last_error(self, project_id: str) -> None:
        """Clear the last error message for a project."""
        self._last_errors.pop(project_id, None)

    def _is_port_available(self, port: int, host: str = "localhost") -> bool:
        """Check if a port is available by trying to bind to it.

        Args:
            port: Port number to check
            host: Host to check (default: localhost)

        Returns:
            True if port is available (not in use), False if in use
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Don't use SO_REUSEADDR here as it can give false positives
                sock.bind((host, port))
                return True  # Port is available
        except OSError:
            return False  # Port is in use/bound

    async def _kill_process_on_port(self, port: int) -> bool:
        """Kill the process using the specified port.

        Cross-platform implementation supporting Windows, macOS, and Linux.

        Args:
            port: The port number to check

        Returns:
            True if a process was found and killed, False otherwise
        """
        try:
            await logger.adebug(f"Checking for processes using port {port}...")
            os_type = platform.system()

            # Platform-specific command to find PID
            if os_type == "Windows":
                # Use netstat on Windows
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    # Parse netstat output to find PID
                    # Format: TCP    0.0.0.0:PORT    0.0.0.0:0    LISTENING    PID
                    windows_pids: list[int] = []
                    for line in result.stdout.split("\n"):
                        if f":{port}" in line and "LISTENING" in line:
                            parts = line.split()
                            if parts:
                                try:
                                    pid = int(parts[-1])
                                    windows_pids.append(pid)
                                except (ValueError, IndexError):
                                    continue

                    await logger.adebug(f"Found {len(windows_pids)} process(es) using port {port}: {windows_pids}")

                    for pid in windows_pids:
                        try:
                            await logger.adebug(f"Attempting to kill process {pid} on port {port}...")
                            # Use taskkill on Windows
                            kill_result = await asyncio.to_thread(
                                subprocess.run,
                                ["taskkill", "/F", "/PID", str(pid)],
                                capture_output=True,
                                check=False,
                            )

                            if kill_result.returncode == 0:
                                await logger.adebug(f"Successfully killed process {pid} on port {port}")
                                return True
                            await logger.awarning(
                                f"taskkill returned {kill_result.returncode} for process {pid} on port {port}"
                            )
                        except Exception as e:  # noqa: BLE001
                            await logger.aerror(f"Error killing PID {pid}: {e}")

                    return False
            else:
                # Use lsof on Unix-like systems (macOS, Linux)
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                await logger.adebug(f"lsof returned code {result.returncode} for port {port}")

                # Extract PIDs from lsof output
                lsof_output = result.stdout.strip()
                lsof_errors = result.stderr.strip()

                if lsof_output:
                    await logger.adebug(f"lsof stdout: {lsof_output}")
                if lsof_errors:
                    await logger.adebug(f"lsof stderr: {lsof_errors}")

                if result.returncode == 0 and lsof_output:
                    unix_pids = lsof_output.split("\n")
                    await logger.adebug(f"Found {len(unix_pids)} process(es) using port {port}: {unix_pids}")

                    for pid_str in unix_pids:
                        try:
                            pid = int(pid_str.strip())
                            await logger.adebug(f"Attempting to kill process {pid} on port {port}...")

                            # Try to kill the process
                            kill_result = await asyncio.to_thread(
                                subprocess.run,
                                ["kill", "-9", str(pid)],
                                capture_output=True,
                                check=False,
                            )

                            if kill_result.returncode == 0:
                                await logger.adebug(f"Successfully sent kill signal to process {pid} on port {port}")
                                return True
                            await logger.awarning(
                                f"kill command returned {kill_result.returncode} for process {pid} on port {port}"
                            )
                        except (ValueError, ProcessLookupError) as e:
                            await logger.aerror(f"Error processing PID {pid_str}: {e}")

                    # If we get here, we found processes but couldn't kill any
                    return False
                await logger.adebug(f"No process found using port {port}")
                return False
        except Exception as e:  # noqa: BLE001
            await logger.aerror(f"Error finding/killing process on port {port}: {e}")
            return False
        return False

    def _is_port_used_by_another_project(self, port: int, current_project_id: str) -> tuple[bool, str | None]:
        """Check if a port is being used by another project.

        Args:
            port: The port to check
            current_project_id: The current project ID

        Returns:
            Tuple of (is_used_by_other, other_project_id)
        """
        other_project_id = self._port_to_project.get(port)
        if other_project_id and other_project_id != current_project_id:
            return True, other_project_id
        return False, None

    async def start(self):
        """Check if the MCP Composer service is enabled."""
        settings = get_settings_service().settings
        if not settings.mcp_composer_enabled:
            await logger.adebug(
                "MCP Composer is disabled in settings. OAuth authentication will not be enabled for MCP Servers."
            )
        else:
            await logger.adebug(
                "MCP Composer is enabled in settings. OAuth authentication will be enabled for MCP Servers."
            )

    async def stop(self):
        """Stop all MCP Composer instances."""
        for project_id in list(self.project_composers.keys()):
            await self.stop_project_composer(project_id)
        await logger.adebug("All MCP Composer instances stopped")

    @require_composer_enabled
    async def stop_project_composer(self, project_id: str):
        """Stop the MCP Composer instance for a specific project."""
        if project_id not in self.project_composers:
            return

        # Use the same lock to ensure consistency
        if project_id in self._start_locks:
            async with self._start_locks[project_id]:
                await self._do_stop_project_composer(project_id)
                # Clean up the lock as well
                del self._start_locks[project_id]
        else:
            # Fallback if no lock exists
            await self._do_stop_project_composer(project_id)

    async def _do_stop_project_composer(self, project_id: str):
        """Internal method to stop a project composer."""
        if project_id not in self.project_composers:
            return

        composer_info = self.project_composers[project_id]
        process = composer_info.get("process")

        try:
            if process:
                try:
                    # Check if process is still running before trying to terminate
                    if process.poll() is None:
                        await logger.adebug(f"Terminating MCP Composer process {process.pid} for project {project_id}")
                        process.terminate()

                        # Wait longer for graceful shutdown
                        try:
                            await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=2.0)
                            await logger.adebug(f"MCP Composer for project {project_id} terminated gracefully")
                        except asyncio.TimeoutError:
                            await logger.aerror(
                                f"MCP Composer for project {project_id} did not terminate gracefully, force killing"
                            )
                            await asyncio.to_thread(process.kill)
                            await asyncio.to_thread(process.wait)
                    else:
                        await logger.adebug(f"MCP Composer process for project {project_id} was already terminated")

                    await logger.adebug(f"MCP Composer stopped for project {project_id}")

                except ProcessLookupError:
                    # Process already terminated
                    await logger.adebug(f"MCP Composer process for project {project_id} was already terminated")
                except Exception as e:  # noqa: BLE001
                    await logger.aerror(f"Error stopping MCP Composer for project {project_id}: {e}")
        finally:
            # Always clean up tracking, even if stopping failed
            port = composer_info.get("port")
            if port and self._port_to_project.get(port) == project_id:
                self._port_to_project.pop(port, None)
                await logger.adebug(f"Released port {port} from project {project_id}")

            # Clean up PID tracking
            if process and process.pid:
                self._pid_to_project.pop(process.pid, None)
                await logger.adebug(f"Released PID {process.pid} tracking for project {project_id}")

            # Remove from tracking
            self.project_composers.pop(project_id, None)
            await logger.adebug(f"Removed tracking for project {project_id}")

    async def _wait_for_process_exit(self, process):
        """Wait for a process to exit."""
        await asyncio.to_thread(process.wait)

    async def _read_process_output_and_extract_error(
        self, process: subprocess.Popen, oauth_server_url: str | None, timeout: float = 2.0
    ) -> tuple[str, str, str]:
        """Read process output and extract user-friendly error message.

        Args:
            process: The subprocess to read from
            oauth_server_url: OAuth server URL for error messages
            timeout: Timeout for reading output

        Returns:
            Tuple of (stdout, stderr, error_message)
        """
        try:
            # Use asyncio.to_thread to avoid blocking the event loop
            # Process returns bytes, decode with error handling
            stdout_bytes, stderr_bytes = await asyncio.to_thread(process.communicate, timeout=timeout)
            stdout_content = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr_content = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        except subprocess.TimeoutExpired:
            process.kill()
            error_msg = self._extract_error_message("", "", oauth_server_url)
            return "", "", error_msg
        else:
            error_msg = self._extract_error_message(stdout_content, stderr_content, oauth_server_url)
            return stdout_content, stderr_content, error_msg

    async def _read_stream_non_blocking(self, stream, stream_name: str) -> None:
        """Read from a stream without blocking and log the content.

        Args:
            stream: The stream to read from (stdout or stderr)
            stream_name: Name of the stream for logging ("stdout" or "stderr")
        """
        if stream and select.select([stream], [], [], 0)[0]:
            try:
                line_bytes = stream.readline()
                if line_bytes:
                    # Decode bytes with error handling
                    line = line_bytes.decode("utf-8", errors="replace") if isinstance(line_bytes, bytes) else line_bytes
                    stripped = line.strip()
                    if stripped:
                        # Log errors at error level, everything else at debug
                        if stream_name == "stderr" and ("ERROR" in stripped or "error" in stripped):
                            await logger.aerror(f"MCP Composer {stream_name}: {stripped}")
                        else:
                            await logger.adebug(f"MCP Composer {stream_name}: {stripped}")
            except Exception as e:  # noqa: BLE001
                await logger.adebug(f"Error reading {stream_name}: {e}")

    async def _ensure_port_available(self, port: int, current_project_id: str) -> None:
        """Ensure a port is available, only killing untracked processes.

        Args:
            port: The port number to ensure is available
            current_project_id: The project ID requesting the port

        Raises:
            MCPComposerPortError: If port cannot be made available
        """
        is_port_available = self._is_port_available(port)
        await logger.adebug(f"Port {port} availability check: {is_port_available}")

        if not is_port_available:
            # Check if the port is being used by a tracked project
            is_used_by_other, other_project_id = self._is_port_used_by_another_project(port, current_project_id)

            if is_used_by_other and other_project_id:
                # Port is being used by another tracked project
                # Check if we can take ownership (e.g., the other project is failing)
                other_composer = self.project_composers.get(other_project_id)
                if other_composer and other_composer.get("process"):
                    other_process = other_composer["process"]
                    # If the other process is still running and healthy, don't kill it
                    if other_process.poll() is None:
                        await logger.aerror(
                            f"Port {port} requested by project {current_project_id} is already in use by "
                            f"project {other_project_id}. Will not kill active MCP Composer process."
                        )
                        port_error_msg = (
                            f"Port {port} is already in use by another project. "
                            f"Please choose a different port (e.g., {port + 1}) "
                            f"or disable OAuth on the other project first."
                        )
                        raise MCPComposerPortError(port_error_msg, current_project_id)

                    # Process died but port tracking wasn't cleaned up - allow takeover
                    await logger.adebug(
                        f"Port {port} was tracked to project {other_project_id} but process died. "
                        f"Allowing project {current_project_id} to take ownership."
                    )
                    # Clean up the old tracking
                    await self._do_stop_project_composer(other_project_id)

            # Check if port is used by a process owned by the current project (e.g., stuck in startup loop)
            port_owner_project = self._port_to_project.get(port)
            if port_owner_project == current_project_id:
                # Port is owned by current project - safe to kill
                await logger.adebug(
                    f"Port {port} is in use by current project {current_project_id} (likely stuck in startup). "
                    f"Killing process to retry."
                )
                killed = await self._kill_process_on_port(port)
                if killed:
                    await logger.adebug(
                        f"Successfully killed own process on port {port}. Waiting for port to be released..."
                    )
                    await asyncio.sleep(2)
                    is_port_available = self._is_port_available(port)
                    if not is_port_available:
                        await logger.aerror(f"Port {port} is still in use after killing own process.")
                        port_error_msg = f"Port {port} is still in use after killing process"
                        raise MCPComposerPortError(port_error_msg)
            else:
                # Port is in use by unknown process - don't kill it (security concern)
                await logger.aerror(
                    f"Port {port} is in use by an unknown process (not owned by Langflow). "
                    f"Will not kill external application for security reasons."
                )
                port_error_msg = (
                    f"Port {port} is already in use by another application. "
                    f"Please choose a different port (e.g., {port + 1}) or free up the port manually."
                )
                raise MCPComposerPortError(port_error_msg, current_project_id)

        await logger.adebug(f"Port {port} is available, proceeding with MCP Composer startup")

    async def _log_startup_error_details(
        self,
        project_id: str,
        cmd: list[str],
        host: str,
        port: int,
        stdout: str = "",
        stderr: str = "",
        error_msg: str = "",
        exit_code: int | None = None,
        pid: int | None = None,
    ) -> None:
        """Log detailed startup error information.

        Args:
            project_id: The project ID
            cmd: The command that was executed
            host: Target host
            port: Target port
            stdout: Standard output from the process
            stderr: Standard error from the process
            error_msg: User-friendly error message
            exit_code: Process exit code (if terminated)
            pid: Process ID (if still running)
        """
        await logger.aerror(f"MCP Composer startup failed for project {project_id}:")
        if exit_code is not None:
            await logger.aerror(f"  - Process died with exit code: {exit_code}")
        if pid is not None:
            await logger.aerror(f"  - Process is running (PID: {pid}) but failed to bind to port {port}")
        await logger.aerror(f"  - Target: {host}:{port}")

        # Obfuscate secrets in command before logging
        safe_cmd = self._obfuscate_command_secrets(cmd)
        await logger.aerror(f"  - Command: {' '.join(safe_cmd)}")

        if stderr.strip():
            await logger.aerror(f"  - Error output: {stderr.strip()}")
        if stdout.strip():
            await logger.aerror(f"  - Standard output: {stdout.strip()}")
        if error_msg:
            await logger.aerror(f"  - Error message: {error_msg}")

    def _validate_oauth_settings(self, auth_config: dict[str, Any]) -> None:
        """Validate that all required OAuth settings are present and non-empty.

        Raises:
            MCPComposerConfigError: If any required OAuth field is missing or empty
        """
        if auth_config.get("auth_type") != "oauth":
            return

        required_fields = [
            "oauth_host",
            "oauth_port",
            "oauth_server_url",
            "oauth_auth_url",
            "oauth_token_url",
            "oauth_client_id",
            "oauth_client_secret",
        ]

        missing_fields = []
        empty_fields = []

        for field in required_fields:
            value = auth_config.get(field)
            if value is None:
                missing_fields.append(field)
            elif not str(value).strip():
                empty_fields.append(field)

        error_parts = []
        if missing_fields:
            error_parts.append(f"Missing required fields: {', '.join(missing_fields)}")
        if empty_fields:
            error_parts.append(f"Empty required fields: {', '.join(empty_fields)}")

        if error_parts:
            config_error_msg = f"Invalid OAuth configuration: {'; '.join(error_parts)}"
            raise MCPComposerConfigError(config_error_msg)

    @staticmethod
    def _normalize_config_value(value: Any) -> Any:
        """Normalize a config value (None or empty string becomes None).

        Args:
            value: The value to normalize

        Returns:
            None if value is None or empty string, otherwise the value
        """
        return None if (value is None or value == "") else value

    def _has_auth_config_changed(self, existing_auth: dict[str, Any] | None, new_auth: dict[str, Any] | None) -> bool:
        """Check if auth configuration has changed in a way that requires restart."""
        if not existing_auth and not new_auth:
            return False

        if not existing_auth or not new_auth:
            return True

        auth_type = new_auth.get("auth_type", "")

        # Auth type changed?
        if existing_auth.get("auth_type") != auth_type:
            return True

        # Define which fields to check for each auth type
        fields_to_check = []
        if auth_type == "oauth":
            # Get all oauth_* fields plus host/port from both configs
            all_keys = set(existing_auth.keys()) | set(new_auth.keys())
            fields_to_check = [k for k in all_keys if k.startswith("oauth_") or k in ["host", "port"]]
        elif auth_type == "apikey":
            fields_to_check = ["api_key"]

        # Compare relevant fields
        for field in fields_to_check:
            old_normalized = self._normalize_config_value(existing_auth.get(field))
            new_normalized = self._normalize_config_value(new_auth.get(field))

            if old_normalized != new_normalized:
                return True

        return False

    def _obfuscate_command_secrets(self, cmd: list[str]) -> list[str]:
        """Obfuscate secrets in command arguments for safe logging.

        Args:
            cmd: List of command arguments

        Returns:
            List of command arguments with secrets replaced with ***REDACTED***
        """
        safe_cmd = []
        i = 0

        while i < len(cmd):
            arg = cmd[i]

            # Check if this is --env followed by a secret key
            if arg == "--env" and i + 2 < len(cmd):
                env_key = cmd[i + 1]
                env_value = cmd[i + 2]

                if any(secret in env_key.lower() for secret in ["secret", "key", "token"]):
                    # Redact the value
                    safe_cmd.extend([arg, env_key, "***REDACTED***"])
                    i += 3  # Skip all three: --env, key, and value
                    continue

                # Not a secret, keep as-is
                safe_cmd.extend([arg, env_key, env_value])
                i += 3
                continue

            # Regular argument
            safe_cmd.append(arg)
            i += 1

        return safe_cmd

    def _extract_error_message(
        self, stdout_content: str, stderr_content: str, oauth_server_url: str | None = None
    ) -> str:
        """Attempts to extract a user-friendly error message from subprocess output.

        Args:
            stdout_content: Standard output from the subprocess
            stderr_content: Standard error from the subprocess
            oauth_server_url: OAuth server URL

        Returns:
            User-friendly error message or a generic message if no specific pattern is found
        """
        # Combine both outputs and clean them up
        combined_output = (stderr_content + "\n" + stdout_content).strip()
        if not oauth_server_url:
            oauth_server_url = "OAuth server URL"

        # Common error patterns with user-friendly messages
        error_patterns = [
            (r"address already in use", f"Address {oauth_server_url} is already in use."),
            (r"permission denied", f"Permission denied starting MCP Composer on address {oauth_server_url}."),
            (
                r"connection refused",
                f"Connection refused on address {oauth_server_url}. The address may be blocked or unavailable.",
            ),
            (
                r"bind.*failed",
                f"Failed to bind to address {oauth_server_url}. The address may be in use or unavailable.",
            ),
            (r"timeout", "MCP Composer startup timed out. Please try again."),
            (r"invalid.*configuration", "Invalid MCP Composer configuration. Please check your settings."),
            (r"oauth.*error", "OAuth configuration error. Please check your OAuth settings."),
            (r"authentication.*failed", "Authentication failed. Please check your credentials."),
        ]

        # Check for specific error patterns first
        for pattern, friendly_msg in error_patterns:
            if re.search(pattern, combined_output, re.IGNORECASE):
                return friendly_msg

        return GENERIC_STARTUP_ERROR_MSG

    @require_composer_enabled
    async def start_project_composer(
        self,
        project_id: str,
        sse_url: str,
        auth_config: dict[str, Any] | None,
        max_retries: int = 3,
        max_startup_checks: int = 20,
        startup_delay: float = 1.5,
    ) -> None:
        """Start an MCP Composer instance for a specific project.

        Args:
            project_id: The project ID
            sse_url: The SSE URL to connect to
            auth_config: Authentication configuration
            max_retries: Maximum number of retry attempts (default: 3)
            max_startup_checks: Number of checks per retry attempt (default: 60)
            startup_delay: Delay between checks in seconds (default: 3.0)

        Raises:
            MCPComposerError: Various specific errors if startup fails
        """
        # Cancel any active start operation for this project
        if project_id in self._active_start_tasks:
            active_task = self._active_start_tasks[project_id]
            if not active_task.done():
                await logger.adebug(f"Cancelling previous MCP Composer start operation for project {project_id}")
                active_task.cancel()
                try:
                    await active_task
                except asyncio.CancelledError:
                    await logger.adebug(f"Previous start operation for project {project_id} cancelled successfully")
                finally:
                    # Clean up the cancelled task from tracking
                    del self._active_start_tasks[project_id]

        # Create and track the current task
        current_task = asyncio.current_task()
        if not current_task:
            await logger.awarning(
                f"Could not get current task for project {project_id}. "
                f"Concurrent start operations may not be properly cancelled."
            )
        else:
            self._active_start_tasks[project_id] = current_task

        try:
            await self._do_start_project_composer(
                project_id, sse_url, auth_config, max_retries, max_startup_checks, startup_delay
            )
        finally:
            # Clean up the task reference when done
            if project_id in self._active_start_tasks and self._active_start_tasks[project_id] == current_task:
                del self._active_start_tasks[project_id]

    async def _do_start_project_composer(
        self,
        project_id: str,
        sse_url: str,
        auth_config: dict[str, Any] | None,
        max_retries: int = 3,
        max_startup_checks: int = 20,
        startup_delay: float = 1.5,
    ) -> None:
        """Internal method to start an MCP Composer instance.

        Args:
            project_id: The project ID
            sse_url: The SSE URL to connect to
            auth_config: Authentication configuration
            max_retries: Maximum number of retry attempts (default: 3)
            max_startup_checks: Number of checks per retry attempt (default: 60)
            startup_delay: Delay between checks in seconds (default: 3.0)

        Raises:
            MCPComposerError: Various specific errors if startup fails
        """
        if not auth_config:
            no_auth_error_msg = "No auth settings provided"
            raise MCPComposerConfigError(no_auth_error_msg, project_id)

        # Validate OAuth settings early to provide clear error messages
        self._validate_oauth_settings(auth_config)

        project_host = auth_config.get("oauth_host") if auth_config else "unknown"
        project_port = auth_config.get("oauth_port") if auth_config else "unknown"
        await logger.adebug(f"Starting MCP Composer for project {project_id} on {project_host}:{project_port}")

        # Use a per-project lock to prevent race conditions
        if project_id not in self._start_locks:
            self._start_locks[project_id] = asyncio.Lock()

        async with self._start_locks[project_id]:
            # Check if already running (double-check after acquiring lock)
            project_port_str = auth_config.get("oauth_port")
            if not project_port_str:
                no_port_error_msg = "No OAuth port provided"
                raise MCPComposerConfigError(no_port_error_msg, project_id)

            try:
                project_port = int(project_port_str)
            except (ValueError, TypeError) as e:
                port_error_msg = f"Invalid OAuth port: {project_port_str}"
                raise MCPComposerConfigError(port_error_msg, project_id) from e

            project_host = auth_config.get("oauth_host")
            if not project_host:
                no_host_error_msg = "No OAuth host provided"
                raise MCPComposerConfigError(no_host_error_msg, project_id)

            if project_id in self.project_composers:
                composer_info = self.project_composers[project_id]
                process = composer_info.get("process")
                existing_auth = composer_info.get("auth_config", {})
                existing_port = composer_info.get("port")

                # Check if process is still running
                if process and process.poll() is None:
                    # Process is running - only restart if config changed
                    auth_changed = self._has_auth_config_changed(existing_auth, auth_config)

                    if auth_changed:
                        await logger.adebug(f"Config changed for project {project_id}, restarting MCP Composer")
                        await self._do_stop_project_composer(project_id)
                    else:
                        await logger.adebug(
                            f"MCP Composer already running for project {project_id} with current config"
                        )
                        return  # Already running with correct config
                else:
                    # Process died or never started properly, restart it
                    await logger.adebug(f"MCP Composer process died for project {project_id}, restarting")
                    await self._do_stop_project_composer(project_id)
                    # Also kill any process that might be using the old port
                    if existing_port:
                        try:
                            await asyncio.wait_for(self._kill_process_on_port(existing_port), timeout=5.0)
                        except asyncio.TimeoutError:
                            await logger.aerror(f"Timeout while killing process on port {existing_port}")

            # Retry loop: try starting the process multiple times
            last_error = None
            try:
                # Ensure port is available (only kill untracked processes)
                try:
                    await self._ensure_port_available(project_port, project_id)
                except MCPComposerPortError as e:
                    # Port error before starting - store and raise immediately
                    self._last_errors[project_id] = e.message
                    raise
                for retry_attempt in range(1, max_retries + 1):
                    try:
                        await logger.adebug(
                            f"Starting MCP Composer for project {project_id} (attempt {retry_attempt}/{max_retries})"
                        )

                        # Re-check port availability before each attempt to prevent race conditions
                        if retry_attempt > 1:
                            await logger.adebug(f"Re-checking port {project_port} availability before retry...")
                            await self._ensure_port_available(project_port, project_id)

                        process = await self._start_project_composer_process(
                            project_id,
                            project_host,
                            project_port,
                            sse_url,
                            auth_config,
                            max_startup_checks,
                            startup_delay,
                        )

                    except MCPComposerError as e:
                        last_error = e
                        await logger.aerror(
                            f"MCP Composer startup attempt {retry_attempt}/{max_retries} failed "
                            f"for project {project_id}: {e.message}"
                        )

                        # Clean up any partially started process before retrying
                        if project_id in self.project_composers:
                            await self._do_stop_project_composer(project_id)

                        # If not the last attempt, wait a bit before retrying
                        if retry_attempt < max_retries:
                            await logger.adebug(f"Waiting 2 seconds before retry attempt {retry_attempt + 1}...")
                            await asyncio.sleep(2)

                    else:
                        # Success! Store the composer info and register the port and PID
                        self.project_composers[project_id] = {
                            "process": process,
                            "host": project_host,
                            "port": project_port,
                            "sse_url": sse_url,
                            "auth_config": auth_config,
                        }
                        self._port_to_project[project_port] = project_id
                        self._pid_to_project[process.pid] = project_id
                        # Clear any previous error on success
                        self.clear_last_error(project_id)

                        await logger.adebug(
                            f"MCP Composer started for project {project_id} on port {project_port} "
                            f"(PID: {process.pid}) after {retry_attempt} attempt(s)"
                        )
                        return  # Success!

                # All retries failed, raise the last error
                if last_error:
                    await logger.aerror(
                        f"MCP Composer failed to start for project {project_id} after {max_retries} attempts"
                    )
                    # Store the error message for later retrieval
                    self._last_errors[project_id] = last_error.message
                    raise last_error

            except asyncio.CancelledError:
                # Operation was cancelled, clean up any started process
                await logger.adebug(f"MCP Composer start operation for project {project_id} was cancelled")
                if project_id in self.project_composers:
                    await self._do_stop_project_composer(project_id)
                raise  # Re-raise to propagate cancellation

    async def _start_project_composer_process(
        self,
        project_id: str,
        host: str,
        port: int,
        sse_url: str,
        auth_config: dict[str, Any] | None = None,
        max_startup_checks: int = 60,
        startup_delay: float = 3.0,
    ) -> subprocess.Popen:
        """Start the MCP Composer subprocess for a specific project.

        Args:
            project_id: The project ID
            host: Host to bind to
            port: Port to bind to
            sse_url: SSE URL to connect to
            auth_config: Authentication configuration
            max_startup_checks: Number of port binding checks (default: 60)
            startup_delay: Delay between checks in seconds (default: 3.0)

        Returns:
            The started subprocess

        Raises:
            MCPComposerStartupError: If startup fails
        """
        settings = get_settings_service().settings
        cmd = [
            "uvx",
            f"mcp-composer{settings.mcp_composer_version}",
            "--port",
            str(port),
            "--host",
            host,
            "--mode",
            "sse",
            "--sse-url",
            sse_url,
            "--disable-composer-tools",
        ]

        # Set environment variables
        env = os.environ.copy()

        oauth_server_url = auth_config.get("oauth_server_url") if auth_config else None
        if auth_config:
            auth_type = auth_config.get("auth_type")

            if auth_type == "oauth":
                cmd.extend(["--auth_type", "oauth"])

                # Add OAuth environment variables as command line arguments
                cmd.extend(["--env", "ENABLE_OAUTH", "True"])

                # Map auth config to environment variables for OAuth
                # Note: oauth_host and oauth_port are passed both via --host/--port CLI args
                # (for server binding) and as environment variables (for OAuth flow)
                oauth_env_mapping = {
                    "oauth_host": "OAUTH_HOST",
                    "oauth_port": "OAUTH_PORT",
                    "oauth_server_url": "OAUTH_SERVER_URL",
                    "oauth_callback_path": "OAUTH_CALLBACK_PATH",
                    "oauth_client_id": "OAUTH_CLIENT_ID",
                    "oauth_client_secret": "OAUTH_CLIENT_SECRET",  # pragma: allowlist secret
                    "oauth_auth_url": "OAUTH_AUTH_URL",
                    "oauth_token_url": "OAUTH_TOKEN_URL",
                    "oauth_mcp_scope": "OAUTH_MCP_SCOPE",
                    "oauth_provider_scope": "OAUTH_PROVIDER_SCOPE",
                }

                # Add environment variables as command line arguments
                # Only set non-empty values to avoid Pydantic validation errors
                for config_key, env_key in oauth_env_mapping.items():
                    value = auth_config.get(config_key)
                    if value is not None and str(value).strip():
                        cmd.extend(["--env", env_key, str(value)])

        # Log the command being executed (with secrets obfuscated)
        safe_cmd = self._obfuscate_command_secrets(cmd)
        await logger.adebug(f"Starting MCP Composer with command: {' '.join(safe_cmd)}")

        # Start the subprocess with both stdout and stderr captured
        # Use binary mode and decode manually to handle encoding errors gracefully
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: ASYNC220, S603

        # Monitor the process startup with multiple checks
        process_running = False
        port_bound = False

        await logger.adebug(
            f"MCP Composer process started with PID {process.pid}, monitoring startup for project {project_id}..."
        )

        try:
            for check in range(max_startup_checks):
                await asyncio.sleep(startup_delay)

                # Check if process is still running
                poll_result = process.poll()

                startup_error_msg = None
                if poll_result is not None:
                    # Process terminated, get the error output
                    (
                        stdout_content,
                        stderr_content,
                        startup_error_msg,
                    ) = await self._read_process_output_and_extract_error(process, oauth_server_url)
                    await self._log_startup_error_details(
                        project_id, cmd, host, port, stdout_content, stderr_content, startup_error_msg, poll_result
                    )
                    raise MCPComposerStartupError(startup_error_msg, project_id)

                # Process is still running, check if port is bound
                port_bound = not self._is_port_available(port)

                if port_bound:
                    await logger.adebug(
                        f"MCP Composer for project {project_id} bound to port {port} "
                        f"(check {check + 1}/{max_startup_checks})"
                    )
                    process_running = True
                    break
                await logger.adebug(
                    f"MCP Composer for project {project_id} not yet bound to port {port} "
                    f"(check {check + 1}/{max_startup_checks})"
                )

                # Try to read any available stderr/stdout without blocking to see what's happening
                await self._read_stream_non_blocking(process.stderr, "stderr")
                await self._read_stream_non_blocking(process.stdout, "stdout")

        except asyncio.CancelledError:
            # Operation was cancelled, kill the process and cleanup
            await logger.adebug(
                f"MCP Composer process startup cancelled for project {project_id}, terminating process {process.pid}"
            )
            try:
                process.terminate()
                # Wait for graceful termination with timeout
                try:
                    await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=2.0)
                except asyncio.TimeoutError:
                    # Force kill if graceful termination times out
                    await logger.adebug(f"Process {process.pid} did not terminate gracefully, force killing")
                    await asyncio.to_thread(process.kill)
                    await asyncio.to_thread(process.wait)
            except Exception as e:  # noqa: BLE001
                await logger.adebug(f"Error terminating process during cancellation: {e}")
            raise  # Re-raise to propagate cancellation

        # After all checks
        if not process_running or not port_bound:
            # Get comprehensive error information
            poll_result = process.poll()

            if poll_result is not None:
                # Process died
                stdout_content, stderr_content, startup_error_msg = await self._read_process_output_and_extract_error(
                    process, oauth_server_url
                )
                await self._log_startup_error_details(
                    project_id, cmd, host, port, stdout_content, stderr_content, startup_error_msg, poll_result
                )
                raise MCPComposerStartupError(startup_error_msg, project_id)
            # Process running but port not bound
            await logger.aerror(
                f"  - Checked {max_startup_checks} times over {max_startup_checks * startup_delay} seconds"
            )

            # Get any available output before terminating
            process.terminate()
            stdout_content, stderr_content, startup_error_msg = await self._read_process_output_and_extract_error(
                process, oauth_server_url
            )
            await self._log_startup_error_details(
                project_id, cmd, host, port, stdout_content, stderr_content, startup_error_msg, pid=process.pid
            )
            raise MCPComposerStartupError(startup_error_msg, project_id)

        # Close the pipes if everything is successful
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

        return process

    @require_composer_enabled
    def get_project_composer_port(self, project_id: str) -> int | None:
        """Get the port number for a specific project's composer."""
        if project_id not in self.project_composers:
            return None
        return self.project_composers[project_id]["port"]

    @require_composer_enabled
    async def teardown(self) -> None:
        """Clean up resources when the service is torn down."""
        await logger.adebug("Tearing down MCP Composer service...")
        await self.stop()
        await logger.adebug("MCP Composer service teardown complete")
