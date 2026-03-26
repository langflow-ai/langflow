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

    def test_rejects_url_exceeding_max_length(self):
        long_path = "a" * 2049
        with pytest.raises(ValueError, match="exceeds maximum length"):
            DeploymentProviderAccount.validate_url(f"https://example.com/{long_path}", self._make_info())

    def test_rejects_userinfo(self):
        url = "https://user:pass@example.com/api"  # pragma: allowlist secret
        with pytest.raises(ValueError, match="must not contain user credentials"):
            DeploymentProviderAccount.validate_url(url, self._make_info())


class TestDeploymentProviderAccountTenantConsistency:
    """Tests for the model_validator that checks tenant/URL consistency.

    SQLModel table models bypass Pydantic validators in __init__ (ORM compat),
    so we use model_validate to trigger the model_validator.
    """

    _BASE = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "name": "test",
        "api_key": "secret",  # pragma: allowlist secret
        "provider_key": DeploymentProviderKey.WATSONX_ORCHESTRATE,
    }

    def test_rejects_inconsistent_tenant_and_url(self):
        with pytest.raises(Exception, match="does not match"):
            DeploymentProviderAccount.model_validate(
                {
                    **self._BASE,
                    "provider_url": "https://api.us-south.wxo.cloud.ibm.com/instances/acct-123/agents",
                    "provider_tenant_id": "wrong-tenant",
                }
            )

    def test_accepts_consistent_tenant_and_url(self):
        account = DeploymentProviderAccount.model_validate(
            {
                **self._BASE,
                "provider_url": "https://api.us-south.wxo.cloud.ibm.com/instances/acct-123/agents",
                "provider_tenant_id": "acct-123",
            }
        )
        assert account.provider_tenant_id == "acct-123"

    def test_accepts_none_tenant(self):
        account = DeploymentProviderAccount.model_validate(
            {
                **self._BASE,
                "provider_url": "https://api.us-south.wxo.cloud.ibm.com/instances/acct-123/agents",
                "provider_tenant_id": None,
            }
        )
        assert account.provider_tenant_id is None

    def test_accepts_url_without_tenant_segment(self):
        account = DeploymentProviderAccount.model_validate(
            {
                **self._BASE,
                "provider_url": "https://api.us-south.wxo.cloud.ibm.com/api/v1",
                "provider_tenant_id": "any-tenant",
            }
        )
        assert account.provider_tenant_id == "any-tenant"


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
