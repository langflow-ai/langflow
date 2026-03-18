"""Tests for deployment API schemas.

Security invariants and validation behaviour that must not regress.
"""

from uuid import uuid4

import pytest
from langflow.api.v1.schemas.deployments import (
    DeploymentConfigBindingUpdate,
    DeploymentConfigCreate,
    DeploymentConfigListItem,
    DeploymentConfigListResponse,
    DeploymentCreateRequest,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountGetResponse,
    DeploymentProviderAccountUpdateRequest,
    DeploymentUpdateRequest,
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
        u1, u2 = uuid4(), uuid4()
        result = FlowVersionsPatch(add=[u1, u2, u1, u2])
        assert result.add == [u1, u2]

    def test_flow_versions_patch_deduplicates_remove(self):
        u1, u2 = uuid4(), uuid4()
        result = FlowVersionsPatch(remove=[u2, u1, u2, u1])
        assert result.remove == [u2, u1]

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
        assert update.unbind is False

    def test_accepts_raw_payload_only(self):
        raw_payload = {
            "name": "new cfg",
            "description": "cfg desc",
            "environment_variables": {
                "OPENAI_API_KEY": {"value": "OPENAI_API_KEY", "source": "variable"},
            },
            "provider_config": {"region": "us-east-1", "flags": {"dry_run": True}},
        }
        update = DeploymentConfigBindingUpdate(raw_payload=raw_payload)
        assert update.raw_payload is not None
        assert update.raw_payload.model_dump() == raw_payload
        assert update.config_id is None
        assert update.unbind is False

    def test_accepts_unbind(self):
        update = DeploymentConfigBindingUpdate(unbind=True)
        assert update.unbind is True
        assert update.config_id is None
        assert update.raw_payload is None

    def test_rejects_both_config_id_and_raw_payload(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate(config_id="cfg_1", raw_payload={"name": "cfg"})

    def test_rejects_config_id_with_unbind(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate(config_id="cfg_1", unbind=True)

    def test_rejects_raw_payload_with_unbind(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate(raw_payload={"name": "cfg"}, unbind=True)

    def test_rejects_all_three(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate(config_id="cfg_1", raw_payload={"name": "cfg"}, unbind=True)

    def test_rejects_noop_empty_payload(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate()

    def test_rejects_unbind_false_alone(self):
        with pytest.raises(ValidationError, match="Exactly one of"):
            DeploymentConfigBindingUpdate(unbind=False)

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            DeploymentConfigBindingUpdate(config_id="cfg_1", unknown_field="x")


class TestDeploymentUpdateRequest:
    def test_accepts_provider_data_only(self):
        payload = DeploymentUpdateRequest(provider_data={"mode": "dry_run"})
        assert payload.provider_data == {"mode": "dry_run"}

    def test_rejects_empty_payload(self):
        with pytest.raises(ValidationError, match="At least one of"):
            DeploymentUpdateRequest()

    def test_rejects_explicit_null_only_payload(self):
        with pytest.raises(ValidationError, match="At least one of"):
            DeploymentUpdateRequest(spec=None)


class TestSharedKernelProviderPayloadCompatibility:
    def test_create_request_accepts_provider_spec_dict_through_strict_wrapper(self):
        request = DeploymentCreateRequest(
            provider_id=uuid4(),
            spec={
                "name": "deployment",
                "description": "",
                "type": "agent",
                "provider_spec": {"region": "us-east-1", "size": "small"},
            },
        )
        assert request.spec.provider_spec == {"region": "us-east-1", "size": "small"}

    def test_config_create_accepts_provider_config_dict_through_strict_wrapper(self):
        payload = DeploymentConfigCreate(
            raw_payload={
                "name": "cfg",
                "description": "cfg-desc",
                "provider_config": {"timeout_s": 30, "flags": {"dry_run": True}},
            }
        )
        assert payload.raw_payload is not None
        assert payload.raw_payload.provider_config == {"timeout_s": 30, "flags": {"dry_run": True}}


# ---------------------------------------------------------------------------
# DeploymentConfigListItem / DeploymentConfigListResponse
# ---------------------------------------------------------------------------


class TestDeploymentConfigListItem:
    def test_accepts_minimal_fields(self):
        item = DeploymentConfigListItem(id="cfg_1", name="Config")
        assert item.id == "cfg_1"
        assert item.name == "Config"
        assert item.created_at is None
        assert item.updated_at is None
        assert item.provider_data is None

    def test_does_not_have_description(self):
        assert "description" not in DeploymentConfigListItem.model_fields

    def test_accepts_all_fields(self):
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        item = DeploymentConfigListItem(
            id="cfg_1",
            name="Config",
            created_at=now,
            updated_at=now,
            provider_data={"region": "us-east-1"},
        )
        assert item.created_at == now
        assert item.provider_data == {"region": "us-east-1"}


class TestDeploymentConfigListResponse:
    def test_wraps_items_with_pagination(self):
        response = DeploymentConfigListResponse(
            configs=[
                DeploymentConfigListItem(id="cfg_1", name="Config 1"),
                DeploymentConfigListItem(id="cfg_2", name="Config 2"),
            ],
            page=1,
            size=20,
            total=2,
        )
        assert len(response.configs) == 2
        assert response.page == 1
        assert response.total == 2

    def test_pagination_defaults(self):
        response = DeploymentConfigListResponse(configs=[])
        assert response.page == 1
        assert response.size == 20
        assert response.total == 0
