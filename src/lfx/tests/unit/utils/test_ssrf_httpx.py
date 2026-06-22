import os
import socket
from unittest.mock import patch

import httpcore
import pytest
from lfx.utils.ssrf_httpx import ssrf_safe_httpx_get
from lfx.utils.ssrf_protection import SSRFProtectionError


class TestSSRFSafeHTTPX:
    def test_direct_internal_ip_is_blocked(self):
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("httpx.Client.get") as mock_get,
            pytest.raises(SSRFProtectionError),
        ):
            ssrf_safe_httpx_get("http://169.254.169.254/latest/meta-data/", timeout=5)
        mock_get.assert_not_called()

    def test_sync_dns_pinning_prevents_rebinding_attack(self):
        call_count = 0
        connected_to_ip = None

        def mock_getaddrinfo(_hostname, _port, *_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

        def mock_connect_tcp(_self, host, port, **_kwargs):
            nonlocal connected_to_ip
            assert port == 8080
            connected_to_ip = host
            return httpcore.MockStream(
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
            patch.object(httpcore.SyncBackend, "connect_tcp", mock_connect_tcp),
        ):
            response = ssrf_safe_httpx_get("http://rebinding.test:8080/models", timeout=5)

        assert response.status_code == 200
        assert call_count == 1
        assert connected_to_ip == "8.8.8.8"
