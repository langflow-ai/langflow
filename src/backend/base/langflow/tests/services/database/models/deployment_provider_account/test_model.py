from unittest.mock import MagicMock

import pytest
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderAccountRead,
    DeploymentProviderKey,
)


class TestDeploymentProviderAccountValidation:
    """Tests for DeploymentProviderAccount table model validators."""

    def _make_info(self, field_name: str) -> MagicMock:
        info = MagicMock()
        info.field_name = field_name
        return info

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            DeploymentProviderAccount.validate_non_empty("", self._make_info("name"))

    def test_rejects_whitespace_name(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            DeploymentProviderAccount.validate_non_empty("   ", self._make_info("name"))

    def test_strips_name_whitespace(self):
        result = DeploymentProviderAccount.validate_non_empty("  staging  ", self._make_info("name"))
        assert result == "staging"

    def test_rejects_empty_api_key(self):
        with pytest.raises(ValueError, match="api_key must not be empty"):
            DeploymentProviderAccount.validate_non_empty("", self._make_info("api_key"))

    def test_rejects_whitespace_api_key(self):
        with pytest.raises(ValueError, match="api_key must not be empty"):
            DeploymentProviderAccount.validate_non_empty("   ", self._make_info("api_key"))

    def test_strips_name_and_api_key_whitespace(self):
        result = DeploymentProviderAccount.validate_non_empty("  value  ", self._make_info("name"))
        assert result == "value"

    def test_provider_key_enum_has_expected_members(self):
        assert DeploymentProviderKey.WATSONX_ORCHESTRATE.value == "watsonx-orchestrate"

    def test_normalizes_blank_tenant_id_to_none(self):
        result = DeploymentProviderAccount.normalize_tenant_id("   ")
        assert result is None

    def test_normalizes_empty_tenant_id_to_none(self):
        result = DeploymentProviderAccount.normalize_tenant_id("")
        assert result is None

    def test_strips_tenant_id(self):
        result = DeploymentProviderAccount.normalize_tenant_id("  tenant-1  ")
        assert result == "tenant-1"

    def test_none_tenant_id_passthrough(self):
        result = DeploymentProviderAccount.normalize_tenant_id(None)
        assert result is None


class TestProviderUrlValidation:
    """Tests for the provider_url validator on DeploymentProviderAccount."""

    def _make_info(self, field_name: str = "provider_url") -> MagicMock:
        info = MagicMock()
        info.field_name = field_name
        return info

    def test_accepts_valid_https_url(self):
        result = DeploymentProviderAccount.validate_url("https://example.com/api", self._make_info())
        assert result == "https://example.com/api"

    def test_strips_whitespace(self):
        result = DeploymentProviderAccount.validate_url("  https://example.com  ", self._make_info())
        assert result == "https://example.com/"

    def test_normalizes_scheme_to_lowercase(self):
        result = DeploymentProviderAccount.validate_url("HTTPS://Example.COM/path", self._make_info())
        assert result == "https://example.com/path"

    def test_normalizes_trailing_slash(self):
        result = DeploymentProviderAccount.validate_url("https://example.com/", self._make_info())
        assert result == "https://example.com/"

    def test_normalizes_bare_host_adds_root_path(self):
        result = DeploymentProviderAccount.validate_url("https://example.com", self._make_info())
        assert result == "https://example.com/"

    def test_preserves_path_segments(self):
        result = DeploymentProviderAccount.validate_url("https://example.com/instances/abc123/api", self._make_info())
        assert result == "https://example.com/instances/abc123/api"

    def test_preserves_port(self):
        result = DeploymentProviderAccount.validate_url("https://example.com:8443/api", self._make_info())
        assert result == "https://example.com:8443/api"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="provider_url must not be empty"):
            DeploymentProviderAccount.validate_url("", self._make_info())

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError, match="provider_url must not be empty"):
            DeploymentProviderAccount.validate_url("   ", self._make_info())

    def test_rejects_http_scheme(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            DeploymentProviderAccount.validate_url("http://example.com", self._make_info())

    def test_rejects_ftp_scheme(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            DeploymentProviderAccount.validate_url("ftp://example.com", self._make_info())

    def test_rejects_no_scheme(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            DeploymentProviderAccount.validate_url("example.com", self._make_info())

    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            DeploymentProviderAccount.validate_url("file:///etc/passwd", self._make_info())

    def test_rejects_javascript_scheme(self):
        with pytest.raises(ValueError, match="must use the https scheme"):
            DeploymentProviderAccount.validate_url("javascript:alert(1)", self._make_info())

    def test_rejects_loopback_v4(self):
        with pytest.raises(ValueError, match="must not point to a private or reserved IP address"):
            DeploymentProviderAccount.validate_url("https://127.0.0.1/api", self._make_info())

    def test_rejects_loopback_ipv6(self):
        with pytest.raises(ValueError, match="must not point to a private or reserved IP address"):
            DeploymentProviderAccount.validate_url("https://[::1]/api", self._make_info())

    def test_rejects_10_network(self):
        with pytest.raises(ValueError, match="must not point to a private or reserved IP address"):
            DeploymentProviderAccount.validate_url("https://10.0.0.1/api", self._make_info())

    def test_rejects_172_16_network(self):
        with pytest.raises(ValueError, match="must not point to a private or reserved IP address"):
            DeploymentProviderAccount.validate_url("https://172.16.0.1/api", self._make_info())

    def test_rejects_192_168_network(self):
        with pytest.raises(ValueError, match="must not point to a private or reserved IP address"):
            DeploymentProviderAccount.validate_url("https://192.168.1.1/api", self._make_info())

    def test_rejects_link_local(self):
        with pytest.raises(ValueError, match="must not point to a private or reserved IP address"):
            DeploymentProviderAccount.validate_url("https://169.254.1.1/api", self._make_info())

    def test_rejects_0_0_0_0(self):
        with pytest.raises(ValueError, match="must not point to a private or reserved IP address"):
            DeploymentProviderAccount.validate_url("https://0.0.0.0/api", self._make_info())

    def test_rejects_url_exceeding_max_length(self):
        long_path = "a" * 2049
        with pytest.raises(ValueError, match="exceeds maximum length"):
            DeploymentProviderAccount.validate_url(f"https://example.com/{long_path}", self._make_info())

    def test_rejects_ipv6_mapped_loopback(self):
        with pytest.raises(ValueError, match="must not point to a private or reserved IP address"):
            DeploymentProviderAccount.validate_url("https://[::ffff:127.0.0.1]/api", self._make_info())

    def test_rejects_localhost_hostname(self):
        with pytest.raises(ValueError, match="local-only hostname"):
            DeploymentProviderAccount.validate_url("https://localhost/api", self._make_info())

    def test_rejects_userinfo(self):
        url = "https://user:pass@example.com/api"  # pragma: allowlist secret
        with pytest.raises(ValueError, match="must not contain user credentials"):
            DeploymentProviderAccount.validate_url(url, self._make_info())


class TestDeploymentProviderAccountRead:
    """Tests for DeploymentProviderAccountRead schema."""

    def test_excludes_api_key(self):
        assert "api_key" not in DeploymentProviderAccountRead.model_fields

    def test_has_expected_fields(self):
        expected = {
            "id",
            "user_id",
            "name",
            "provider_tenant_id",
            "provider_key",
            "provider_url",
            "created_at",
            "updated_at",
        }
        assert set(DeploymentProviderAccountRead.model_fields.keys()) == expected
