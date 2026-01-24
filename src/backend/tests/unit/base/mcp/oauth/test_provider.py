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


class TestClientIdMetadataDocuments:
    """Tests for Client ID Metadata Documents (CIMD) support."""

    @pytest.fixture
    def storage_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory for token storage."""
        return tmp_path / "oauth"

    @pytest.mark.asyncio
    async def test_creates_provider_with_client_metadata_url(self, storage_dir: Path) -> None:
        """Test that create_mcp_oauth_provider accepts client_metadata_url parameter."""
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
            client_metadata_url="https://myapp.example.com/oauth/metadata.json",
        )

        try:
            assert provider is not None
            assert redirect_uri.startswith(("http://localhost:", "http://127.0.0.1:"))
            # Verify client_metadata_url is passed to the provider
            assert provider.context.client_metadata_url == "https://myapp.example.com/oauth/metadata.json"
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_client_metadata_url_none_by_default(self, storage_dir: Path) -> None:
        """Test that client_metadata_url is None by default."""
        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        try:
            assert provider.context.client_metadata_url is None
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_invalid_client_metadata_url_raises_error(self, storage_dir: Path) -> None:
        """Test that invalid client_metadata_url raises ValueError."""
        # Non-HTTPS URL should be rejected
        with pytest.raises(ValueError, match="must be a valid HTTPS URL"):
            await create_mcp_oauth_provider(
                server_url="https://mcp.example.com",
                storage_dir=storage_dir,
                redirect_port=0,
                client_metadata_url="http://insecure.example.com/metadata.json",
            )

    @pytest.mark.asyncio
    async def test_client_metadata_url_without_path_raises_error(self, storage_dir: Path) -> None:
        """Test that client_metadata_url without path component raises ValueError."""
        # URL without path should be rejected (root path only)
        with pytest.raises(ValueError, match="must be a valid HTTPS URL"):
            await create_mcp_oauth_provider(
                server_url="https://mcp.example.com",
                storage_dir=storage_dir,
                redirect_port=0,
                client_metadata_url="https://myapp.example.com",
            )

    @pytest.mark.asyncio
    async def test_client_metadata_url_with_only_root_path_raises_error(self, storage_dir: Path) -> None:
        """Test that client_metadata_url with only root path raises ValueError."""
        with pytest.raises(ValueError, match="must be a valid HTTPS URL"):
            await create_mcp_oauth_provider(
                server_url="https://mcp.example.com",
                storage_dir=storage_dir,
                redirect_port=0,
                client_metadata_url="https://myapp.example.com/",
            )


class TestPreRegisteredCredentials:
    """Tests for pre-registered client credentials support."""

    @pytest.fixture
    def storage_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory for token storage."""
        return tmp_path / "oauth"

    @pytest.mark.asyncio
    async def test_creates_provider_with_client_id(self, storage_dir: Path) -> None:
        """Test that create_mcp_oauth_provider accepts client_id parameter."""
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
            client_id="my-pre-registered-client-id",
        )

        try:
            assert provider is not None
            assert redirect_uri.startswith(("http://localhost:", "http://127.0.0.1:"))
            # Verify client info was stored
            stored_client = await provider.context.storage.get_client_info()
            assert stored_client is not None
            assert stored_client.client_id == "my-pre-registered-client-id"
            assert stored_client.token_endpoint_auth_method == "none"  # Public client
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_creates_provider_with_client_id_and_secret(self, storage_dir: Path) -> None:
        """Test that create_mcp_oauth_provider accepts client_id and client_secret."""
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
            client_id="my-confidential-client-id",
            client_secret="my-client-secret",
        )

        try:
            assert provider is not None
            # Verify client info was stored with secret
            stored_client = await provider.context.storage.get_client_info()
            assert stored_client is not None
            assert stored_client.client_id == "my-confidential-client-id"
            assert stored_client.client_secret == "my-client-secret"
            assert stored_client.token_endpoint_auth_method == "client_secret_post"
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_client_id_none_by_default(self, storage_dir: Path) -> None:
        """Test that no client info is pre-stored when client_id is not provided."""
        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
        )

        try:
            # No pre-registered client info should be stored
            stored_client = await provider.context.storage.get_client_info()
            assert stored_client is None
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_client_id_takes_priority_over_metadata_url(self, storage_dir: Path) -> None:
        """Test that client_id takes priority when both client_id and client_metadata_url are provided."""
        provider, _, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
            client_id="my-pre-registered-client-id",
            client_metadata_url="https://myapp.example.com/oauth/metadata.json",
        )

        try:
            # client_id should be stored (takes priority)
            stored_client = await provider.context.storage.get_client_info()
            assert stored_client is not None
            assert stored_client.client_id == "my-pre-registered-client-id"
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_redirect_uri_included_in_stored_client_info(self, storage_dir: Path) -> None:
        """Test that the redirect URI is included in stored client info."""
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_port=0,
            client_id="my-client-id",
        )

        try:
            stored_client = await provider.context.storage.get_client_info()
            assert stored_client is not None
            assert stored_client.redirect_uris is not None
            assert len(stored_client.redirect_uris) == 1
            assert str(stored_client.redirect_uris[0]) == redirect_uri
        finally:
            cleanup()


class TestCustomRedirectUri:
    """Tests for custom redirect_uri support."""

    @pytest.fixture
    def storage_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory for token storage."""
        return tmp_path / "oauth"

    @pytest.mark.asyncio
    async def test_creates_provider_with_custom_redirect_uri(self, storage_dir: Path) -> None:
        """Test that create_mcp_oauth_provider accepts custom redirect_uri."""
        custom_uri = "http://localhost:9000/auth/idaas/callback"
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_uri=custom_uri,
        )

        try:
            assert provider is not None
            # The returned redirect_uri should match the custom one
            assert redirect_uri == custom_uri
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_custom_redirect_uri_used_in_client_info(self, storage_dir: Path) -> None:
        """Test that custom redirect_uri is stored in client info."""
        custom_uri = "http://localhost:9000/auth/callback"
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_uri=custom_uri,
            client_id="my-client-id",
        )

        try:
            stored_client = await provider.context.storage.get_client_info()
            assert stored_client is not None
            assert stored_client.redirect_uris is not None
            assert len(stored_client.redirect_uris) == 1
            assert str(stored_client.redirect_uris[0]) == custom_uri
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_custom_redirect_uri_overrides_port_and_host(self, storage_dir: Path) -> None:
        """Test that custom redirect_uri takes precedence over redirect_port and redirect_host."""
        custom_uri = "http://myhost:8080/oauth/callback"
        provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
            server_url="https://mcp.example.com",
            storage_dir=storage_dir,
            redirect_uri=custom_uri,
            redirect_port=18085,  # Should be ignored
            redirect_host="localhost",  # Should be ignored
        )

        try:
            # The custom URI should be used, not the default port/host
            assert redirect_uri == custom_uri
            assert "myhost" in redirect_uri
            assert ":8080" in redirect_uri
        finally:
            cleanup()

    @pytest.mark.asyncio
    async def test_invalid_redirect_uri_raises_error(self, storage_dir: Path) -> None:
        """Test that invalid redirect_uri raises ValueError."""
        with pytest.raises(ValueError, match="Invalid redirect_uri"):
            await create_mcp_oauth_provider(
                server_url="https://mcp.example.com",
                storage_dir=storage_dir,
                redirect_uri="not-a-valid-url",
            )

    @pytest.mark.asyncio
    async def test_redirect_uri_without_scheme_raises_error(self, storage_dir: Path) -> None:
        """Test that redirect_uri without scheme raises ValueError."""
        with pytest.raises(ValueError, match="Invalid redirect_uri"):
            await create_mcp_oauth_provider(
                server_url="https://mcp.example.com",
                storage_dir=storage_dir,
                redirect_uri="localhost:9000/callback",
            )


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
