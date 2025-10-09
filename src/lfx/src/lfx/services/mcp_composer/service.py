"""MCP Composer service for proxying and orchestrating MCP servers."""

import asyncio
import os
import re
import select
import socket
import subprocess
from collections.abc import Callable
from functools import wraps
from typing import Any

from lfx.log.logger import logger
from lfx.services.base import Service
from lfx.services.deps import get_settings_service

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

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available by trying to bind to it."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", port))
                return True  # Port is available
        except OSError:
            return False  # Port is in use/bound

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

        if process:
            try:
                # Check if process is still running before trying to terminate
                if process.poll() is None:
                    await logger.adebug(f"Terminating MCP Composer process {process.pid} for project {project_id}")
                    process.terminate()

                    # Wait longer for graceful shutdown
                    try:
                        await asyncio.wait_for(self._wait_for_process_exit(process), timeout=3.0)
                        await logger.adebug(f"MCP Composer for project {project_id} terminated gracefully")
                    except asyncio.TimeoutError:
                        await logger.aerror(
                            f"MCP Composer for project {project_id} did not terminate gracefully, force killing"
                        )
                        process.kill()
                        # Wait a bit more for force kill to complete
                        try:
                            await asyncio.wait_for(self._wait_for_process_exit(process), timeout=2.0)
                        except asyncio.TimeoutError:
                            await logger.aerror(
                                f"Failed to kill MCP Composer process {process.pid} for project {project_id}"
                            )
                else:
                    await logger.adebug(f"MCP Composer process for project {project_id} was already terminated")

                await logger.adebug(f"MCP Composer stopped for project {project_id}")

            except ProcessLookupError:
                # Process already terminated
                await logger.adebug(f"MCP Composer process for project {project_id} was already terminated")
            except Exception as e:  # noqa: BLE001
                await logger.aerror(f"Error stopping MCP Composer for project {project_id}: {e}")

        # Remove from tracking
        del self.project_composers[project_id]

    async def _wait_for_process_exit(self, process):
        """Wait for a process to exit."""
        await asyncio.to_thread(process.wait)

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
            old_val = existing_auth.get(field)
            new_val = new_auth.get(field)

            # Convert None and empty string to None for comparison
            old_normalized = None if (old_val is None or old_val == "") else old_val
            new_normalized = None if (new_val is None or new_val == "") else new_val

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
        skip_next = False

        for i, arg in enumerate(cmd):
            if skip_next:
                skip_next = False
                safe_cmd.append("***REDACTED***")
                continue

            if arg == "--env" and i + 2 < len(cmd):
                # Check if next env var is a secret
                env_key = cmd[i + 1]
                if any(secret in env_key.lower() for secret in ["secret", "key", "token"]):
                    safe_cmd.extend([arg, env_key])  # Keep env key, redact value
                    skip_next = True
                    continue

            safe_cmd.append(arg)

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
        max_startup_checks: int = 5,
        startup_delay: float = 2.0,
    ) -> None:
        """Start an MCP Composer instance for a specific project.

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

            is_port_available = self._is_port_available(project_port)
            if not is_port_available:
                await logger.awarning(f"Port {project_port} is already in use.")
                port_error_msg = f"Port {project_port} is already in use"
                raise MCPComposerPortError(port_error_msg)

            # Start the MCP Composer process (single attempt, no outer retry loop)
            process = await self._start_project_composer_process(
                project_id, project_host, project_port, sse_url, auth_config, max_startup_checks, startup_delay
            )
            self.project_composers[project_id] = {
                "process": process,
                "host": project_host,
                "port": project_port,
                "sse_url": sse_url,
                "auth_config": auth_config,
            }

            await logger.adebug(
                f"MCP Composer started for project {project_id} on port {project_port} (PID: {process.pid})"
            )

    async def _start_project_composer_process(
        self,
        project_id: str,
        host: str,
        port: int,
        sse_url: str,
        auth_config: dict[str, Any] | None = None,
        max_startup_checks: int = 5,
        startup_delay: float = 2.0,
    ) -> subprocess.Popen:
        """Start the MCP Composer subprocess for a specific project."""
        settings = get_settings_service().settings
        cmd = [
            "uvx",
            f"mcp-composer{settings.mcp_composer_version}",
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

        # Start the subprocess with both stdout and stderr captured
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)  # noqa: ASYNC220, S603

        # Monitor the process startup with multiple checks
        process_running = False
        port_bound = False

        await logger.adebug(f"Monitoring MCP Composer startup for project {project_id} (PID: {process.pid})")

        for check in range(max_startup_checks):
            await asyncio.sleep(startup_delay)

            # Check if process is still running
            poll_result = process.poll()

            startup_error_msg = None
            if poll_result is not None:
                # Process terminated, get the error output
                await logger.aerror(f"MCP Composer process {process.pid} terminated with exit code: {poll_result}")
                try:
                    stdout_content, stderr_content = process.communicate(timeout=2)
                    # Log the full error details for debugging
                    await logger.aerror(f"MCP Composer startup failed for project {project_id}")
                    await logger.aerror(f"MCP Composer stdout:\n{stdout_content}")
                    await logger.aerror(f"MCP Composer stderr:\n{stderr_content}")
                    safe_cmd = self._obfuscate_command_secrets(cmd)
                    await logger.aerror(f"Command that failed: {' '.join(safe_cmd)}")

                    # Extract meaningful error message
                    startup_error_msg = self._extract_error_message(stdout_content, stderr_content, oauth_server_url)
                    raise MCPComposerStartupError(startup_error_msg, project_id)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await logger.aerror(
                        f"MCP Composer process {process.pid} terminated unexpectedly for project {project_id}"
                    )
                    startup_error_msg = self._extract_error_message("", "", oauth_server_url)
                    raise MCPComposerStartupError(startup_error_msg, project_id) from None

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

            # Try to read any available stderr without blocking (only log if there's an error)
            if process.stderr and select.select([process.stderr], [], [], 0)[0]:
                try:
                    stderr_line = process.stderr.readline()
                    if stderr_line and "ERROR" in stderr_line:
                        await logger.aerror(f"MCP Composer error: {stderr_line.strip()}")
                except Exception:  # noqa: BLE001
                    pass

        # After all checks
        if not process_running or not port_bound:
            # Get comprehensive error information
            poll_result = process.poll()

            if poll_result is not None:
                # Process died
                startup_error_msg = None
                try:
                    stdout_content, stderr_content = process.communicate(timeout=2)
                    # Extract meaningful error message
                    startup_error_msg = self._extract_error_message(stdout_content, stderr_content, oauth_server_url)
                    await logger.aerror(f"MCP Composer startup failed for project {project_id}:")
                    await logger.aerror(f"  - Process died with exit code: {poll_result}")
                    await logger.aerror(f"  - Target: {host}:{port}")
                    # Obfuscate secrets in command before logging
                    safe_cmd = self._obfuscate_command_secrets(cmd)
                    await logger.aerror(f"  - Command: {' '.join(safe_cmd)}")
                    if stderr_content.strip():
                        await logger.aerror(f"  - Error output: {stderr_content.strip()}")
                    if stdout_content.strip():
                        await logger.aerror(f"  - Standard output: {stdout_content.strip()}")
                    await logger.aerror(f"  - Error message: {startup_error_msg}")
                except subprocess.TimeoutExpired:
                    await logger.aerror(f"MCP Composer for project {project_id} died but couldn't read output")
                    process.kill()

                raise MCPComposerStartupError(startup_error_msg, project_id)
            # Process running but port not bound
            await logger.aerror(f"MCP Composer startup failed for project {project_id}:")
            await logger.aerror(f"  - Process is running (PID: {process.pid}) but failed to bind to port {port}")
            await logger.aerror(
                f"  - Checked {max_startup_checks} times over {max_startup_checks * startup_delay} seconds"
            )
            await logger.aerror(f"  - Target: {host}:{port}")

            # Get any available output before terminating
            startup_error_msg = None
            try:
                process.terminate()
                stdout_content, stderr_content = process.communicate(timeout=2)
                startup_error_msg = self._extract_error_message(stdout_content, stderr_content, oauth_server_url)
                if stderr_content.strip():
                    await logger.aerror(f"  - Process stderr: {stderr_content.strip()}")
                if stdout_content.strip():
                    await logger.aerror(f"  - Process stdout: {stdout_content.strip()}")
            except Exception:  # noqa: BLE001
                process.kill()
                await logger.aerror("  - Could not retrieve process output before termination")

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
