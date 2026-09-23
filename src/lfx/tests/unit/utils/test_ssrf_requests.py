"""Unit tests for the SSRF-protected ``requests`` helper (``ssrf_safe_get``)."""

import ipaddress
import os
import socket
from unittest.mock import Mock, patch

import pytest
import requests
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx.utils.ssrf_requests import (
    REDIRECT_STATUS_CODES,
    refuse_aiohttp_redirects,
    refuse_redirects,
    ssrf_safe_get,
)


def _resolve_public(host, *_args, **_kwargs):
    """socket.getaddrinfo stub: hostnames resolve to a public IP, literal IPs to themselves."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        ip = "93.184.216.34"  # hostname -> public IP
    else:
        ip = host  # literal IP -> itself
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, 0))]


def _response(status_code=200, *, location=None, body=b"ok"):
    """Build a minimal mock ``requests.Response``."""
    response = Mock()
    response.status_code = status_code
    response.headers = {"Location": location} if location else {}
    response.content = body
    response.raise_for_status = Mock()
    return response


class TestSSRFSafeGet:
    def test_direct_internal_ip_is_blocked(self):
        """A literal internal IP is blocked before any request is made."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("requests.get") as mock_get,
            pytest.raises(SSRFProtectionError),
        ):
            ssrf_safe_get("http://127.0.0.1:8080/secret", timeout=5)
        mock_get.assert_not_called()

    def test_backslash_authority_parser_confusion_is_blocked(self):
        """A URL interpreted differently by stdlib and Requests is blocked before transport."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("requests.get") as mock_get,
            pytest.raises(SSRFProtectionError, match="backslash"),
        ):
            ssrf_safe_get("http://127.0.0.1\\@1.1.1.1/", timeout=5)
        mock_get.assert_not_called()

    @pytest.mark.parametrize(
        "url",
        [
            "http://feed.example.com/folder\\item",
            "http://feed.example.com/rss?filter=folder\\item",
        ],
    )
    def test_backslash_outside_authority_is_allowed(self, url):
        """Backslashes outside the authority retain Requests' existing quoting behavior."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", return_value=_response()) as mock_get,
        ):
            ssrf_safe_get(url, timeout=5)
        mock_get.assert_called_once()

    def test_cloud_metadata_endpoint_is_blocked(self):
        """The cloud metadata endpoint is blocked before any request is made."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("requests.get") as mock_get,
            pytest.raises(SSRFProtectionError),
        ):
            ssrf_safe_get("http://169.254.169.254/latest/meta-data/", timeout=5)
        mock_get.assert_not_called()

    def test_public_url_returns_response(self):
        """A public URL passes validation and returns the response."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", return_value=_response(200, body=b"feed")) as mock_get,
        ):
            response = ssrf_safe_get("http://feed.example.com/rss", timeout=5)
        assert response.status_code == 200
        assert mock_get.call_count == 1
        # Auto-redirects must be disabled so each hop can be validated.
        assert mock_get.call_args.kwargs["allow_redirects"] is False

    def test_redirect_to_internal_is_blocked(self):
        """A public URL that redirects to an internal address is blocked at the redirect hop."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch(
                "requests.get",
                return_value=_response(302, location="http://169.254.169.254/latest/meta-data/"),
            ) as mock_get,
            pytest.raises(SSRFProtectionError),
        ):
            ssrf_safe_get("http://public-redirector.example.com/go", timeout=5)
        # Only the first (public) hop was requested; the internal redirect was never followed.
        assert mock_get.call_count == 1

    def test_public_redirect_chain_is_followed(self):
        """A chain of public redirects is followed to the final response."""
        responses = [
            _response(302, location="http://hop2.example.com/b"),
            _response(307, location="http://hop3.example.com/c"),
            _response(200, body=b"final"),
        ]
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", side_effect=responses) as mock_get,
        ):
            response = ssrf_safe_get("http://hop1.example.com/a", timeout=5)
        assert response.status_code == 200
        assert response.content == b"final"
        assert mock_get.call_count == 3

    def test_relative_redirect_resolved_against_current_url(self):
        """A relative redirect Location resolves against the current URL and is followed."""
        responses = [_response(302, location="/next"), _response(200, body=b"final")]
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", side_effect=responses) as mock_get,
        ):
            response = ssrf_safe_get("http://feed.example.com/a", timeout=5)
        assert response.status_code == 200
        assert mock_get.call_args_list[1].args[0] == "http://feed.example.com/next"

    def test_scheme_change_redirect_is_blocked(self):
        """A redirect that switches to a non-http(s) scheme is blocked."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", return_value=_response(302, location="file:///etc/passwd")),
            pytest.raises(SSRFProtectionError),
        ):
            ssrf_safe_get("http://feed.example.com/a", timeout=5)

    def test_too_many_redirects_raises(self):
        """A redirect loop is bounded and raises instead of looping forever."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch(
                "requests.get",
                return_value=_response(302, location="http://loop.example.com/again"),
            ) as mock_get,
            pytest.raises(SSRFProtectionError, match="Exceeded the maximum"),
        ):
            ssrf_safe_get("http://loop.example.com/start", timeout=5, max_redirects=3)
        assert mock_get.call_count == 4  # max_redirects + 1 attempts

    def test_protection_disabled_allows_internal(self):
        """With SSRF protection disabled, no validation is applied (user opted out)."""
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "false"}),
            patch("requests.get", return_value=_response(200, body=b"internal")) as mock_get,
        ):
            response = ssrf_safe_get("http://127.0.0.1:8080/secret", timeout=5)
        assert response.status_code == 200
        assert mock_get.call_count == 1

    def test_cross_host_redirect_strips_credential_headers(self):
        """Credential-bearing headers are dropped when a redirect crosses to a different host."""
        responses = [_response(302, location="http://other.example.com/b"), _response(200, body=b"final")]
        headers = {
            "Authorization": "Bearer secret-token",
            "cookie": "session=abc",  # lowercase: stripping must be case-insensitive
            "Proxy-Authorization": "Basic xyz",
            "User-Agent": "langflow-test",
        }
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", side_effect=responses) as mock_get,
        ):
            ssrf_safe_get("http://feed.example.com/a", timeout=5, headers=headers)
        # First hop (intended host) keeps all headers; second hop (cross-host) drops the secrets.
        assert mock_get.call_args_list[0].kwargs["headers"] == headers
        assert mock_get.call_args_list[1].kwargs["headers"] == {"User-Agent": "langflow-test"}
        # The caller's dict must not be mutated.
        assert "Authorization" in headers

    def test_same_host_redirect_keeps_headers(self):
        """Headers (including credentials) are preserved across a same-host redirect."""
        responses = [_response(302, location="http://feed.example.com/next"), _response(200, body=b"final")]
        headers = {"Authorization": "Bearer secret-token", "User-Agent": "langflow-test"}
        with (
            patch.dict(os.environ, {"LANGFLOW_SSRF_PROTECTION_ENABLED": "true"}),
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("requests.get", side_effect=responses) as mock_get,
        ):
            ssrf_safe_get("http://feed.example.com/a", timeout=5, headers=headers)
        assert mock_get.call_args_list[1].kwargs["headers"] == headers


class TestRefuseRedirects:
    """Transports that own their session cannot re-validate hops, so they must not follow one."""

    @staticmethod
    def _resp(status_code, location=None):
        """A response mock whose ``is_redirect`` follows requests' own definition."""
        response = Mock()
        response.status_code = status_code
        response.headers = {"Location": location} if location else {}
        response.url = "https://api.example.com/v1/chat/completions"
        response.is_redirect = bool(location) and status_code in REDIRECT_STATUS_CODES
        return response

    @staticmethod
    def _session():
        return refuse_redirects(requests.Session())

    @pytest.mark.parametrize("status", sorted(REDIRECT_STATUS_CODES))
    def test_should_raise_on_any_redirect_status(self, status):
        response = self._resp(status, "https://elsewhere.example.com/v1")

        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            list(self._session().resolve_redirects(response, Mock()))

    def test_should_raise_on_a_same_host_port_change(self):
        """The Authorization header survives a same-host redirect, including a new port."""
        response = self._resp(302, "http://api.example.com:9999/internal")

        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            list(self._session().resolve_redirects(response, Mock()))

    def test_should_be_a_no_op_for_a_normal_response(self):
        assert list(self._session().resolve_redirects(self._resp(200), Mock())) == []

    def test_should_not_raise_on_the_yield_requests_probe(self):
        """Session.send probes for a follow-up request without following it; that is not egress."""
        response = self._resp(302, "https://elsewhere.example.com/v1")

        assert list(self._session().resolve_redirects(response, Mock(), yield_requests=True)) == []

    def test_should_leave_the_rest_of_the_session_intact(self):
        session = requests.Session()
        session.verify = "/etc/ssl/corp-ca.pem"
        session.headers["X-Marker"] = "kept"

        hardened = refuse_redirects(session)

        assert hardened is session
        assert hardened.verify == "/etc/ssl/corp-ca.pem"
        assert hardened.headers["X-Marker"] == "kept"


class _StubAiohttpSession:
    """The two attributes ``refuse_aiohttp_redirects`` touches, without depending on aiohttp.

    ``aiohttp`` is not an lfx dependency -- only bundles that ship an SDK using it pull it in
    -- so the helper duck-types the session and these tests do the same. The real transport is
    exercised against the pinned SDK in ``src/bundles/lfx-bundles/tests/test_nvidia_component.py``.
    """

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []

    async def _request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._response


class _StubAiohttpResponse:
    def __init__(self, status, location=None):
        self.status = status
        self.headers = {"Location": location} if location else {}
        self.url = "https://api.example.com/v1/chat/completions"
        self.closed = False

    def close(self):
        self.closed = True


class TestRefuseAiohttpRedirects:
    """The async transports need the same refusal; aiohttp follows redirects by default too."""

    @staticmethod
    def _session(status, location=None):
        response = _StubAiohttpResponse(status, location)
        session = _StubAiohttpSession(response)
        return refuse_aiohttp_redirects(session), response

    @pytest.mark.parametrize("status", sorted(REDIRECT_STATUS_CODES))
    async def test_should_raise_on_any_redirect_status(self, status):
        session, response = self._session(status, "https://elsewhere.example.com/v1")

        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            await session._request("POST", "https://api.example.com/v1/chat/completions")

        assert response.closed, "the refused response must be released, not left dangling"

    async def test_should_raise_on_a_same_host_port_change(self):
        """A same-host hop keeps the Authorization header, so a new port is still a new service."""
        session, _ = self._session(307, "http://api.example.com:9999/internal")

        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            await session._request("POST", "https://api.example.com/v1/chat/completions")

    async def test_should_disable_redirect_following_on_every_request(self):
        """Refusing the response is the backstop; aiohttp must not have followed it already."""
        session, _ = self._session(200)

        await session._request("POST", "https://api.example.com/v1", json={"prompt": "hi"})

        assert session.calls[0]["allow_redirects"] is False
        assert session.calls[0]["json"] == {"prompt": "hi"}

    async def test_should_override_a_caller_supplied_allow_redirects(self):
        session, _ = self._session(200)

        await session._request("GET", "https://api.example.com/v1/models", allow_redirects=True)

        assert session.calls[0]["allow_redirects"] is False

    async def test_should_return_a_normal_response_untouched(self):
        session, response = self._session(200)

        assert await session._request("GET", "https://api.example.com/v1/models") is response
        assert not response.closed

    def test_should_return_the_same_session(self):
        session = _StubAiohttpSession(_StubAiohttpResponse(200))

        assert refuse_aiohttp_redirects(session) is session
