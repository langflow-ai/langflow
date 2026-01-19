"""Unit tests for MCP OAuth storage implementations.

This test suite validates the TokenStorage implementations including:
- InMemoryTokenStorage: Simple in-memory storage
- FileTokenStorage: File-based persistent storage
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from lfx.base.mcp.oauth.storage import FileTokenStorage, InMemoryTokenStorage


class TestInMemoryTokenStorage:
    """Tests for InMemoryTokenStorage class."""

    @pytest.fixture
    def storage(self) -> InMemoryTokenStorage:
        """Create an InMemoryTokenStorage instance."""
        return InMemoryTokenStorage()

    @pytest.mark.asyncio
    async def test_initial_state_is_empty(self, storage: InMemoryTokenStorage) -> None:
        """Test that storage starts with no tokens or client info."""
        assert await storage.get_tokens() is None
        assert await storage.get_client_info() is None

    @pytest.mark.asyncio
    async def test_stores_and_retrieves_tokens(self, storage: InMemoryTokenStorage) -> None:
        """Test storing and retrieving OAuth tokens."""
        from mcp.shared.auth import OAuthToken

        token = OAuthToken(access_token="test_access_token", token_type="Bearer")

        await storage.set_tokens(token)
        retrieved = await storage.get_tokens()

        assert retrieved is not None
        assert retrieved.access_token == "test_access_token"
        assert retrieved.token_type == "Bearer"

    @pytest.mark.asyncio
    async def test_stores_and_retrieves_client_info(self, storage: InMemoryTokenStorage) -> None:
        """Test storing and retrieving client information."""
        from mcp.shared.auth import OAuthClientInformationFull

        client_info = OAuthClientInformationFull(
            client_id="test_client_id",
            client_name="test_client",
            redirect_uris=["http://localhost/callback"],
        )

        await storage.set_client_info(client_info)
        retrieved = await storage.get_client_info()

        assert retrieved is not None
        assert retrieved.client_id == "test_client_id"
        assert retrieved.client_name == "test_client"

    @pytest.mark.asyncio
    async def test_tokens_can_be_overwritten(self, storage: InMemoryTokenStorage) -> None:
        """Test that tokens can be overwritten with new values."""
        from mcp.shared.auth import OAuthToken

        token1 = OAuthToken(access_token="first_token", token_type="Bearer")
        token2 = OAuthToken(access_token="second_token", token_type="Bearer")

        await storage.set_tokens(token1)
        await storage.set_tokens(token2)
        retrieved = await storage.get_tokens()

        assert retrieved is not None
        assert retrieved.access_token == "second_token"

    @pytest.mark.asyncio
    async def test_tokens_with_refresh_token(self, storage: InMemoryTokenStorage) -> None:
        """Test storing tokens with refresh token."""
        from mcp.shared.auth import OAuthToken

        token = OAuthToken(
            access_token="test_access",
            token_type="Bearer",
            refresh_token="test_refresh",
            expires_in=3600,
        )

        await storage.set_tokens(token)
        retrieved = await storage.get_tokens()

        assert retrieved is not None
        assert retrieved.access_token == "test_access"
        assert retrieved.refresh_token == "test_refresh"
        assert retrieved.expires_in == 3600


class TestFileTokenStorage:
    """Tests for FileTokenStorage class."""

    @pytest.fixture
    def storage_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory for token storage."""
        return tmp_path / "oauth"

    @pytest.fixture
    def storage(self, storage_dir: Path) -> FileTokenStorage:
        """Create a FileTokenStorage instance."""
        return FileTokenStorage(storage_dir, "test_server")

    def test_creates_storage_directory(self, storage_dir: Path) -> None:
        """Test that storage directory is created on initialization."""
        assert not storage_dir.exists()

        FileTokenStorage(storage_dir, "test_server")

        assert storage_dir.exists()
        assert storage_dir.is_dir()

    def test_sanitizes_server_key(self, storage_dir: Path) -> None:
        """Test that server keys are sanitized for use in filenames."""
        storage = FileTokenStorage(storage_dir, "server.example.com:8080/path")

        # The sanitized key should not contain problematic characters
        token_path = storage._token_path()
        assert "." not in token_path.stem.replace("_tokens", "")
        assert ":" not in token_path.stem
        assert "/" not in token_path.stem

    @pytest.mark.asyncio
    async def test_initial_state_is_empty(self, storage: FileTokenStorage) -> None:
        """Test that storage starts with no tokens or client info."""
        assert await storage.get_tokens() is None
        assert await storage.get_client_info() is None

    @pytest.mark.asyncio
    async def test_stores_and_retrieves_tokens(self, storage: FileTokenStorage) -> None:
        """Test storing and retrieving OAuth tokens from file."""
        from mcp.shared.auth import OAuthToken

        token = OAuthToken(access_token="file_test_token", token_type="Bearer")

        await storage.set_tokens(token)
        retrieved = await storage.get_tokens()

        assert retrieved is not None
        assert retrieved.access_token == "file_test_token"

    @pytest.mark.asyncio
    async def test_stores_and_retrieves_client_info(self, storage: FileTokenStorage) -> None:
        """Test storing and retrieving client information from file."""
        from mcp.shared.auth import OAuthClientInformationFull

        client_info = OAuthClientInformationFull(
            client_id="file_client_id",
            client_name="file_client",
            redirect_uris=["http://localhost/callback"],
        )

        await storage.set_client_info(client_info)
        retrieved = await storage.get_client_info()

        assert retrieved is not None
        assert retrieved.client_id == "file_client_id"

    @pytest.mark.asyncio
    async def test_tokens_persist_across_instances(self, storage_dir: Path) -> None:
        """Test that tokens persist and can be retrieved by new instances."""
        from mcp.shared.auth import OAuthToken

        server_key = "persistent_test"
        token = OAuthToken(access_token="persistent_token", token_type="Bearer")

        # Store with first instance
        storage1 = FileTokenStorage(storage_dir, server_key)
        await storage1.set_tokens(token)

        # Retrieve with new instance
        storage2 = FileTokenStorage(storage_dir, server_key)
        retrieved = await storage2.get_tokens()

        assert retrieved is not None
        assert retrieved.access_token == "persistent_token"

    @pytest.mark.asyncio
    async def test_different_servers_are_isolated(self, storage_dir: Path) -> None:
        """Test that different servers have isolated token storage."""
        from mcp.shared.auth import OAuthToken

        storage1 = FileTokenStorage(storage_dir, "server1")
        storage2 = FileTokenStorage(storage_dir, "server2")

        token1 = OAuthToken(access_token="token_for_server1", token_type="Bearer")
        token2 = OAuthToken(access_token="token_for_server2", token_type="Bearer")

        await storage1.set_tokens(token1)
        await storage2.set_tokens(token2)

        retrieved1 = await storage1.get_tokens()
        retrieved2 = await storage2.get_tokens()

        assert retrieved1 is not None
        assert retrieved1.access_token == "token_for_server1"
        assert retrieved2 is not None
        assert retrieved2.access_token == "token_for_server2"

    @pytest.mark.asyncio
    async def test_handles_corrupted_token_file(self, storage: FileTokenStorage) -> None:
        """Test that corrupted token files are handled gracefully."""
        # Write invalid JSON to token file
        token_path = storage._token_path()
        token_path.write_text("not valid json {{{", encoding="utf-8")

        # Should return None instead of raising
        result = await storage.get_tokens()
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_corrupted_client_info_file(self, storage: FileTokenStorage) -> None:
        """Test that corrupted client info files are handled gracefully."""
        # Write invalid JSON to client info file
        client_path = storage._client_info_path()
        client_path.write_text("not valid json", encoding="utf-8")

        # Should return None instead of raising
        result = await storage.get_client_info()
        assert result is None

    def test_clear_removes_files(self, storage: FileTokenStorage) -> None:
        """Test that clear() removes both token and client info files."""
        # Create files
        token_path = storage._token_path()
        client_path = storage._client_info_path()
        token_path.write_text("{}", encoding="utf-8")
        client_path.write_text("{}", encoding="utf-8")

        assert token_path.exists()
        assert client_path.exists()

        storage.clear()

        assert not token_path.exists()
        assert not client_path.exists()

    def test_clear_handles_missing_files(self, storage: FileTokenStorage) -> None:
        """Test that clear() handles missing files gracefully."""
        # Files don't exist yet, should not raise
        storage.clear()

    @pytest.mark.skipif(os.name == "nt", reason="File permissions work differently on Windows")
    @pytest.mark.asyncio
    async def test_token_file_has_secure_permissions(self, storage: FileTokenStorage) -> None:
        """Test that token files are created with secure permissions."""
        from mcp.shared.auth import OAuthToken

        token = OAuthToken(access_token="secure_token", token_type="Bearer")
        await storage.set_tokens(token)

        token_path = storage._token_path()
        mode = token_path.stat().st_mode & 0o777

        # Should be 0o600 (owner read/write only)
        assert mode == 0o600

    @pytest.mark.skipif(os.name == "nt", reason="File permissions work differently on Windows")
    def test_storage_dir_has_secure_permissions(self, storage_dir: Path) -> None:
        """Test that storage directory is created with secure permissions."""
        FileTokenStorage(storage_dir, "test")

        mode = storage_dir.stat().st_mode & 0o777

        # Should be 0o700 (owner read/write/execute only)
        assert mode == 0o700
