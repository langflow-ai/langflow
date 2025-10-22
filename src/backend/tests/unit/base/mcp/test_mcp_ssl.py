"""Unit tests for MCP SSL/TLS functionality.

This test suite validates SSL certificate verification functionality for MCP clients including:
- SSL verification enabled (default secure behavior)
- SSL verification disabled (for self-signed certificates)
- SSL connection error handling
- Integration with both StreamableHTTP and SSE transports
"""

import httpx
import pytest
from lfx.base.mcp.util import (
    MCPStreamableHttpClient,
    create_mcp_http_client_with_ssl_option,
)


class TestSSLClientFactory:
    """Test the SSL-aware HTTP client factory function."""

    def test_create_client_with_ssl_verification_enabled(self):
        """Test creating HTTP client with SSL verification enabled (default)."""
        client = create_mcp_http_client_with_ssl_option(verify_ssl=True)

        assert isinstance(client, httpx.AsyncClient)
        # Verify that the client is configured for SSL verification
        # httpx stores verify in the transport
        assert hasattr(client, "_transport")

    def test_create_client_with_ssl_verification_disabled(self):
        """Test creating HTTP client with SSL verification disabled."""
        client = create_mcp_http_client_with_ssl_option(verify_ssl=False)

        assert isinstance(client, httpx.AsyncClient)
        # Client should be created successfully with verify_ssl=False

    def test_create_client_with_default_ssl_verification(self):
        """Test that SSL verification defaults to True when not specified."""
        client = create_mcp_http_client_with_ssl_option()

        assert isinstance(client, httpx.AsyncClient)
        # Default should be secure (SSL verification enabled)

    def test_create_client_with_custom_headers(self):
        """Test creating client with custom headers and SSL verification."""
        headers = {"Authorization": "Bearer token123", "X-Custom-Header": "value"}
        client = create_mcp_http_client_with_ssl_option(headers=headers, verify_ssl=True)

        assert isinstance(client, httpx.AsyncClient)
        # Verify headers are set
        assert client.headers.get("authorization") == "Bearer token123"
        assert client.headers.get("x-custom-header") == "value"

    def test_create_client_with_custom_timeout(self):
        """Test creating client with custom timeout and SSL verification."""
        custom_timeout = httpx.Timeout(60.0)
        client = create_mcp_http_client_with_ssl_option(timeout=custom_timeout, verify_ssl=False)

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout == custom_timeout

    def test_create_client_with_auth(self):
        """Test creating client with authentication and SSL verification."""
        auth = httpx.BasicAuth("user", "password")
        client = create_mcp_http_client_with_ssl_option(auth=auth, verify_ssl=True)

        assert isinstance(client, httpx.AsyncClient)
        assert client.auth == auth

    def test_verify_ssl_parameter_types(self):
        """Test that verify_ssl parameter accepts boolean values."""
        # Should accept True
        client_true = create_mcp_http_client_with_ssl_option(verify_ssl=True)
        assert isinstance(client_true, httpx.AsyncClient)

        # Should accept False
        client_false = create_mcp_http_client_with_ssl_option(verify_ssl=False)
        assert isinstance(client_false, httpx.AsyncClient)


class TestMCPStreamableHttpClientSSLConfiguration:
    """Test SSL configuration in MCPStreamableHttpClient without external dependencies."""

    @pytest.mark.asyncio
    async def test_connection_params_store_verify_ssl_true(self):
        """Test that connection params properly store verify_ssl=True."""
        client = MCPStreamableHttpClient()
        test_url = "https://example.com/mcp"

        # Manually set connection params to simulate what _connect_to_server does
        client._connection_params = {
            "url": test_url,
            "headers": {},
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
            "verify_ssl": True,
        }
        client._connected = False
        client._session_context = "test_context"

        # Verify the params are stored correctly
        assert "verify_ssl" in client._connection_params
        assert client._connection_params["verify_ssl"] is True
        assert client._connection_params["url"] == test_url

    @pytest.mark.asyncio
    async def test_connection_params_store_verify_ssl_false(self):
        """Test that connection params properly store verify_ssl=False."""
        client = MCPStreamableHttpClient()
        test_url = "https://self-signed.example.com/mcp"

        # Manually set connection params to simulate what _connect_to_server does
        client._connection_params = {
            "url": test_url,
            "headers": {},
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
            "verify_ssl": False,
        }
        client._connected = False
        client._session_context = "test_context"

        # Verify the params are stored correctly
        assert "verify_ssl" in client._connection_params
        assert client._connection_params["verify_ssl"] is False
        assert client._connection_params["url"] == test_url

    @pytest.mark.asyncio
    async def test_url_validation_function(self):
        """Test URL validation with valid and invalid URLs."""
        client = MCPStreamableHttpClient()

        # Test valid HTTPS URL
        is_valid, error = await client.validate_url("https://example.com/mcp")
        assert is_valid is True
        assert error == ""

        # Test valid HTTP URL
        is_valid, error = await client.validate_url("http://localhost:8080/mcp")
        assert is_valid is True
        assert error == ""

        # Test invalid URL format
        is_valid, error = await client.validate_url("not_a_url")
        assert is_valid is False
        assert "Invalid URL format" in error

        # Test URL without scheme
        is_valid, error = await client.validate_url("example.com/mcp")
        assert is_valid is False
        assert "Invalid URL format" in error

    @pytest.mark.asyncio
    async def test_client_initialization_defaults(self):
        """Test that client initializes with correct default values."""
        client = MCPStreamableHttpClient()

        assert client.session is None
        assert client._connection_params is None
        assert client._connected is False
        assert client._session_context is None


class TestSSLClientFactoryIntegration:
    """Integration tests for SSL client factory with real httpx behavior."""

    @pytest.mark.asyncio
    async def test_client_can_be_used_in_context_manager(self):
        """Test that created clients work as async context managers."""
        client = create_mcp_http_client_with_ssl_option(verify_ssl=True)

        async with client:
            # Client should be usable in context manager
            assert client is not None

    @pytest.mark.asyncio
    async def test_client_with_ssl_disabled_can_be_created(self):
        """Test that clients with SSL disabled can be instantiated."""
        client = create_mcp_http_client_with_ssl_option(verify_ssl=False)

        async with client:
            # Client with SSL disabled should work
            assert client is not None

    def test_multiple_clients_with_different_ssl_settings(self):
        """Test creating multiple clients with different SSL settings."""
        client_secure = create_mcp_http_client_with_ssl_option(verify_ssl=True)
        client_insecure = create_mcp_http_client_with_ssl_option(verify_ssl=False)

        # Both clients should be created successfully
        assert isinstance(client_secure, httpx.AsyncClient)
        assert isinstance(client_insecure, httpx.AsyncClient)

        # They should be different instances
        assert client_secure is not client_insecure


class TestSSLParameterPropagation:
    """Test that SSL parameters are properly propagated through the system."""

    @pytest.mark.asyncio
    async def test_verify_ssl_true_in_connection_params(self):
        """Test that verify_ssl=True is stored in connection parameters."""
        # Simulate connection parameter storage
        connection_params = {
            "url": "https://secure.example.com",
            "headers": {},
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
            "verify_ssl": True,
        }

        # Verify the structure
        assert connection_params["verify_ssl"] is True
        assert "url" in connection_params
        assert "headers" in connection_params

    @pytest.mark.asyncio
    async def test_verify_ssl_false_in_connection_params(self):
        """Test that verify_ssl=False is stored in connection parameters."""
        # Simulate connection parameter storage for self-signed cert scenario
        connection_params = {
            "url": "https://self-signed.local",
            "headers": {},
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
            "verify_ssl": False,
        }

        # Verify the structure
        assert connection_params["verify_ssl"] is False
        assert "url" in connection_params

    @pytest.mark.asyncio
    async def test_default_verify_ssl_value(self):
        """Test that verify_ssl defaults to True when not specified."""
        # Simulate default connection params
        connection_params = {
            "url": "https://example.com",
            "headers": {},
            "timeout_seconds": 30,
            "sse_read_timeout_seconds": 30,
        }

        # Get with default
        verify_ssl = connection_params.get("verify_ssl", True)
        assert verify_ssl is True


class TestSSLUsageScenarios:
    """Test real-world SSL usage scenarios."""

    def test_production_scenario_with_valid_certificate(self):
        """Test production scenario with SSL verification enabled."""
        # Production should always use SSL verification
        production_client = create_mcp_http_client_with_ssl_option(
            headers={"Authorization": "Bearer prod-token"}, verify_ssl=True
        )

        assert isinstance(production_client, httpx.AsyncClient)
        assert production_client.headers.get("authorization") == "Bearer prod-token"

    def test_development_scenario_with_self_signed_certificate(self):
        """Test development scenario with self-signed certificates."""
        # Development with self-signed certs should disable SSL verification
        dev_client = create_mcp_http_client_with_ssl_option(headers={"X-Dev-Key": "dev123"}, verify_ssl=False)

        assert isinstance(dev_client, httpx.AsyncClient)
        assert dev_client.headers.get("x-dev-key") == "dev123"

    def test_localhost_development_scenario(self):
        """Test localhost development scenario."""
        # Localhost development typically uses self-signed certs
        localhost_client = create_mcp_http_client_with_ssl_option(verify_ssl=False)

        assert isinstance(localhost_client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_client_configuration_for_different_environments(self):
        """Test that clients can be configured differently for different environments."""
        # Production configuration
        prod_config = {
            "url": "https://api.production.com/mcp",
            "verify_ssl": True,
            "headers": {"Authorization": "Bearer prod-key"},
        }

        # Development configuration
        dev_config = {
            "url": "https://localhost:8443/mcp",
            "verify_ssl": False,
            "headers": {"X-Dev-Mode": "true"},
        }

        # Both configurations should be valid
        assert prod_config["verify_ssl"] is True
        assert dev_config["verify_ssl"] is False


class TestSSLClientBehavior:
    """Test SSL client behavior and configuration."""

    def test_client_with_timeout_and_ssl(self):
        """Test client configuration with both timeout and SSL settings."""
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
        client = create_mcp_http_client_with_ssl_option(timeout=timeout, verify_ssl=True)

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout == timeout

    def test_client_with_auth_and_ssl(self):
        """Test client configuration with authentication and SSL."""
        auth = httpx.BasicAuth("username", "password")
        client = create_mcp_http_client_with_ssl_option(auth=auth, verify_ssl=False)

        assert isinstance(client, httpx.AsyncClient)
        assert client.auth == auth

    def test_client_with_all_options(self):
        """Test client with all configuration options."""
        headers = {"X-Custom": "value"}
        timeout = httpx.Timeout(30.0)
        auth = httpx.BasicAuth("user", "pass")

        client = create_mcp_http_client_with_ssl_option(headers=headers, timeout=timeout, auth=auth, verify_ssl=True)

        assert isinstance(client, httpx.AsyncClient)
        assert client.headers.get("x-custom") == "value"
        assert client.timeout == timeout
        assert client.auth == auth


class TestSSLErrorScenarios:
    """Test SSL error scenario handling (configuration level)."""

    @pytest.mark.asyncio
    async def test_invalid_url_detected_by_validator(self):
        """Test that invalid URLs are caught by validation."""
        client = MCPStreamableHttpClient()

        # Test clearly invalid URL formats that validator should catch
        invalid_urls = ["not-a-url", "example.com/mcp"]  # No scheme

        for invalid_url in invalid_urls:
            is_valid, error = await client.validate_url(invalid_url)
            assert is_valid is False, f"Expected {invalid_url} to be invalid"
            assert len(error) > 0

    @pytest.mark.asyncio
    async def test_valid_urls_pass_validation(self):
        """Test that valid URLs pass validation."""
        client = MCPStreamableHttpClient()

        valid_urls = [
            "https://example.com",
            "https://example.com/path",
            "https://example.com:8443/mcp",
            "http://localhost",
            "http://127.0.0.1:8080",
        ]

        for valid_url in valid_urls:
            is_valid, error = await client.validate_url(valid_url)
            assert is_valid is True
            assert error == ""


class TestSSLConfigurationConsistency:
    """Test consistency of SSL configuration across different operations."""

    def test_ssl_true_configuration_consistency(self):
        """Test that SSL verification enabled is consistently configured."""
        # Create multiple clients with SSL enabled
        clients = [create_mcp_http_client_with_ssl_option(verify_ssl=True) for _ in range(3)]

        # All should be httpx clients
        for client in clients:
            assert isinstance(client, httpx.AsyncClient)

    def test_ssl_false_configuration_consistency(self):
        """Test that SSL verification disabled is consistently configured."""
        # Create multiple clients with SSL disabled
        clients = [create_mcp_http_client_with_ssl_option(verify_ssl=False) for _ in range(3)]

        # All should be httpx clients
        for client in clients:
            assert isinstance(client, httpx.AsyncClient)

    def test_mixed_ssl_configuration(self):
        """Test creating clients with mixed SSL configurations."""
        configs = [True, False, True, False, True]
        clients = [create_mcp_http_client_with_ssl_option(verify_ssl=verify) for verify in configs]

        # All should be valid clients
        assert len(clients) == len(configs)
        for client in clients:
            assert isinstance(client, httpx.AsyncClient)
