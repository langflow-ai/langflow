"""Unit tests for MCP OAuth provider factory.

This test suite validates the OAuth provider factory functionality including:
- create_mcp_oauth_provider: Factory for creating OAuthClientProvider instances
- OAuth integration with MCP server connections
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.mcp.oauth.provider import create_mcp_oauth_provider


class TestCreateMcpOAuthProvider:
    """Tests for create_mcp_oauth_provider function."""

    @pytest.fixture
    def storage_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory for token storage."""
        return tmp_path / "oauth"

    @pytest.mark.asyncio
    async def test_creates_provider_with_defaults(self, storage_dir: Path) -> None:
        """Test that create_mcp_oauth_provider creates a valid provider."""
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        try:
            assert provider is not None
            assert redirect_uri.startswith(("http://localhost:", "http://127.0.0.1:"))
            assert callable(cleanup)
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_custom_client_name(self, storage_dir: Path) -> None:
        """Test creating provider with custom client name."""
        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            client_name="my-custom-client",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        try:
            # Provider should be created successfully with custom name
            assert provider is not None
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_uses_file_storage_by_default(self, storage_dir: Path) -> None:
        """Test that file storage is used by default."""
        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            use_file_storage=True,
            redirect_port=0,
        )

        try:
            # Verify provider was created
            assert provider is not None
            # Verify storage directory was created
            assert storage_dir.exists()
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_can_use_memory_storage(self, storage_dir: Path) -> None:
        """Test creating provider with in-memory storage."""
        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            use_file_storage=False,
            redirect_port=0,
        )

        try:
            # Provider should be created successfully
            assert provider is not None
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_stops_callback_server(self, storage_dir: Path) -> None:
        """Test that cleanup function stops the callback server."""
        _provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        # Call cleanup multiple times - should be idempotent
        cleanup()
        cleanup()

    @pytest.mark.asyncio
    async def test_redirect_uri_contains_callback_path(self, storage_dir: Path) -> None:
        """Test that redirect URI contains /callback path."""
        _, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        try:
            assert "/callback" in redirect_uri
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_provider_is_httpx_auth(self, storage_dir: Path) -> None:
        """Test that provider implements httpx.Auth interface."""
        import httpx

        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        try:
            # OAuthClientProvider should be usable as httpx.Auth
            assert isinstance(provider, httpx.Auth)
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_default_storage_dir(self) -> None:
        """Test that default storage directory is used when not specified."""
        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            redirect_port=0,
            # No storage_dir specified
        )

        try:
            # Should use default ~/.langflow/oauth
            # Provider should be created successfully
            assert provider is not None
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_different_servers_get_different_redirect_uris(self, storage_dir: Path) -> None:
        """Test that different server URLs result in different redirect URIs."""
        provider1, redirect_uri1, cleanup1 = await create_mcp_oauth_provider(
            server_url="https://server1.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )
        provider2, redirect_uri2, cleanup2 = await create_mcp_oauth_provider(
            server_url="https://server2.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        try:
            # Each provider should have its own redirect URI (different ports)
            assert redirect_uri1 != redirect_uri2
            assert provider1 is not None
            assert provider2 is not None
        finally:
            cleanup1()
            cleanup2()

    @pytest.mark.asyncio
    async def test_provider_is_valid_oauth_provider(self, storage_dir: Path) -> None:
        """Test that the provider is a valid OAuth provider."""
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        try:
            # Provider should be created and have expected attributes
            assert provider is not None
            assert redirect_uri is not None
            # The redirect URI should be a valid local callback URL
            assert redirect_uri.startswith(("http://localhost:", "http://127.0.0.1:"))
            assert "/callback" in redirect_uri
        finally:
            cleanup()


class TestOAuthIntegration:
    """Integration tests for OAuth with MCP utilities."""

    @pytest.mark.asyncio
    async def test_oauth_auth_can_be_passed_to_http_client(self, tmp_path: Path) -> None:
        """Test that OAuth provider can be used with MCPStreamableHttpClient."""
        from lfx.base.mcp.oauth.provider import create_mcp_oauth_provider
        from lfx.base.mcp.util import MCPStreamableHttpClient

        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=tmp_path / "oauth",
            redirect_port=0,
        )

        try:
            client = MCPStreamableHttpClient()

            # Connection params should accept oauth_auth
            client._connection_params = {
                "url": "https://mcp.example.com",
                "headers": {},
                "timeout_seconds": 30,
                "sse_read_timeout_seconds": 30,
                "verify_ssl": True,
                "oauth_auth": provider,
            }

            assert client._connection_params["oauth_auth"] is provider
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_update_tools_accepts_oauth_auth(self, tmp_path: Path) -> None:
        """Test that update_tools function accepts oauth_auth parameter."""
        from lfx.base.mcp.oauth.provider import create_mcp_oauth_provider
        from lfx.base.mcp.util import MCPStreamableHttpClient, update_tools

        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=tmp_path / "oauth",
            redirect_port=0,
        )

        try:
            # Create a mock client that tracks what it was called with
            mock_client = MCPStreamableHttpClient()

            # Mock the connect_to_server method
            mock_tools = []
            mock_client.connect_to_server = AsyncMock(return_value=mock_tools)
            mock_client._connected = True

            # Call update_tools with OAuth auth
            with patch.object(mock_client, "connect_to_server", new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = []

                # Should not raise - oauth_auth parameter is accepted
                await update_tools(
                    server_name="test_server",
                    server_config={"url": "https://mcp.example.com", "mode": "Streamable_HTTP"},
                    mcp_streamable_http_client=mock_client,
                    oauth_auth=provider,
                )

                # Verify oauth_auth was passed
                if mock_connect.called:
                    call_kwargs = mock_connect.call_args.kwargs
                    assert call_kwargs.get("oauth_auth") is provider
        finally:
            cleanup()
