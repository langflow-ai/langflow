from unittest.mock import MagicMock

import pytest
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderAccountRead,
)


class TestDeploymentProviderAccountValidation:
    """Tests for DeploymentProviderAccount table model validators."""

    def _make_info(self, field_name: str) -> MagicMock:
        info = MagicMock()
        info.field_name = field_name
        return info

    def test_rejects_empty_provider_key(self):
        with pytest.raises(ValueError, match="provider_key must not be empty"):
            DeploymentProviderAccount.validate_non_empty("", self._make_info("provider_key"))

    def test_rejects_whitespace_provider_key(self):
        with pytest.raises(ValueError, match="provider_key must not be empty"):
            DeploymentProviderAccount.validate_non_empty("   ", self._make_info("provider_key"))

    def test_rejects_empty_provider_url(self):
        with pytest.raises(ValueError, match="provider_url must not be empty"):
            DeploymentProviderAccount.validate_non_empty("", self._make_info("provider_url"))

    def test_rejects_whitespace_provider_url(self):
        with pytest.raises(ValueError, match="provider_url must not be empty"):
            DeploymentProviderAccount.validate_non_empty("   ", self._make_info("provider_url"))

    def test_rejects_empty_api_key(self):
        with pytest.raises(ValueError, match="api_key must not be empty"):
            DeploymentProviderAccount.validate_non_empty("", self._make_info("api_key"))

    def test_rejects_whitespace_api_key(self):
        with pytest.raises(ValueError, match="api_key must not be empty"):
            DeploymentProviderAccount.validate_non_empty("   ", self._make_info("api_key"))

    def test_strips_whitespace(self):
        result = DeploymentProviderAccount.validate_non_empty("  watsonx  ", self._make_info("provider_key"))
        assert result == "watsonx"

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


class TestDeploymentProviderAccountRead:
    """Tests for DeploymentProviderAccountRead schema."""

    def test_excludes_api_key(self):
        assert "api_key" not in DeploymentProviderAccountRead.model_fields

    def test_has_expected_fields(self):
        expected = {
            "id",
            "user_id",
            "provider_tenant_id",
            "provider_key",
            "provider_url",
            "created_at",
            "updated_at",
        }
        assert set(DeploymentProviderAccountRead.model_fields.keys()) == expected
