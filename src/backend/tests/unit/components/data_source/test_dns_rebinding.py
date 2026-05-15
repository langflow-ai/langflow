"""Test DNS rebinding protection in API Request component.

This test suite verifies that the DNS pinning implementation prevents
DNS rebinding attacks that could bypass SSRF protection.
"""
# ruff: noqa: ARG001, SIM117

import os
import socket
from unittest.mock import patch

import httpcore
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
        IP from the first lookup should be used directly at the network layer.
        """
        call_count = 0
        connected_to_ip = None

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

        # Mock the network backend's connect_tcp to capture the actual IP being connected to
        async def mock_connect_tcp(self, host, port, **kwargs):
            """Capture the IP that's actually being connected to."""
            nonlocal connected_to_ip
            connected_to_ip = host
            # Return a mock stream with proper format (list of bytes)
            return httpcore.AsyncMockStream(
                [
                    b"HTTP/1.1 200 OK\r\n",
                    b"Content-Type: application/json\r\n",
                    b"Content-Length: 15\r\n",
                    b"\r\n",
                    b'{"status":"ok"}',
                ]
            )

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch.object(httpcore.AnyIOBackend, "connect_tcp", mock_connect_tcp),
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

            # Verify the connection was made to the pinned IP
            assert connected_to_ip is not None, "No TCP connection was made"
            assert connected_to_ip == "8.8.8.8", (
                f"Connection should be to pinned IP 8.8.8.8, but was to {connected_to_ip}"
            )

    @pytest.mark.asyncio
    async def test_dns_pinning_preserves_hostname_in_header(self, component):
        """Test that DNS pinning connects to pinned IP while preserving hostname for TLS.

        With network-level DNS pinning:
        - TCP connection goes to the pinned IP (93.184.216.34)
        - URL preserves the original hostname (rebinding.test)
        - This allows TLS SNI and certificate verification to work correctly

        This is important for:
        - Virtual hosting (multiple sites on same IP)
        - SNI (Server Name Indication) for HTTPS
        - Certificate verification (cert is for hostname, not IP)
        """
        connected_to_ip = None

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution."""
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

        # Mock network backend to capture TCP connection
        async def mock_connect_tcp(self, host, port, **kwargs):
            """Capture the IP that TCP connects to."""
            nonlocal connected_to_ip
            connected_to_ip = host
            return httpcore.AsyncMockStream(
                [
                    b"HTTP/1.1 200 OK\r\n",
                    b"Content-Type: application/json\r\n",
                    b"Content-Length: 15\r\n",
                    b"\r\n",
                    b'{"status":"ok"}',
                ]
            )

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch.object(httpcore.AnyIOBackend, "connect_tcp", mock_connect_tcp),
        ):
            result = await component.make_api_request()

            # Verify the request succeeded
            assert result is not None

            # Verify TCP connection was made to the pinned IP
            assert connected_to_ip is not None, "No TCP connection was made"
            assert connected_to_ip == "93.184.216.34", (
                f"TCP connection should be to pinned IP 93.184.216.34, but was to {connected_to_ip}"
            )

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
        """Test that DNS pinning works with IPv6 addresses.

        With network-level DNS pinning:
        - TCP connection goes to the IPv6 address
        - URL preserves the original hostname
        - IPv6 addresses don't need brackets in connect_tcp (only in URLs)
        """
        component.url_input = "http://ipv6.example.com/api"
        connected_to_ip = None

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution to return IPv6."""
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:4860:4860::8888", 0))]

        # Mock network backend to capture TCP connection
        async def mock_connect_tcp(self, host, port, **kwargs):
            """Capture the IP that TCP connects to."""
            nonlocal connected_to_ip
            connected_to_ip = host
            return httpcore.AsyncMockStream(
                [
                    b"HTTP/1.1 200 OK\r\n",
                    b"Content-Type: application/json\r\n",
                    b"Content-Length: 15\r\n",
                    b"\r\n",
                    b'{"status":"ok"}',
                ]
            )

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch.object(httpcore.AnyIOBackend, "connect_tcp", mock_connect_tcp),
        ):
            result = await component.make_api_request()

            # Verify the request succeeded
            assert isinstance(result, Data)

            # Verify TCP connection was made to the IPv6 address
            assert connected_to_ip is not None, "No TCP connection was made"
            assert connected_to_ip == "2001:4860:4860::8888", (
                f"TCP connection should be to IPv6 2001:4860:4860::8888, but was to {connected_to_ip}"
            )

    @pytest.mark.asyncio
    async def test_dns_pinning_with_allowlisted_host(self, component):
        """Test that allowlisted hosts bypass DNS pinning and preserve original hostname."""
        component.url_input = "http://internal.example.com:8080/api"  # Use a valid hostname format
        captured_request = None

        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            """Mock DNS resolution."""
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0))]

        # Mock the transport's handle_async_request to capture the rewritten request
        async def mock_handle_async_request(_self, request):
            """Capture the request after transport rewrite."""
            nonlocal captured_request
            captured_request = request
            return httpx.Response(200, json={"status": "ok"}, request=request)

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
                    "LANGFLOW_SSRF_ALLOWED_HOSTS": "internal.example.com,10.0.0.1",
                },
            ),
            # Patch get_allowed_hosts to return the allowlist directly
            patch(
                "lfx.utils.ssrf_protection.get_allowed_hosts",
                return_value=["internal.example.com", "10.0.0.1"],
            ),
            patch.object(httpx.AsyncHTTPTransport, "handle_async_request", mock_handle_async_request),
        ):
            result = await component.make_api_request()

            # Verify the request succeeded
            assert isinstance(result, Data)
            assert captured_request is not None, "Transport did not capture request"

            # Verify the original hostname is preserved (no DNS pinning for allowlisted hosts)
            url_str = str(captured_request.url)
            assert "internal.example.com" in url_str, f"Allowlisted host should preserve hostname: {url_str}"
            assert "10.0.0.1" not in url_str, f"Allowlisted host should not use IP: {url_str}"

    @pytest.mark.asyncio
    async def test_dns_pinning_with_multiple_ips_fallback(self, component):
        """Test that DNS pinning tries multiple IPs when first one fails (dual-stack/load balancing)."""
        component.url_input = "http://dual-stack.example.com/api"

        # Track which IPs were attempted
        attempted_ips = []

        def mock_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
            """Mock DNS resolution to return multiple IPs (IPv4 and IPv6)."""
            if host == "dual-stack.example.com":
                # Return both IPv4 and IPv6 addresses (dual-stack)
                return [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),  # IPv4
                    (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", 0)),  # IPv6
                ]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, 0))]

        async def mock_connect_tcp(self, host, port, **kwargs):
            """Mock connection that fails on first IP, succeeds on second."""
            nonlocal attempted_ips
            attempted_ips.append(host)

            # First IP fails (simulating IPv4 unreachable)
            if host == "93.184.216.34":
                msg = "Connection refused"
                raise OSError(msg)

            # Second IP succeeds (IPv6 works)
            if host == "2606:2800:220:1:248:1893:25c8:1946":
                return httpcore.AsyncMockStream(
                    [
                        b"HTTP/1.1 200 OK\r\n",
                        b"Content-Type: application/json\r\n",
                        b"Content-Length: 15\r\n",
                        b"\r\n",
                        b'{"status":"ok"}',
                    ]
                )

            msg = f"Unexpected host: {host}"
            raise OSError(msg)

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch.object(httpcore.AnyIOBackend, "connect_tcp", mock_connect_tcp),
        ):
            # Execute the request
            result = await component.make_api_request()

            # Verify both IPs were attempted in order
            assert len(attempted_ips) == 2
            assert attempted_ips[0] == "93.184.216.34"  # IPv4 tried first
            assert attempted_ips[1] == "2606:2800:220:1:248:1893:25c8:1946"  # IPv6 tried second

            # Verify the result (should succeed with second IP)
            assert isinstance(result, Data)
            assert result.data is not None
