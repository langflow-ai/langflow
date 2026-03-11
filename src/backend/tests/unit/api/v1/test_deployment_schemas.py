"""Tests for deployment API schemas.

Security invariants and validation behaviour that must not regress.
"""

from uuid import uuid4

import pytest
from langflow.api.v1.schemas.deployments import (
    DeploymentConfigBindingUpdate,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountGetResponse,
    DeploymentProviderAccountUpdateRequest,
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
        """DeploymentProviderAccountGetResponse.model_fields must not contain api_key."""
        assert "api_key" not in DeploymentProviderAccountGetResponse.model_fields

    def test_provider_account_response_dump_excludes_api_key(self):
        """model_dump() on a response instance must never contain api_key."""
        response = DeploymentProviderAccountGetResponse(
            id=uuid4(),
            provider_key="aws",
            provider_url="https://example.com",
        )
        dumped = response.model_dump()
        assert "api_key" not in dumped

    def test_create_schema_masks_api_key_in_repr(self):
        """SecretStr should mask the value in string representations."""
        account = DeploymentProviderAccountCreateRequest(
            provider_key="aws",
            provider_url="https://example.com",
            api_key="super-secret-key",
        )
        assert isinstance(account.api_key, SecretStr)
        assert "super-secret-key" not in repr(account)

    def test_update_schema_masks_api_key_in_repr(self):
        """SecretStr should mask the value in string representations on update."""
        account = DeploymentProviderAccountUpdateRequest(api_key="new-secret")
        assert isinstance(account.api_key, SecretStr)
        assert "new-secret" not in repr(account)


# ---------------------------------------------------------------------------
# NonEmptyStr validation
# ---------------------------------------------------------------------------


class TestNonEmptyStr:
    def test_strips_whitespace(self):
        account = DeploymentProviderAccountCreateRequest(
            provider_key="  aws  ",
            provider_url="https://example.com",
            api_key="key",
        )
        assert account.provider_key == "aws"

    def test_rejects_empty_string(self):
        with pytest.raises(ValidationError):
            DeploymentProviderAccountCreateRequest(
                provider_key="",
                provider_url="https://example.com",
                api_key="key",
            )

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValidationError):
            DeploymentProviderAccountCreateRequest(
                provider_key="   ",
                provider_url="https://example.com",
                api_key="key",
            )


# ---------------------------------------------------------------------------
# Duplicate rejection in id lists
# ---------------------------------------------------------------------------


class TestUuidIdListDedup:
    """UUID id lists silently deduplicate while preserving order."""

    def test_flow_versions_attach_deduplicates(self):
        u1, u2 = uuid4(), uuid4()
        result = FlowVersionsAttach(ids=[u1, u2, u1])
        assert result.ids == [u1, u2]

    def test_flow_versions_patch_deduplicates_add(self):
        u1 = uuid4()
        result = FlowVersionsPatch(add=[u1, u1])
        assert result.add == [u1]

    def test_flow_versions_patch_deduplicates_remove(self):
        u1 = uuid4()
        result = FlowVersionsPatch(remove=[u1, u1])
        assert result.remove == [u1]

    def test_flow_versions_patch_rejects_overlap(self):
        u1 = uuid4()
        with pytest.raises(ValidationError, match="both"):
            FlowVersionsPatch(add=[u1], remove=[u1])


# ---------------------------------------------------------------------------
# DeploymentConfigBindingUpdate validation
# ---------------------------------------------------------------------------


class TestDeploymentConfigBindingUpdate:
    def test_accepts_config_id_only(self):
        update = DeploymentConfigBindingUpdate(config_id="cfg_1")
        assert update.config_id == "cfg_1"
        assert update.raw_payload is None

    def test_accepts_raw_payload_only(self):
        update = DeploymentConfigBindingUpdate(raw_payload={"name": "new cfg"})
        assert update.raw_payload is not None
        assert update.config_id is None

    def test_accepts_explicit_null_config_id_for_unbind(self):
        update = DeploymentConfigBindingUpdate(config_id=None)
        assert update.config_id is None
        assert update.raw_payload is None

    def test_rejects_both_config_id_and_raw_payload(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate(config_id="cfg_1", raw_payload={"name": "cfg"})

    def test_rejects_null_config_id_with_raw_payload(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate(config_id=None, raw_payload={"name": "cfg"})

    def test_rejects_noop_empty_payload(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate()
