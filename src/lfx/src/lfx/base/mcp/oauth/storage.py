"""Token storage implementations for MCP OAuth 2.1.

This module provides TokenStorage implementations that satisfy the MCP SDK's
TokenStorage Protocol (mcp.client.auth.TokenStorage).

Two implementations are provided:
- InMemoryTokenStorage: Simple in-memory storage for single-session use
- FileTokenStorage: File-based storage with per-server isolation for persistence
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path  # noqa: TC003 - Path is used at runtime for file operations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


class InMemoryTokenStorage:
    """Simple in-memory token storage for single-session use.

    This storage implementation keeps tokens only in memory and does not
    persist them between sessions. Use this when:
    - Token persistence is not required
    - Running in ephemeral environments
    - Testing or development
    """

    def __init__(self) -> None:
        """Initialize empty token storage."""
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        """Retrieve stored OAuth tokens.

        Returns:
            The stored OAuthToken if available, None otherwise.
        """
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store OAuth tokens.

        Args:
            tokens: The OAuthToken to store.
        """
        self._tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Retrieve stored client information.

        Returns:
            The stored OAuthClientInformationFull if available, None otherwise.
        """
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information from dynamic registration.

        Args:
            client_info: The OAuthClientInformationFull to store.
        """
        self._client_info = client_info


class FileTokenStorage:
    """File-based token storage with per-server isolation.

    This storage implementation persists tokens to files, allowing OAuth sessions
    to survive application restarts. Files are stored with secure permissions
    (owner read/write only).

    Each MCP server gets isolated storage files based on a unique server key,
    preventing token conflicts between different servers.
    """

    def __init__(self, storage_dir: Path, server_key: str) -> None:
        """Initialize file-based token storage.

        Args:
            storage_dir: Directory where token files will be stored.
            server_key: Unique identifier for the MCP server (used in filenames).
        """
        self._storage_dir = storage_dir
        self._server_key = self._sanitize_key(server_key)
        self._ensure_storage_dir()

    def _sanitize_key(self, key: str) -> str:
        """Sanitize the server key for use in filenames.

        Args:
            key: The raw server key.

        Returns:
            A sanitized key safe for use in filenames.
        """
        # Replace characters that are problematic in filenames
        sanitized = key.replace(".", "_").replace(":", "_").replace("/", "_")
        sanitized = sanitized.replace("\\", "_").replace(" ", "_")
        # Remove any remaining non-alphanumeric characters except underscore and hyphen
        return "".join(c for c in sanitized if c.isalnum() or c in "_-")

    def _ensure_storage_dir(self) -> None:
        """Create storage directory with secure permissions if it doesn't exist."""
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        # Secure permissions: owner read/write/execute only (700)
        # On some systems (e.g., Windows), chmod may not work as expected
        with contextlib.suppress(OSError):
            self._storage_dir.chmod(0o700)

    def _token_path(self) -> Path:
        """Get the path to the token file for this server.

        Returns:
            Path to the token JSON file.
        """
        return self._storage_dir / f"{self._server_key}_tokens.json"

    def _client_info_path(self) -> Path:
        """Get the path to the client info file for this server.

        Returns:
            Path to the client info JSON file.
        """
        return self._storage_dir / f"{self._server_key}_client.json"

    async def get_tokens(self) -> OAuthToken | None:
        """Retrieve stored OAuth tokens from file.

        Returns:
            The stored OAuthToken if the file exists and is valid, None otherwise.
        """
        from mcp.shared.auth import OAuthToken

        path = self._token_path()
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return OAuthToken.model_validate(data)
        except (json.JSONDecodeError, ValueError, OSError):
            # Invalid or corrupted file - return None and let OAuth flow re-authenticate
            return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store OAuth tokens to file with secure permissions.

        Args:
            tokens: The OAuthToken to store.
        """
        path = self._token_path()
        path.write_text(tokens.model_dump_json(), encoding="utf-8")
        # Secure permissions: owner read/write only (600)
        # On some systems chmod may not work as expected
        with contextlib.suppress(OSError):
            path.chmod(0o600)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Retrieve stored client information from file.

        Returns:
            The stored OAuthClientInformationFull if the file exists and is valid,
            None otherwise.
        """
        from mcp.shared.auth import OAuthClientInformationFull

        path = self._client_info_path()
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return OAuthClientInformationFull.model_validate(data)
        except (json.JSONDecodeError, ValueError, OSError):
            # Invalid or corrupted file - return None and let OAuth flow re-register
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information to file with secure permissions.

        Args:
            client_info: The OAuthClientInformationFull to store.
        """
        path = self._client_info_path()
        path.write_text(client_info.model_dump_json(), encoding="utf-8")
        # Secure permissions: owner read/write only (600)
        # On some systems chmod may not work as expected
        with contextlib.suppress(OSError):
            path.chmod(0o600)

    def clear(self) -> None:
        """Remove all stored tokens and client info for this server.

        This is useful when the user wants to re-authenticate or when
        stored credentials are no longer valid.
        """
        for path in [self._token_path(), self._client_info_path()]:
            with contextlib.suppress(OSError):
                if path.exists():
                    path.unlink()
