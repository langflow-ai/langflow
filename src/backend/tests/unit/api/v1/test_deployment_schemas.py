"""Tests for deployment API schemas.

Security invariants and validation behaviour that must not regress.
"""

from uuid import uuid4

import pytest
from langflow.api.v1.schemas.deployments import (
    DEPLOYMENT_DESCRIPTION_MAX_LENGTH,
    DeploymentConfigListResponse,
    DeploymentCreateRequest,
    DeploymentFlowVersionListItem,
    DeploymentFlowVersionListResponse,
    DeploymentListItem,
    DeploymentListResponse,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountGetResponse,
    DeploymentProviderAccountUpdateRequest,
    DeploymentUpdateRequest,
    FlowIdsQuery,
)
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Security: credentials must never appear in response schemas
# ---------------------------------------------------------------------------


class TestCredentialSecurity:
    """Ensure credentials are excluded from every response model."""

    def test_provider_account_response_excludes_api_key(self):
        """DeploymentProviderAccountGetResponse.model_fields must not contain api_key."""
        assert "api_key" not in DeploymentProviderAccountGetResponse.model_fields

    def test_provider_account_response_includes_provider_data(self):
        """DeploymentProviderAccountGetResponse includes non-sensitive provider metadata."""
        assert "provider_data" in DeploymentProviderAccountGetResponse.model_fields

    def test_provider_account_response_dump_excludes_credentials(self):
        """model_dump() on a response instance must never contain credential fields."""
        response = DeploymentProviderAccountGetResponse(
            id=uuid4(),
            name="staging",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            url="https://api.us-south.wxo.cloud.ibm.com",
            provider_data={"tenant_id": "tenant-1"},
        )
        dumped = response.model_dump()
        assert "api_key" not in dumped
        assert dumped["provider_data"] == {"tenant_id": "tenant-1"}
        assert "api_key" not in (dumped["provider_data"] or {})


# ---------------------------------------------------------------------------
# NonEmptyStr validation
# ---------------------------------------------------------------------------


class TestProviderAccountName:
    def test_create_accepts_valid_name(self):
        account = DeploymentProviderAccountCreateRequest(
            name="production",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            url="https://api.us-south.wxo.cloud.ibm.com",
            provider_data={"api_key": "key"},
        )
        assert account.name == "production"

    def test_create_strips_name_whitespace(self):
        account = DeploymentProviderAccountCreateRequest(
            name="  staging  ",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            url="https://api.us-south.wxo.cloud.ibm.com",
            provider_data={"api_key": "key"},
        )
        assert account.name == "staging"

    def test_create_rejects_empty_name(self):
        with pytest.raises(ValidationError, match="name"):
            DeploymentProviderAccountCreateRequest(
                name="",
                provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
                url="https://example.com",
                provider_data={"api_key": "key"},
            )

    def test_create_rejects_whitespace_only_name(self):
        with pytest.raises(ValidationError, match="name"):
            DeploymentProviderAccountCreateRequest(
                name="   ",
                provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
                url="https://example.com",
                provider_data={"api_key": "key"},
            )

    def test_create_rejects_missing_name(self):
        with pytest.raises(ValidationError):
            DeploymentProviderAccountCreateRequest(
                provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
                url="https://example.com",
                provider_data={"api_key": "key"},
            )

    def test_update_accepts_name(self):
        update = DeploymentProviderAccountUpdateRequest(name="new-name")
        assert update.name == "new-name"

    def test_update_rejects_null_name(self):
        with pytest.raises(ValidationError, match=r"name.*cannot be set to null"):
            DeploymentProviderAccountUpdateRequest(name=None)

    def test_response_includes_name(self):
        assert "name" in DeploymentProviderAccountGetResponse.model_fields


# ---------------------------------------------------------------------------
# url validation
# ---------------------------------------------------------------------------


class TestProviderUrlSchemaValidation:
    """URL validation for create schema."""

    def test_create_accepts_valid_https_url(self):
        account = DeploymentProviderAccountCreateRequest(
            name="staging",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            url="https://api.us-south.wxo.cloud.ibm.com/v1",
            provider_data={"api_key": "key"},
        )
        assert account.url == "https://api.us-south.wxo.cloud.ibm.com/v1"

    def test_create_normalizes_scheme_and_host(self):
        account = DeploymentProviderAccountCreateRequest(
            name="staging",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            url="HTTPS://API.US-SOUTH.WXO.CLOUD.IBM.COM/v1",
            provider_data={"api_key": "key"},
        )
        assert account.url == "https://api.us-south.wxo.cloud.ibm.com/v1"

    def test_create_rejects_http(self):
        with pytest.raises(ValidationError, match="https"):
            DeploymentProviderAccountCreateRequest(
                name="staging",
                provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
                url="http://example.com",
                provider_data={"api_key": "key"},
            )

    def test_create_rejects_no_scheme(self):
        with pytest.raises(ValidationError, match="https"):
            DeploymentProviderAccountCreateRequest(
                name="staging",
                provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
                url="example.com",
                provider_data={"api_key": "key"},
            )

    def test_update_rejects_url_field(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DeploymentProviderAccountUpdateRequest(url="https://new.example.com/api")

    def test_update_rejects_tenant_id_field(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DeploymentProviderAccountUpdateRequest(tenant_id="tenant-1")

    def test_create_rejects_top_level_tenant_id_field(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DeploymentProviderAccountCreateRequest(
                name="staging",
                tenant_id="tenant-1",
                provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
                url="https://api.us-south.wxo.cloud.ibm.com/v1",
                provider_data={"api_key": "key"},
            )


class TestProviderKeyEnum:
    def test_accepts_valid_enum_value(self):
        account = DeploymentProviderAccountCreateRequest(
            name="staging",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            url="https://api.us-south.wxo.cloud.ibm.com",
            provider_data={"api_key": "key"},
        )
        assert account.provider_key == DeploymentProviderKey.WATSONX_ORCHESTRATE

    def test_accepts_valid_string_value(self):
        account = DeploymentProviderAccountCreateRequest(
            name="staging",
            provider_key="watsonx-orchestrate",
            url="https://api.us-south.wxo.cloud.ibm.com",
            provider_data={"api_key": "key"},
        )
        assert account.provider_key == DeploymentProviderKey.WATSONX_ORCHESTRATE

    def test_rejects_invalid_provider_key(self):
        with pytest.raises(ValidationError):
            DeploymentProviderAccountCreateRequest(
                name="staging",
                provider_key="unknown-provider",
                url="https://example.com",
                provider_data={"api_key": "key"},
            )

    def test_rejects_empty_string(self):
        with pytest.raises(ValidationError):
            DeploymentProviderAccountCreateRequest(
                name="staging",
                provider_key="",
                url="https://example.com",
                provider_data={"api_key": "key"},
            )


class TestDeploymentUpdateRequest:
    def test_accepts_provider_data_only(self):
        payload = DeploymentUpdateRequest(provider_data={"mode": "dry_run"})
        assert payload.provider_data == {"mode": "dry_run"}

    def test_rejects_empty_payload(self):
        with pytest.raises(ValidationError, match="At least one of"):
            DeploymentUpdateRequest()

    def test_rejects_explicit_null_only_payload(self):
        with pytest.raises(ValidationError, match="At least one of"):
            DeploymentUpdateRequest(description=None)

    def test_rejects_description_over_max_length(self):
        with pytest.raises(ValidationError, match="at most"):
            DeploymentUpdateRequest(description="x" * (DEPLOYMENT_DESCRIPTION_MAX_LENGTH + 1))


class TestDeploymentSpecPayloadCompatibility:
    def test_create_request_rejects_provider_spec_dict(self):
        with pytest.raises(ValidationError, match="provider_spec"):
            DeploymentCreateRequest(
                provider_id=uuid4(),
                name="deployment",
                description="",
                type="agent",
                provider_spec={"region": "us-east-1", "size": "small"},
            )

    def test_create_request_accepts_provider_data_payload(self):
        request = DeploymentCreateRequest(
            provider_id=uuid4(),
            name="deployment",
            description="",
            type="agent",
            provider_data={"operations": []},
        )
        assert request.provider_data == {"operations": []}

    def test_create_request_rejects_description_over_max_length(self):
        with pytest.raises(ValidationError, match="at most"):
            DeploymentCreateRequest(
                provider_id=uuid4(),
                name="deployment",
                description="x" * (DEPLOYMENT_DESCRIPTION_MAX_LENGTH + 1),
                type="agent",
                provider_data={"operations": []},
            )


# ---------------------------------------------------------------------------
# DeploymentConfigListResponse / DeploymentSnapshotListResponse
# ---------------------------------------------------------------------------


class TestDeploymentConfigListResponse:
    def test_provider_data_contains_connections(self):
        response = DeploymentConfigListResponse(
            provider_data={
                "connections": [
                    {"id": "cfg_1", "name": "Config 1"},
                    {"id": "cfg_2", "name": "Config 2"},
                ],
                "scope": "shared",
            },
            page=1,
            size=20,
            total=2,
        )
        assert len(response.provider_data["connections"]) == 2
        assert response.provider_data["scope"] == "shared"
        assert response.page == 1
        assert response.total == 2

    def test_allows_null_provider_data(self):
        response = DeploymentConfigListResponse()
        assert response.provider_data is None
        assert response.page is None
        assert response.size is None
        assert response.total is None

    def test_has_provider_data_and_pagination_fields_only(self):
        assert set(DeploymentConfigListResponse.model_fields.keys()) == {
            "provider_data",
            "page",
            "size",
            "total",
        }


class TestDeploymentSnapshotListResponse:
    def test_provider_data_contains_tools(self):
        from langflow.api.v1.schemas.deployments import DeploymentSnapshotListResponse

        response = DeploymentSnapshotListResponse(
            provider_data={
                "tools": [
                    {"id": "tool-1", "name": "Tool 1"},
                    {"id": "tool-2", "name": "Tool 2"},
                ],
                "scope": "shared",
            },
            page=1,
            size=20,
            total=2,
        )
        assert len(response.provider_data["tools"]) == 2
        assert response.page == 1

    def test_allows_null_provider_data(self):
        from langflow.api.v1.schemas.deployments import DeploymentSnapshotListResponse

        response = DeploymentSnapshotListResponse()
        assert response.provider_data is None

    def test_has_provider_data_and_pagination_fields_only(self):
        from langflow.api.v1.schemas.deployments import DeploymentSnapshotListResponse

        assert set(DeploymentSnapshotListResponse.model_fields.keys()) == {
            "provider_data",
            "page",
            "size",
            "total",
        }


class TestDeploymentFlowVersionListSchemas:
    def test_flow_version_list_item_uses_attached_at(self):
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        item = DeploymentFlowVersionListItem(
            id=uuid4(),
            flow_id=uuid4(),
            version_number=3,
            attached_at=now,
            provider_snapshot_id="tool-1",
            provider_data={"app_ids": ["cfg-1"]},
        )
        assert item.attached_at == now
        assert item.provider_snapshot_id == "tool-1"
        assert item.provider_data == {"app_ids": ["cfg-1"]}

    def test_flow_version_list_item_does_not_expose_description_or_created_at(self):
        assert "description" not in DeploymentFlowVersionListItem.model_fields
        assert "created_at" not in DeploymentFlowVersionListItem.model_fields

    def test_flow_version_list_response_wraps_items_with_pagination(self):
        response = DeploymentFlowVersionListResponse(
            flow_versions=[
                DeploymentFlowVersionListItem(
                    id=uuid4(),
                    flow_id=uuid4(),
                    version_number=1,
                    attached_at=None,
                    provider_snapshot_id=None,
                    provider_data=None,
                )
            ],
            page=2,
            size=5,
            total=9,
        )
        assert len(response.flow_versions) == 1
        assert response.page == 2
        assert response.size == 5
        assert response.total == 9


class TestDeploymentListResponse:
    def test_allows_provider_only_shape(self):
        response = DeploymentListResponse(provider_data={"deployments": []})
        assert response.deployments is None
        assert response.page is None
        assert response.size is None
        assert response.total is None
        assert response.provider_data == {"deployments": []}


# ---------------------------------------------------------------------------
# FlowIdsQuery validation
# ---------------------------------------------------------------------------


class TestFlowIdsQueryValidation:
    """Validate the FlowIdsQuery annotated type used for the list_deployments filter."""

    def test_none_passes_through(self):
        from pydantic import TypeAdapter

        adapter = TypeAdapter(FlowIdsQuery)
        assert adapter.validate_python(None) is None

    def test_single_valid_uuid(self):
        from pydantic import TypeAdapter

        uid = uuid4()
        adapter = TypeAdapter(FlowIdsQuery)
        result = adapter.validate_python([uid])
        assert result == [uid]

    def test_accepts_string_uuid(self):
        from pydantic import TypeAdapter

        uid = uuid4()
        adapter = TypeAdapter(FlowIdsQuery)
        result = adapter.validate_python([str(uid)])
        assert result == [uid]

    def test_rejects_more_than_one(self):
        from pydantic import TypeAdapter, ValidationError

        adapter = TypeAdapter(FlowIdsQuery)
        with pytest.raises(ValidationError, match="at most 1"):
            adapter.validate_python([uuid4(), uuid4()])

    def test_rejects_invalid_uuid(self):
        from pydantic import TypeAdapter, ValidationError

        adapter = TypeAdapter(FlowIdsQuery)
        with pytest.raises(ValidationError):
            adapter.validate_python(["not-a-uuid"])

    def test_rejects_empty_list(self):
        from pydantic import TypeAdapter, ValidationError

        adapter = TypeAdapter(FlowIdsQuery)
        with pytest.raises(ValidationError, match="flow_ids"):
            adapter.validate_python([])

    def test_deduplicates(self):
        from pydantic import TypeAdapter

        uid = uuid4()
        adapter = TypeAdapter(FlowIdsQuery)
        result = adapter.validate_python([uid, uid])
        assert result == [uid]


# ---------------------------------------------------------------------------
# DeploymentListItem.flow_version_ids
# ---------------------------------------------------------------------------


class TestDeploymentListItemFlowVersionIds:
    def _make_item(self, **kwargs):
        defaults = {
            "id": uuid4(),
            "provider_id": uuid4(),
            "provider_key": DeploymentProviderKey.WATSONX_ORCHESTRATE,
            "name": "dep",
            "type": "agent",
            "resource_key": "rk-1",
        }
        defaults.update(kwargs)
        return DeploymentListItem(**defaults)

    def test_defaults_to_none(self):
        item = self._make_item()
        assert item.flow_version_ids is None

    def test_accepts_flow_version_ids_list(self):
        fv_id = uuid4()
        item = self._make_item(
            flow_version_ids=[fv_id],
        )
        assert item.flow_version_ids == [fv_id]

    def test_accepts_empty_list(self):
        item = self._make_item(flow_version_ids=[])
        assert item.flow_version_ids == []
