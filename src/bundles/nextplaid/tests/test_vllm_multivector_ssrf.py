"""SSRF regression coverage for the vLLM multivector embeddings endpoint.

The ``url`` passed to ``VllmMultivectorEmbeddings`` comes from a tenant-editable component
field, and every ``/pooling`` request carries ``api_key`` in an Authorization header.
"""

import socket
from unittest.mock import patch

import httpcore
import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_nextplaid.components.nextplaid.vllm_multivector_impl import VllmMultivectorEmbeddings

_FAKE_VLLM_API_KEY = "not-a-real-key"  # pragma: allowlist secret


class TestVllmMultivectorSSRF:
    @pytest.mark.parametrize(
        "blocked_url",
        [
            "http://169.254.169.254/latest/meta-data",
            "http://10.0.0.5:8000",
            "http://192.168.1.10:8000",
            "http://172.16.0.9:8000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
    )
    def test_should_block_internal_endpoint(self, blocked_url):
        """Constructing against an internal host must fail before any request is made."""
        with patch("lfx_nextplaid.components.nextplaid.vllm_multivector_impl.provider_safe_httpx_post") as mock_post:
            with pytest.raises(ValueError, match="SSRF Protection"):
                VllmMultivectorEmbeddings(url=blocked_url, model="test-model", api_key=_FAKE_VLLM_API_KEY)

            mock_post.assert_not_called()

    def test_should_allow_explicitly_allowlisted_local_vllm_server(self, monkeypatch):
        """A single-tenant operator can explicitly trust its local vLLM server."""
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "localhost")
        embeddings = VllmMultivectorEmbeddings(url="http://localhost:8000", model="test-model")

        assert embeddings.url == "http://localhost:8000"

    def test_should_respect_global_ssrf_kill_switch(self, monkeypatch):
        """Operators who disable SSRF protection keep the previous unvalidated behavior."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")

        embeddings = VllmMultivectorEmbeddings(url="http://10.0.0.5:8000", model="test-model")

        assert embeddings.url == "http://10.0.0.5:8000"

    def test_should_send_requests_through_the_provider_safe_client(self, monkeypatch):
        monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _hostname: ["93.184.216.34"])
        embeddings = VllmMultivectorEmbeddings(
            url="https://vllm.example", model="test-model", api_key=_FAKE_VLLM_API_KEY
        )

        with patch("lfx_nextplaid.components.nextplaid.vllm_multivector_impl.provider_safe_httpx_post") as mock_post:
            mock_post.return_value.json.return_value = {"data": [{"index": 0, "data": [[0.1, 0.2]]}]}
            result = embeddings.embed_query("query")

        assert result == [[0.1, 0.2]]
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {_FAKE_VLLM_API_KEY}"

    def test_should_pin_the_request_ip_after_revalidation(self):
        call_count = 0
        connected_to_ip = None

        def mock_getaddrinfo(_hostname, _port, *_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

        def mock_connect_tcp(_self, host, port, **_kwargs):
            nonlocal connected_to_ip
            connected_to_ip = host
            assert port == 8080
            body = b'{"data":[{"index":0,"data":[[0.1,0.2]]}]}'
            return httpcore.MockStream(
                [
                    b"HTTP/1.1 200 OK\r\n",
                    b"Content-Type: application/json\r\n",
                    f"Content-Length: {len(body)}\r\n".encode(),
                    b"\r\n",
                    body,
                ]
            )

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.object(httpcore.SyncBackend, "connect_tcp", mock_connect_tcp),
        ):
            embeddings = VllmMultivectorEmbeddings(
                url="http://rebind.example:8080", model="test-model", api_key=_FAKE_VLLM_API_KEY
            )
            result = embeddings.embed_query("query")

        assert result == [[0.1, 0.2]]
        assert call_count == 2
        assert connected_to_ip == "93.184.216.34"

    def test_should_block_a_rebind_before_sending_the_credential(self):
        call_count = 0

        def mock_getaddrinfo(_hostname, _port, *_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            address = "93.184.216.34" if call_count == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

        with (
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch("httpx.Client.post") as mock_post,
        ):
            embeddings = VllmMultivectorEmbeddings(
                url="http://rebind.example:8080", model="test-model", api_key=_FAKE_VLLM_API_KEY
            )
            with pytest.raises(SSRFProtectionError, match="blocked"):
                embeddings.embed_query("query")

        assert call_count == 2
        mock_post.assert_not_called()
