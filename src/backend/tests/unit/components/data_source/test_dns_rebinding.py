"""Test DNS rebinding protection in API Request component.

This test suite verifies that the DNS pinning implementation prevents
DNS rebinding attacks that could bypass SSRF protection.
"""
# ruff: noqa: ARG001, SIM117

import os
import socket
from unittest.mock import patch

import httpx
import pytest
from lfx.components.data_source.api_request import APIRequestComponent
from lfx.schema import Data


class TestDNSRebindingProtection:
    """Test DNS rebinding attack prevention through DNS pinning."""

    @pytest.fixture
    def component(self):
        """Create a basic API request component."""
        return APIRequestComponent(
            url_input="http://rebinding.test:8080/api",
            method="GET",
            headers=[],
            body=[],
            timeout=30,
            follow_redirects=False,
            save_to_file=False,
            include_httpx_metadata=False,
            mode="URL",
            curl_input="",
            query_params={},
        )

    @pytest.mark.asyncio
    async def test_dns_pinning_prevents_rebinding_attack(self, component):
        """Test that DNS pinning prevents DNS rebinding attacks.

        This test simulates a DNS rebinding attack where:
        1. First DNS lookup (validation): returns public IP (8.8.8.8)
        2. Second DNS lookup (httpx): would return localhost (127.0.0.1)

        With DNS pinning, the second lookup should NOT happen - the validated
        IP from the first lookup should be used directly.
        """
        call_count = 0
        pinned_url_used = None

        def mock_getaddrinfo(_hostname, _port, *_args, **_kwargs):
            """Mock DNS resolution to simulate rebinding attack."""
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call (during validation): return public IP
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]
            # Second call (during httpx request): return localhost
            # This simulates the DNS rebinding attack
            # With DNS pinning, this should NOT be called
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

        # Mock the transport's handle_async_request to capture the actual URL used
        async def mock_handle_async_request(_self, request):
            """Capture the URL that's actually being requested."""
            nonlocal pinned_url_used
            pinned_url_used = str(request.url)
            # Return a mock response
            return httpx.Response(200, json={"status": "ok"}, request=request)

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch.object(httpx.AsyncHTTPTransport, "handle_async_request", mock_handle_async_request),
        ):
            # Execute the request
            result = await component.make_api_request()

            # Verify the request succeeded
            assert result is not None

            # CRITICAL CHECK: DNS should only be called once (during validation)
            # If called twice, DNS pinning failed and the attack succeeded
            assert call_count == 1, (
                f"DNS was called {call_count} times. Expected 1 (validation only). "
                "DNS pinning failed - the component is vulnerable to DNS rebinding!"
            )

            # Verify the pinned URL was used
            assert pinned_url_used is not None, "No HTTP request was made"
            assert "8.8.8.8" in pinned_url_used, f"Request didn't use pinned IP 8.8.8.8: {pinned_url_used}"
            assert "127.0.0.1" not in pinned_url_used, (
                f"Request used rebinded IP 127.0.0.1 (VULNERABILITY!): {pinned_url_used}"
            )

    @pytest.mark.asyncio
    async def test_dns_pinning_preserves_hostname_in_header(self, component):
        """Test that DNS pinning preserves the original hostname in the Host header.

        This is important for:
        - Virtual hosting (multiple sites on same IP)
        - SNI (Server Name Indication) for HTTPS
        """

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution."""
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

        mock_response = httpx.Response(200, json={"status": "ok"})

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("httpx.AsyncClient.request", return_value=mock_response) as mock_request,
        ):
            await component.make_api_request()

            # Verify the Host header contains the original hostname
            called_headers = mock_request.call_args[1].get("headers", {})
            assert "Host" in called_headers or "host" in called_headers, "Host header not set"

            # The Host header should be the original hostname, not the IP
            host_value = called_headers.get("Host") or called_headers.get("host")
            assert host_value == "rebinding.test", f"Host header should be 'rebinding.test', got: {host_value}"

    @pytest.mark.asyncio
    async def test_dns_pinning_with_direct_ip_address(self, component):
        """Test that direct IP addresses work correctly (no DNS pinning needed)."""
        component.url_input = "http://93.184.216.34:8080/api"

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution - should not be called for direct IPs."""
            # For direct IPs, socket.getaddrinfo is still called but returns the same IP
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

        mock_response = httpx.Response(200, json={"status": "ok"})

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("httpx.AsyncClient.request", return_value=mock_response) as mock_request,
        ):
            result = await component.make_api_request()

            # Verify the request succeeded
            assert isinstance(result, Data)
            assert mock_request.called

    @pytest.mark.asyncio
    async def test_dns_pinning_disabled_when_protection_disabled(self, component):
        """Test that DNS pinning is skipped when SSRF protection is disabled."""
        call_count = 0

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution."""
            nonlocal call_count
            call_count += 1
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]

        mock_response = httpx.Response(200, json={"status": "ok"})

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "false"}),
            patch("httpx.AsyncClient.request", return_value=mock_response) as mock_request,
        ):
            result = await component.make_api_request()

            # Verify the request succeeded
            assert isinstance(result, Data)
            assert mock_request.called

            # When protection is disabled, DNS pinning is not used
            # So DNS might be called multiple times (once by httpx)
            # This is expected behavior when protection is off

    @pytest.mark.asyncio
    async def test_dns_pinning_blocks_private_ip_resolution(self, component):
        """Test that DNS pinning blocks hostnames that resolve to private IPs."""
        component.url_input = "http://internal.example.com/api"

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution to return private IP."""
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 0))]

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
        ):
            # Should raise ValueError due to SSRF protection
            with pytest.raises(ValueError, match="SSRF Protection"):
                await component.make_api_request()

    @pytest.mark.asyncio
    async def test_dns_pinning_with_ipv6(self, component):
        """Test that DNS pinning works with IPv6 addresses."""
        component.url_input = "http://ipv6.example.com/api"

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution to return IPv6."""
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:4860:4860::8888", 0))]

        mock_response = httpx.Response(200, json={"status": "ok"})

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("httpx.AsyncClient.request", return_value=mock_response) as mock_request,
        ):
            result = await component.make_api_request()

            # Verify the request succeeded
            assert isinstance(result, Data)
            assert mock_request.called

            # Verify IPv6 address is properly formatted in URL (with brackets)
            called_url = str(mock_request.call_args[1]["url"])
            assert "[2001:4860:4860::8888]" in called_url, f"IPv6 not properly formatted: {called_url}"

    @pytest.mark.asyncio
    async def test_dns_pinning_with_allowlisted_host(self, component):
        """Test that allowlisted hosts bypass DNS pinning."""
        component.url_input = "http://localhost:11434/api"  # Ollama default

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution."""
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

        mock_response = httpx.Response(200, json={"status": "ok"})

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
                    "LANGFLOW_SSRF_ALLOWED_HOSTS": "localhost,127.0.0.1",
                },
            ),
            patch("httpx.AsyncClient.request", return_value=mock_response) as mock_request,
        ):
            result = await component.make_api_request()

            # Verify the request succeeded (allowlisted host)
            assert isinstance(result, Data)
            assert mock_request.called


# Made with Bob
