"""Tests for deployment API schemas.

Security invariants and validation behaviour that must not regress.
"""

from uuid import uuid4

import pytest
from langflow.api.v1.schemas.deployments import (
    DeploymentProviderAccountCreate,
    DeploymentProviderAccountResponse,
    DeploymentProviderAccountUpdate,
    FlowVersionsAttach,
    FlowVersionsPatch,
)
from pydantic import SecretStr, ValidationError

# ---------------------------------------------------------------------------
# Security: api_key must never appear in response schemas
# ---------------------------------------------------------------------------


class TestApiKeyWriteOnly:
    """Ensure api_key is excluded from every response model."""

    def test_provider_account_response_excludes_api_key(self):
        """DeploymentProviderAccountResponse.model_fields must not contain api_key."""
        assert "api_key" not in DeploymentProviderAccountResponse.model_fields

    def test_provider_account_response_dump_excludes_api_key(self):
        """model_dump() on a response instance must never contain api_key."""
        response = DeploymentProviderAccountResponse(
            id=uuid4(),
            provider_key="aws",
            provider_url="https://example.com",
        )
        dumped = response.model_dump()
        assert "api_key" not in dumped

    def test_create_schema_masks_api_key_in_repr(self):
        """SecretStr should mask the value in string representations."""
        account = DeploymentProviderAccountCreate(
            provider_key="aws",
            provider_url="https://example.com",
            api_key="super-secret-key",
        )
        assert isinstance(account.api_key, SecretStr)
        assert "super-secret-key" not in repr(account)

    def test_update_schema_masks_api_key_in_repr(self):
        """SecretStr should mask the value in string representations on update."""
        account = DeploymentProviderAccountUpdate(api_key="new-secret")
        assert isinstance(account.api_key, SecretStr)
        assert "new-secret" not in repr(account)


# ---------------------------------------------------------------------------
# NonEmptyStr validation
# ---------------------------------------------------------------------------


class TestNonEmptyStr:
    def test_strips_whitespace(self):
        account = DeploymentProviderAccountCreate(
            provider_key="  aws  ",
            provider_url="https://example.com",
            api_key="key",
        )
        assert account.provider_key == "aws"

    def test_rejects_empty_string(self):
        with pytest.raises(ValidationError):
            DeploymentProviderAccountCreate(
                provider_key="",
                provider_url="https://example.com",
                api_key="key",
            )

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValidationError):
            DeploymentProviderAccountCreate(
                provider_key="   ",
                provider_url="https://example.com",
                api_key="key",
            )


# ---------------------------------------------------------------------------
# Duplicate rejection in id lists
# ---------------------------------------------------------------------------


class TestIdListDuplicateRejection:
    def test_flow_versions_attach_rejects_duplicates(self):
        with pytest.raises(ValidationError, match="duplicate"):
            FlowVersionsAttach(ids=["id1", "id1"])

    def test_flow_versions_patch_rejects_duplicates_in_add(self):
        with pytest.raises(ValidationError, match="duplicate"):
            FlowVersionsPatch(add=["id1", "id1"])

    def test_flow_versions_patch_rejects_duplicates_in_remove(self):
        with pytest.raises(ValidationError, match="duplicate"):
            FlowVersionsPatch(remove=["id1", "id1"])

    def test_flow_versions_patch_rejects_overlap(self):
        with pytest.raises(ValidationError, match="both"):
            FlowVersionsPatch(add=["id1"], remove=["id1"])
