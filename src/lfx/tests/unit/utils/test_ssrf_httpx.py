import os
import socket
from unittest.mock import AsyncMock, patch

import httpcore
import httpx
import pytest
from lfx.utils.ssrf_httpx import (
    ssrf_protected_httpx_client_kwargs_for_url,
    ssrf_safe_async_get,
    ssrf_safe_async_post,
    ssrf_safe_httpx_get,
)
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx.utils.ssrf_transport import SSRFProtectedSyncTransport, SSRFProtectedTransport


class TestSSRFSafeHTTPX:
    def test_client_kwargs_pin_idn_under_httpx_connect_host(self):
        with (
            patch(
                "lfx.utils.ssrf_httpx.validate_and_resolve_connector_url",
                return_value=("https://exämple.com/v1", ["93.184.216.34"]),
            ),
            patch("lfx.utils.ssrf_httpx.is_ssrf_protection_enabled", return_value=True),
        ):
            sync_kwargs, async_kwargs = ssrf_protected_httpx_client_kwargs_for_url("https://exämple.com/v1")

        sync_transport = sync_kwargs["transport"]
        async_transport = async_kwargs["transport"]
        assert isinstance(sync_transport, SSRFProtectedSyncTransport)
        assert isinstance(async_transport, SSRFProtectedTransport)
        assert sync_transport.pinned_ips == {"xn--exmple-cua.com": ["93.184.216.34"]}
        assert async_transport.pinned_ips == {"xn--exmple-cua.com": ["93.184.216.34"]}

    def test_literal_loopback_is_allowed_by_connector_policy(self):
        with (
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "true",
                },
                clear=True,
            ),
            patch("httpx.Client.get") as mock_get,
        ):
            ssrf_safe_httpx_get("http://127.0.0.1:1234/v1/models", timeout=5)

        mock_get.assert_called_once()

    def test_literal_loopback_is_blocked_when_connector_policy_opts_out(self):
        with (
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
                },
                clear=True,
            ),
            patch("httpx.Client.get") as mock_get,
            pytest.raises(SSRFProtectionError, match=r"127\.0\.0\.1.*blocked"),
        ):
            ssrf_safe_httpx_get("http://127.0.0.1:1234/v1/models", timeout=5)

        mock_get.assert_not_called()

    @pytest.mark.parametrize(
        ("request_fn", "client_method"),
        [(ssrf_safe_async_get, "get"), (ssrf_safe_async_post, "post")],
    )
    async def test_async_literal_loopback_is_allowed_by_connector_policy(self, request_fn, client_method):
        with (
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "true",
                },
                clear=True,
            ),
            patch(f"httpx.AsyncClient.{client_method}", new_callable=AsyncMock) as mock_request,
        ):
            await request_fn("http://127.0.0.1:1234/v1/models", timeout=5)

        mock_request.assert_awaited_once()

    @pytest.mark.parametrize(
        ("request_fn", "client_method"),
        [(ssrf_safe_async_get, "get"), (ssrf_safe_async_post, "post")],
    )
    async def test_async_literal_loopback_is_blocked_when_connector_policy_opts_out(self, request_fn, client_method):
        with (
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
                },
                clear=True,
            ),
            patch(f"httpx.AsyncClient.{client_method}", new_callable=AsyncMock) as mock_request,
            pytest.raises(SSRFProtectionError, match=r"127\.0\.0\.1.*blocked"),
        ):
            await request_fn("http://127.0.0.1:1234/v1/models", timeout=5)

        mock_request.assert_not_awaited()

    def test_direct_internal_ip_is_blocked(self):
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("httpx.Client.get") as mock_get,
            pytest.raises(SSRFProtectionError),
        ):
            ssrf_safe_httpx_get("http://169.254.169.254/latest/meta-data/", timeout=5)
        mock_get.assert_not_called()

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1\\@1.1.1.1/",
            "http://1.1.1.1\\@127.0.0.1/",
        ],
    )
    def test_ambiguous_authority_is_blocked_before_transport(self, url):
        with (
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
                    "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
                },
                clear=True,
            ),
            patch("httpx.Client.get") as mock_get,
            pytest.raises(SSRFProtectionError, match="backslash"),
        ):
            ssrf_safe_httpx_get(url, timeout=5)
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

    def test_sync_redirects_are_revalidated_and_strip_cross_origin_credentials(self):
        first_url = "https://models.example/v1/models"
        second_url = "https://catalog.example/models"
        auth = httpx.BasicAuth("user", "secret")
        responses = [
            httpx.Response(302, headers={"location": second_url}, request=httpx.Request("GET", first_url)),
            httpx.Response(200, json={"data": []}, request=httpx.Request("GET", second_url)),
        ]

        with (
            patch(
                "lfx.utils.ssrf_httpx.validate_and_resolve_connector_url",
                side_effect=lambda url: (url, []),
            ) as validate_url,
            patch("httpx.Client.get", side_effect=responses) as get,
        ):
            response = ssrf_safe_httpx_get(
                first_url,
                headers=[
                    (b"Authorization", b"Bearer secret"),
                    (b"Cookie", b"session=header-secret"),
                    (b"Proxy-Authorization", b"Basic proxy-secret"),
                    (b"User-Agent", b"langflow-test"),
                ],
                auth=auth,
                cookies={"session": "kwarg-secret"},
                timeout=5,
                follow_redirects=True,
            )

        assert response.status_code == 200
        assert [call.args[0] for call in validate_url.call_args_list] == [first_url, second_url]
        first_headers = get.call_args_list[0].kwargs["headers"]
        assert first_headers["Authorization"] == "Bearer secret"
        assert first_headers["Cookie"] == "session=header-secret"
        assert first_headers["Proxy-Authorization"] == "Basic proxy-secret"
        assert get.call_args_list[0].kwargs["auth"] is auth
        assert get.call_args_list[0].kwargs["cookies"] == {"session": "kwarg-secret"}

        second_headers = get.call_args_list[1].kwargs["headers"]
        assert dict(second_headers) == {"user-agent": "langflow-test"}
        assert "auth" not in get.call_args_list[1].kwargs
        assert "cookies" not in get.call_args_list[1].kwargs
        assert all(call.kwargs["follow_redirects"] is False for call in get.call_args_list)

    def test_sync_https_upgrade_preserves_auth_but_not_cookie_or_proxy_credentials(self):
        first_url = "http://models.example:80/v1/models"
        second_url = "https://models.example:443/v1/models"
        auth = httpx.BasicAuth("user", "secret")
        responses = [
            httpx.Response(308, headers={"location": second_url}, request=httpx.Request("GET", first_url)),
            httpx.Response(200, json={"data": []}, request=httpx.Request("GET", second_url)),
        ]

        with (
            patch(
                "lfx.utils.ssrf_httpx.validate_and_resolve_connector_url",
                side_effect=lambda url: (url, []),
            ),
            patch("httpx.Client.get", side_effect=responses) as get,
        ):
            response = ssrf_safe_httpx_get(
                first_url,
                headers=[
                    (b"Authorization", b"Bearer secret"),
                    (b"Cookie", b"session=header-secret"),
                    (b"Proxy-Authorization", b"Basic proxy-secret"),
                ],
                auth=auth,
                cookies={"session": "kwarg-secret"},
                follow_redirects=True,
            )

        assert response.status_code == 200
        second_call = get.call_args_list[1]
        assert second_call.kwargs["headers"]["Authorization"] == "Bearer secret"
        assert "Cookie" not in second_call.kwargs["headers"]
        assert "Proxy-Authorization" not in second_call.kwargs["headers"]
        assert second_call.kwargs["auth"] is auth
        assert "cookies" not in second_call.kwargs

    def test_sync_public_redirect_uses_each_hops_validated_pinned_ip(self):
        first_url = "http://first.example:8080/models"
        second_url = "http://second.example:8081/models"
        public_ips = {"first.example": "8.8.8.8", "second.example": "1.1.1.1"}
        resolved_hosts: list[str] = []
        connections: list[tuple[str, int]] = []

        def mock_getaddrinfo(host, _port, *_args, **_kwargs):
            resolved_hosts.append(host)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (public_ips[host], 0))]

        def mock_connect_tcp(_self, host, port, **_kwargs):
            connections.append((host, port))
            if host == public_ips["first.example"]:
                body = b""
                status_line = b"HTTP/1.1 302 Found\r\n"
                location = f"Location: {second_url}\r\n".encode()
            else:
                body = b'{"data":[]}'
                status_line = b"HTTP/1.1 200 OK\r\n"
                location = b""
            response_chunks = [status_line, f"Content-Length: {len(body)}\r\n".encode()]
            if location:
                response_chunks.append(location)
            response_chunks.extend([b"Content-Type: application/json\r\n", b"\r\n", body])
            return httpcore.MockStream(response_chunks)

        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch.object(httpcore.SyncBackend, "connect_tcp", mock_connect_tcp),
        ):
            response = ssrf_safe_httpx_get(first_url, timeout=5, follow_redirects=True)

        assert response.status_code == 200
        assert resolved_hosts == ["first.example", "second.example"]
        assert connections == [("8.8.8.8", 8080), ("1.1.1.1", 8081)]


class TestBoundedGet:
    """``ssrf_safe_httpx_get_bounded`` must refuse an oversized body without buffering it."""

    @staticmethod
    def _fake_streaming_client(chunk: bytes, chunks_served: list[int], *, status_code: int = 200):
        """A client whose stream yields ``chunk`` forever, recording how many were consumed."""
        import contextlib

        class _FakeResponse:
            status_code = 200
            headers: httpx.Headers = httpx.Headers({})

            def raise_for_status(self):
                return None

            def iter_bytes(self):
                while True:
                    chunks_served[0] += 1
                    yield chunk

        class _FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            @contextlib.contextmanager
            def stream(self, *_args, **_kwargs):
                yield _FakeResponse()

        _FakeResponse.status_code = status_code
        return _FakeClient()

    def test_oversized_body_is_refused_before_it_is_fully_read(self):
        """The transfer stops as soon as the cap is passed, rather than buffering everything.

        An endpoint can pass SSRF validation and still answer with an unbounded body, so
        measuring the size after a buffered read has already paid the memory cost.
        """
        from lfx.utils import ssrf_httpx

        chunk = b"x" * 1024
        chunks_served = [0]
        max_bytes = 4096

        with (
            patch.object(
                ssrf_httpx,
                "_sync_client_for_url",
                return_value=self._fake_streaming_client(chunk, chunks_served),
            ),
            patch.object(
                ssrf_httpx, "validate_and_resolve_connector_url", return_value=("http://ok.test/", ["1.2.3.4"])
            ),
            pytest.raises(ValueError, match="exceeds the maximum size"),
        ):
            ssrf_httpx.ssrf_safe_httpx_get_bounded("http://ok.test/", max_bytes=max_bytes)

        # One chunk past the cap is enough to detect it; an unbounded generator would keep
        # going forever if the reader did not stop.
        assert chunks_served[0] == (max_bytes // len(chunk)) + 1

    def test_body_within_the_cap_is_returned_intact(self):
        from lfx.utils import ssrf_httpx

        chunk = b"y" * 512

        class _BoundedResponse:
            status_code = 200
            headers = httpx.Headers({})

            def raise_for_status(self):
                return None

            def iter_bytes(self):
                yield chunk
                yield chunk

        import contextlib

        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            @contextlib.contextmanager
            def stream(self, *_args, **_kwargs):
                yield _BoundedResponse()

        with (
            patch.object(ssrf_httpx, "_sync_client_for_url", return_value=_Client()),
            patch.object(
                ssrf_httpx, "validate_and_resolve_connector_url", return_value=("http://ok.test/", ["1.2.3.4"])
            ),
        ):
            body = ssrf_httpx.ssrf_safe_httpx_get_bounded("http://ok.test/", max_bytes=4096)

        assert body == chunk * 2
