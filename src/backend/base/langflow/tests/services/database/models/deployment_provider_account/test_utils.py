"""Tests for deployment_provider_account.utils URL validation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langflow.services.database.models.deployment_provider_account.utils import (
    validate_provider_url,
    validate_provider_url_optional,
)


class TestValidateProviderUrl:
    """Tests for validate_provider_url."""

    def _info(self, field_name: str = "provider_url") -> MagicMock:
        info = MagicMock()
        info.field_name = field_name
        return info

    # -- happy path --

    def test_accepts_valid_https_url(self):
        assert validate_provider_url("https://example.com/api", self._info()) == "https://example.com/api"

    def test_strips_whitespace(self):
        assert validate_provider_url("  https://example.com  ", self._info()) == "https://example.com/"

    def test_normalizes_scheme_lowercase(self):
        assert validate_provider_url("HTTPS://example.com/path", self._info()) == "https://example.com/path"

    def test_normalizes_host_lowercase(self):
        assert validate_provider_url("https://EXAMPLE.COM/path", self._info()) == "https://example.com/path"

    def test_normalizes_bare_host_to_root_path(self):
        assert validate_provider_url("https://example.com", self._info()) == "https://example.com/"

    def test_strips_trailing_slash_on_path(self):
        assert validate_provider_url("https://example.com/api/", self._info()) == "https://example.com/api"

    def test_preserves_port(self):
        assert validate_provider_url("https://example.com:8443/api", self._info()) == "https://example.com:8443/api"

    def test_preserves_query_string(self):
        result = validate_provider_url("https://example.com/api?key=val", self._info())
        assert result == "https://example.com/api?key=val"

    # -- empty / whitespace --

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_provider_url("", self._info())

    def test_rejects_whitespace(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_provider_url("   ", self._info())

    # -- scheme enforcement --

    def test_rejects_http(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            validate_provider_url("http://example.com", self._info())

    def test_rejects_ftp(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            validate_provider_url("ftp://example.com", self._info())

    def test_rejects_file(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            validate_provider_url("file:///etc/passwd", self._info())

    def test_rejects_no_scheme(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            validate_provider_url("example.com", self._info())

    def test_rejects_javascript(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            validate_provider_url("javascript:alert(1)", self._info())

    # -- private / reserved IP blocking --

    def test_rejects_loopback_v4(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://127.0.0.1/api", self._info())

    def test_rejects_loopback_v6(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://[::1]/api", self._info())

    def test_rejects_10_network(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://10.0.0.1/api", self._info())

    def test_rejects_172_16_network(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://172.16.0.1/api", self._info())

    def test_rejects_192_168_network(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://192.168.1.1/api", self._info())

    def test_rejects_link_local(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://169.254.1.1/api", self._info())

    def test_rejects_0_0_0_0(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://0.0.0.0/api", self._info())

    def test_rejects_cgn_100_64(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://100.64.0.1/api", self._info())

    def test_rejects_multicast_v4(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://224.0.0.1/api", self._info())

    def test_rejects_reserved_v4(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://240.0.0.1/api", self._info())

    def test_rejects_ipv6_unspecified(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://[::]/api", self._info())

    def test_rejects_multicast_v6(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://[ff02::1]/api", self._info())

    # -- IPv6-mapped IPv4 bypass --

    def test_rejects_ipv6_mapped_loopback(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://[::ffff:127.0.0.1]/api", self._info())

    def test_rejects_ipv6_mapped_10_network(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://[::ffff:10.0.0.1]/api", self._info())

    def test_rejects_ipv6_mapped_192_168(self):
        with pytest.raises(ValueError, match="private or reserved"):
            validate_provider_url("https://[::ffff:192.168.1.1]/api", self._info())

    def test_accepts_ipv6_mapped_public_ip(self):
        result = validate_provider_url("https://[::ffff:8.8.8.8]/api", self._info())
        assert "8.8.8.8" in result

    # -- localhost hostname --

    def test_rejects_localhost(self):
        with pytest.raises(ValueError, match="local-only hostname"):
            validate_provider_url("https://localhost/api", self._info())

    def test_rejects_localhost_localdomain(self):
        with pytest.raises(ValueError, match="local-only hostname"):
            validate_provider_url("https://localhost.localdomain/api", self._info())

    def test_rejects_subdomain_of_localhost(self):
        with pytest.raises(ValueError, match="local-only hostname"):
            validate_provider_url("https://app.localhost/api", self._info())

    # -- userinfo --

    def test_rejects_url_with_userinfo(self):
        with pytest.raises(ValueError, match="must not contain user credentials"):
            validate_provider_url("https://user:pass@example.com/api", self._info())  # pragma: allowlist secret

    def test_rejects_url_with_username_only(self):
        with pytest.raises(ValueError, match="must not contain user credentials"):
            validate_provider_url("https://user@example.com/api", self._info())

    # -- max length --

    def test_rejects_url_exceeding_max_length(self):
        long_path = "a" * 2049
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_provider_url(f"https://example.com/{long_path}", self._info())

    def test_accepts_url_at_max_length(self):
        path = "a" * (2048 - len("https://example.com/"))
        result = validate_provider_url(f"https://example.com/{path}", self._info())
        assert result.startswith("https://example.com/")

    # -- field name in error messages --

    def test_error_includes_field_name(self):
        with pytest.raises(ValueError, match="my_url"):
            validate_provider_url("http://example.com", self._info("my_url"))


class TestValidateProviderUrlOptional:
    """Tests for validate_provider_url_optional."""

    def _info(self, field_name: str = "provider_url") -> MagicMock:
        info = MagicMock()
        info.field_name = field_name
        return info

    def test_none_passthrough(self):
        assert validate_provider_url_optional(None, self._info()) is None

    def test_valid_url_passes(self):
        result = validate_provider_url_optional("https://example.com/api", self._info())
        assert result == "https://example.com/api"

    def test_invalid_url_rejected(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            validate_provider_url_optional("http://example.com", self._info())
