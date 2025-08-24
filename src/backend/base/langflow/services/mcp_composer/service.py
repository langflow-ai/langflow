"""MCP Composer service for proxying and orchestrating MCP servers."""

import asyncio
import os
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
        # Track multiple composer processes - one per project
        self.project_composers: dict[str, dict] = {}  # project_id -> {process, port, sse_url, auth_config}
        self.next_port: int = 8001  # Starting port for composers

        # Get settings for host configuration
        settings = get_settings_service().settings
        self.composer_host: str = settings.mcp_composer_host or "localhost"

        # Check for user-defined port from environment variable first
        self.initial_mcp_port: int = settings.mcp_composer_port or 8001

    async def start(self):
        """Start the MCP Composer service (per-project composers started on demand)."""
        try:
            settings = get_settings_service().settings

            # Check if MCP Composer should be enabled
            if not settings.mcp_composer_enabled:
                logger.info("MCP Composer is disabled in settings")
                return

            # Initialize port allocation
            self.next_port = self.initial_mcp_port
            logger.info("MCP Composer service initialized (per-project composers will start on demand)")

        except Exception as e:
            logger.error(f"Failed to start MCP Composer service: {e}")
            raise

    async def stop(self):
        """Stop all MCP Composer instances."""
        for project_id in list(self.project_composers.keys()):
            await self.stop_project_composer(project_id)

        logger.info("All MCP Composer instances stopped")

    async def stop_project_composer(self, project_id: str):
        """Stop the MCP Composer instance for a specific project."""
        if project_id not in self.project_composers:
            return

        composer_info = self.project_composers[project_id]
        process = composer_info.get("process")

        if process:
            try:
                # Check if process is still running before trying to terminate
                if process.poll() is None:
                    process.terminate()
                    await asyncio.sleep(1)  # Give it time to shut down gracefully

                    if process.poll() is None:
                        logger.warning(
                            f"MCP Composer for project {project_id} did not terminate gracefully, force killing"
                        )
                        process.kill()
                        await asyncio.sleep(0.5)  # Brief pause after force kill

                logger.info(f"MCP Composer stopped for project {project_id}")

            except ProcessLookupError:
                # Process already terminated
                logger.debug(f"MCP Composer process for project {project_id} was already terminated")
            except Exception as e:
                logger.error(f"Error stopping MCP Composer for project {project_id}: {e}")

        # Remove from tracking
        del self.project_composers[project_id]

    async def start_project_composer(
        self, project_id: str, sse_url: str, auth_config: dict[str, Any] | None = None
    ) -> int:
        """Start an MCP Composer instance for a specific project.

        Returns:
            int: The port number assigned to this project's composer
        """
        # Check if already running
        if project_id in self.project_composers:
            logger.debug(f"MCP Composer already running for project {project_id}")
            return self.project_composers[project_id]["port"]

        # Assign a port for this project
        project_port = self.next_port
        self.next_port += 1

        try:
            # Start the composer process for this project
            process = await self._start_project_composer_process(project_id, project_port, sse_url, auth_config)

            # Track the composer instance
            self.project_composers[project_id] = {
                "process": process,
                "port": project_port,
                "sse_url": sse_url,
                "auth_config": auth_config,
            }

            logger.info(f"MCP Composer started for project {project_id} on port {project_port}")
            return project_port

        except Exception as e:
            error = f"Failed to start MCP Composer for project {project_id}: {e}"
            logger.error(error)
            raise

    async def _start_project_composer_process(
        self, project_id: str, port: int, sse_url: str, auth_config: dict[str, Any] | None = None
    ) -> subprocess.Popen:
        """Start the MCP Composer subprocess for a specific project."""
        # Build the command to start mcp-composer for this project
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
        print(f"FRAZIER: MCP COMPOSER CMD: {cmd}")

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
            # Start the subprocess
            process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Give it a moment to start
            await asyncio.sleep(2)

            # Check if process is still running
            if process.poll() is not None:
                # Process terminated, get the error
                try:
                    stdout, stderr = process.communicate(timeout=5)
                    error_msg = stderr.strip() if stderr else stdout.strip() if stdout else "Unknown error"
                    raise RuntimeError(f"MCP Composer failed to start for project {project_id}: {error_msg}")
                except subprocess.TimeoutExpired:
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

            process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            return process

    def teardown(self):
        """Clean up resources when the service is torn down."""
        # TODO: FRAZ - never awaited ?
        asyncio.run(self.stop())
