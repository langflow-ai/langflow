"""Unit tests for the SSRF-protected ``requests`` helper (``ssrf_safe_get``)."""

import ipaddress
import os
import socket
from unittest.mock import Mock, patch

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx.utils.ssrf_requests import ssrf_safe_get


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
