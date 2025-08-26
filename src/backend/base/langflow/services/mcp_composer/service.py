"""MCP Composer service for proxying and orchestrating MCP servers."""

import asyncio
import os
import socket
import subprocess
from typing import Any

from loguru import logger

from langflow.services.base import Service
from langflow.services.deps import get_settings_service


class MCPComposerService(Service):
    """Service for managing per-project MCP Composer instances."""

    name = "mcp_composer_service"

    def __init__(self):
        super().__init__()
        self.project_composers: dict[str, dict] = {}  # project_id -> {process, port, sse_url, auth_config}
        self._start_locks: dict[
            str, asyncio.Lock
        ] = {}  # Lock to prevent concurrent start operations for the same project
        settings = get_settings_service().settings
        self.composer_host: str = settings.mcp_composer_host or "localhost"

        # Check for user-defined port from environment variable first
        self.base_port: int = settings.mcp_composer_port or 8001

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available (not in use)."""
        try:
            with socket.create_connection((self.composer_host, port), timeout=1.0):
                return False  # Port is in use
        except (OSError, ConnectionRefusedError):
            return True  # Port is available

    def _find_available_port(self, start_port: int, max_attempts: int = 100) -> int:
        """Find an available port starting from start_port.

        Args:
            start_port: The port to start searching from
            max_attempts: Maximum number of ports to try

        Returns:
            int: An available port number

        Raises:
            RuntimeError: If no available port is found within max_attempts
        """
        for attempt in range(max_attempts):
            port = start_port + attempt
            if self._is_port_available(port):
                logger.debug(f"Found available port: {port} (tried {attempt + 1} ports)")
                return port

        msg = f"Could not find an available port after trying {max_attempts} ports starting from {start_port}"
        raise RuntimeError(msg)

    async def start(self):
        """Check if the MCP Composer service is enabled."""
        settings = get_settings_service().settings
        if not settings.mcp_composer_enabled:
            logger.debug(
                "MCP Composer is disabled in settings. OAuth authentication will not be enabled for MCP Servers."
            )
            return

    async def stop(self):
        """Stop all MCP Composer instances."""
        for project_id in list(self.project_composers.keys()):
            await self.stop_project_composer(project_id)
        logger.debug("All MCP Composer instances stopped")

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
                    logger.debug(f"Terminating MCP Composer process {process.pid} for project {project_id}")
                    process.terminate()
                    
                    # Wait longer for graceful shutdown
                    try:
                        await asyncio.wait_for(self._wait_for_process_exit(process), timeout=3.0)
                        logger.debug(f"MCP Composer for project {project_id} terminated gracefully")
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"MCP Composer for project {project_id} did not terminate gracefully, force killing"
                        )
                        process.kill()
                        # Wait a bit more for force kill to complete
                        try:
                            await asyncio.wait_for(self._wait_for_process_exit(process), timeout=2.0)
                        except asyncio.TimeoutError:
                            logger.error(f"Failed to kill MCP Composer process {process.pid} for project {project_id}")
                else:
                    logger.debug(f"MCP Composer process for project {project_id} was already terminated")

                logger.debug(f"MCP Composer stopped for project {project_id}")

            except ProcessLookupError:
                # Process already terminated
                logger.debug(f"MCP Composer process for project {project_id} was already terminated")
            except Exception as e:
                logger.error(f"Error stopping MCP Composer for project {project_id}: {e}")

        # Remove from tracking
        del self.project_composers[project_id]
        
    async def _wait_for_process_exit(self, process):
        """Wait for a process to exit by polling."""
        while process.poll() is None:
            await asyncio.sleep(0.1)

    async def start_project_composer(
        self, project_id: str, sse_url: str, auth_config: dict[str, Any] | None = None
    ) -> int:
        """Start an MCP Composer instance for a specific project.

        Returns:
            int: The port number assigned to this project's composer
        """
        # Use a per-project lock to prevent race conditions
        if project_id not in self._start_locks:
            self._start_locks[project_id] = asyncio.Lock()

        async with self._start_locks[project_id]:
            # Check if already running (double-check after acquiring lock)
            if project_id in self.project_composers:
                composer_info = self.project_composers[project_id]
                process = composer_info.get("process")
                if process and process.poll() is None:
                    logger.debug(f"MCP Composer already running for project {project_id}")
                    return composer_info["port"]
                logger.warning(f"MCP Composer process for project {project_id} was terminated, restarting")
                if project_id in self.project_composers:
                    del self.project_composers[project_id]

            # Find an available port starting from the base port
            # Use a higher starting port for subsequent projects to avoid conflicts
            used_ports = {info["port"] for info in self.project_composers.values()}
            start_port = max([self.base_port, *list(used_ports)], default=self.base_port)
            if used_ports:
                start_port += 1  # Start from the next port after the highest used port

            try:
                project_port = self._find_available_port(start_port)
            except RuntimeError as e:
                logger.error(f"Could not find available port for project {project_id}: {e}")
                raise

            max_retries = 3
            last_error = None

            for attempt in range(max_retries):
                try:
                    process = await self._start_project_composer_process(project_id, project_port, sse_url, auth_config)

                    self.project_composers[project_id] = {
                        "process": process,
                        "port": project_port,
                        "sse_url": sse_url,
                        "auth_config": auth_config,
                    }

                    logger.info(f"MCP Composer started for project {project_id} on port {project_port}")
                    return project_port

                except Exception as e:
                    last_error = e

                    # If it's a port-related error, try to find another port
                    if (
                        "port" in str(e).lower()
                        or "bind" in str(e).lower()
                        or "address already in use" in str(e).lower()
                    ):
                        logger.warning(
                            f"Port {project_port} failed for project {project_id} (attempt {attempt + 1}): {e}"
                        )

                        if attempt < max_retries - 1:  # Don't find new port on last attempt
                            try:
                                # Try to find another available port
                                project_port = self._find_available_port(project_port + 1)
                                logger.debug(f"Retrying with port {project_port} for project {project_id}")
                                continue
                            except RuntimeError:
                                logger.error(f"Could not find alternative port for project {project_id}")
                                break
                    else:
                        # Non-port related error, don't retry
                        break

            error = f"Failed to start MCP Composer for project {project_id} after {max_retries} attempts: {last_error}"
            logger.error(error)
            raise RuntimeError(error) from last_error

    async def _start_project_composer_process(
        self, project_id: str, port: int, sse_url: str, auth_config: dict[str, Any] | None = None
    ) -> subprocess.Popen:
        """Start the MCP Composer subprocess for a specific project."""
        cmd = [
            "uvx",
            "mcp-composer",
            "--mode",
            "sse",
            "--endpoint",
            sse_url,
            "--host",
            self.composer_host,
            "--port",
            str(port),
            "--disable-composer-tools",
        ]
        logger.debug(
            f"Starting MCP Composer for project {project_id} on host {self.composer_host} port {port} with SSE URL {sse_url}"
        )

        # Skip auth configuration - let MCP Composer connect without authentication
        # The SSE endpoint will be modified to allow internal connections
        if False and auth_config:  # Disabled auth config
            auth_type = auth_config.get("auth_type")
            if auth_type == "oauth":
                cmd.extend(["--auth_type", "oauth"])
                cmd.extend(["--env", "ENABLE_OAUTH", "True"])

                # Map auth config to environment variables for OAuth
                oauth_env_mapping = {
                    "oauth_host": "OAUTH_HOST",
                    "oauth_port": "OAUTH_PORT",
                    "oauth_server_url": "OAUTH_SERVER_URL",
                    "oauth_callback_path": "OAUTH_CALLBACK_PATH",
                    "oauth_client_id": "OAUTH_CLIENT_ID",
                    "oauth_client_secret": "OAUTH_CLIENT_SECRET",
                    "oauth_auth_url": "OAUTH_AUTH_URL",
                    "oauth_token_url": "OAUTH_TOKEN_URL",
                    "oauth_mcp_scope": "OAUTH_MCP_SCOPE",
                    "oauth_provider_scope": "OAUTH_PROVIDER_SCOPE",
                }

                # Add environment variables to the command
                for config_key, env_key in oauth_env_mapping.items():
                    if config_key in auth_config:
                        cmd.extend(["--env", env_key, str(auth_config[config_key])])

                # Add server_url as workaround for MCP Composer internal ServerSettings bug
                if "oauth_server_url" in auth_config:
                    cmd.extend(["--env", "server_url", str(auth_config["oauth_server_url"])])

            elif auth_type == "apikey":
                cmd.extend(["--auth_type", "apikey"])
                if "api_key" in auth_config:
                    # Configure for token-based authentication
                    cmd.extend(["--env", "API_KEY", str(auth_config["api_key"])])
                    cmd.extend(["--env", "MEDIA_TYPE", "application/json"])

        # Set environment variables
        env = os.environ.copy()

        try:
            # Start the subprocess with proper error capturing
            process = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)

            # Give it a moment to start
            await asyncio.sleep(1)

            # Check if process is still running
            if process.poll() is not None:
                # Process terminated, get the error
                try:
                    stdout, stderr = process.communicate(timeout=5)
                    error_msg = stderr.strip() if stderr else stdout.strip() if stdout else "Unknown error"
                    logger.error(f"MCP Composer subprocess output - stdout: {stdout}, stderr: {stderr}")
                    raise RuntimeError(f"MCP Composer failed to start for project {project_id}: {error_msg}")
                except subprocess.TimeoutExpired:
                    process.kill()  # Force kill if timeout
                    raise RuntimeError(
                        f"MCP Composer for project {project_id} terminated but couldn't read error output"
                    )

            return process

        except FileNotFoundError:
            logger.warning("uvx not found. Trying to run mcp-composer directly with Python...")
            # Try running as a Python module if uvx is not available
            cmd = [
                "python",
                "-m",
                "mcp_composer",
                "--mode",
                "sse",
                "--host",
                self.composer_host,
                "--port",
                str(port),
                "--sse-url",
                sse_url,
            ]

            # Skip auth configuration - disabled for internal connections
            if False and auth_config:  # Disabled auth config
                auth_type = auth_config.get("auth_type")
                if auth_type == "oauth":
                    cmd.extend(["--auth_type", "oauth"])
                    cmd.extend(["--env", "ENABLE_OAUTH", "True"])

                    # Map auth config to environment variables for OAuth
                    oauth_env_mapping = {
                        "oauth_host": "OAUTH_HOST",
                        "oauth_port": "OAUTH_PORT",
                        "oauth_server_url": "OAUTH_SERVER_URL",
                        "oauth_callback_path": "OAUTH_CALLBACK_PATH",
                        "oauth_client_id": "OAUTH_CLIENT_ID",
                        "oauth_client_secret": "OAUTH_CLIENT_SECRET",
                        "oauth_auth_url": "OAUTH_AUTH_URL",
                        "oauth_token_url": "OAUTH_TOKEN_URL",
                        "oauth_mcp_scope": "OAUTH_MCP_SCOPE",
                        "oauth_provider_scope": "OAUTH_PROVIDER_SCOPE",
                    }

                    # Add environment variables to the command
                    for config_key, env_key in oauth_env_mapping.items():
                        if config_key in auth_config:
                            cmd.extend(["--env", env_key, str(auth_config[config_key])])

                    # Add server_url as workaround for MCP Composer internal ServerSettings bug
                    if "oauth_server_url" in auth_config:
                        cmd.extend(["--env", "server_url", str(auth_config["oauth_server_url"])])

                elif auth_type == "apikey":
                    cmd.extend(["--auth_type", "apikey"])
                    if "api_key" in auth_config:
                        # Configure for token-based authentication
                        cmd.extend(["--env", "API_KEY", str(auth_config["api_key"])])
                        cmd.extend(["--env", "MEDIA_TYPE", "application/json"])

            process = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
            return process

    def get_project_composer_port(self, project_id: str) -> int | None:
        """Get the port number for a specific project's composer."""
        if project_id not in self.project_composers:
            return None
        return self.project_composers[project_id]["port"]

    async def teardown(self) -> None:
        """Clean up resources when the service is torn down."""
        logger.debug("Tearing down MCP Composer service...")
        await self.stop()
        logger.debug("MCP Composer service teardown complete")
