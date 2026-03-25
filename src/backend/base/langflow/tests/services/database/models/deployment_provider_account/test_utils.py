"""Tests for deployment_provider_account.utils URL validation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langflow.services.database.models.deployment_provider_account.utils import (
    check_provider_url_allowed,
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

    # -- userinfo --

    def test_rejects_url_with_userinfo(self):
        url = "https://user:pass@example.com/api"  # pragma: allowlist secret
        with pytest.raises(ValueError, match="must not contain user credentials"):
            validate_provider_url(url, self._info())

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


class TestCheckProviderUrlAllowed:
    """Tests for check_provider_url_allowed."""

    # -- WXO accepted hostnames --

    def test_wxo_accepts_cloud_ibm_com(self):
        check_provider_url_allowed("https://api.us-south.wxo.cloud.ibm.com/v1", "watsonx-orchestrate")

    def test_wxo_accepts_ibm_com_subdomain(self):
        check_provider_url_allowed("https://dl.watson.ibm.com/api", "watsonx-orchestrate")

    def test_wxo_accepts_bare_ibm_com(self):
        check_provider_url_allowed("https://ibm.com/api", "watsonx-orchestrate")

    # -- WXO rejected hostnames --

    def test_wxo_rejects_non_ibm_hostname(self):
        with pytest.raises(ValueError, match="not allowed for provider"):
            check_provider_url_allowed("https://evil.example.com/api", "watsonx-orchestrate")

    def test_wxo_rejects_ibm_com_suffix_trick(self):
        with pytest.raises(ValueError, match="not allowed for provider"):
            check_provider_url_allowed("https://not-ibm.com/api", "watsonx-orchestrate")

    def test_wxo_rejects_ibm_in_path_only(self):
        with pytest.raises(ValueError, match="not allowed for provider"):
            check_provider_url_allowed("https://evil.com/ibm.com", "watsonx-orchestrate")

    def test_wxo_rejects_spoofed_subdomain(self):
        with pytest.raises(ValueError, match="not allowed for provider"):
            check_provider_url_allowed("https://ibm.com.evil.com/api", "watsonx-orchestrate")

    def test_wxo_rejects_private_ip(self):
        with pytest.raises(ValueError, match="not allowed for provider"):
            check_provider_url_allowed("https://127.0.0.1/api", "watsonx-orchestrate")

    def test_wxo_rejects_localhost(self):
        with pytest.raises(ValueError, match="not allowed for provider"):
            check_provider_url_allowed("https://localhost/api", "watsonx-orchestrate")

    # -- closed-by-default --

    def test_unknown_provider_rejected(self):
        with pytest.raises(ValueError, match="is not a valid DeploymentProviderKey"):
            check_provider_url_allowed("https://anything.example.com", "unknown-provider")
