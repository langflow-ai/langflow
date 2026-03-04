"""Deployment API schemas.

Identifier domains
------------------
This module draws a strict boundary between two identifier domains:

* **Langflow-managed (UUID)** -- database primary keys owned by the Langflow
  backend.  All ``id``, ``provider_id``, ``project_id``, and ``deployment_id``
  fields on API request/response schemas are UUIDs that reference rows in the
  Langflow database.

* **Provider-owned (str)** -- opaque references assigned by the external
  deployment provider.  These appear as ``reference_id``, ``config_id``,
  ``resource_key``, ``execution_id``, and inside ``provider_*`` payload dicts.
  They are typed as ``str`` because the provider may use any format.

The ``provider_data`` / ``provider_result`` / ``provider_spec`` /
``provider_input`` dicts are transparent pass-through containers whose
contents are entirely defined by the provider adapter.

Service-layer schema reuse
--------------------------
A small number of service-layer schemas are imported directly because they
carry no identifier fields and their shapes are stable:

* ``BaseDeploymentData`` -- name, description, type, provider_spec
* ``BaseDeploymentDataUpdate`` -- name, description
* ``DeploymentConfig`` -- config payload (name, description, env vars, provider config)
* ``DeploymentType`` -- shared vocabulary enum
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from lfx.services.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    DeploymentConfig,
    DeploymentType,
)
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------


def _validate_str_id_list(values: list[str], *, field_name: str) -> list[str]:
    """Strip, reject empty, and deduplicate a list of string identifiers."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            msg = f"{field_name} must not contain empty values."
            raise ValueError(msg)
        if value not in seen:
            seen.add(value)
            cleaned.append(value)
    return cleaned


def _normalize_optional_str(value: str | None) -> str | None:
    """Strip whitespace from an optional string, rejecting whitespace-only values."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        msg = "Field must not be empty or whitespace."
        raise ValueError(msg)
    return normalized


def validate_flow_version_id_query(values: list[str]) -> list[str]:
    """Validate and deduplicate flow_version_ids received as query parameters."""
    return _validate_str_id_list(values, field_name="flow_version_ids")


# ---------------------------------------------------------------------------
# Provider sub-resource schemas
# ---------------------------------------------------------------------------


class ProviderAccountCreate(BaseModel):
    model_config = {"extra": "forbid"}

    provider_tenant_id: str | None = Field(default=None, min_length=1, description="Provider tenant/organization id.")
    provider_key: str = Field(min_length=1, description="Deployment provider key.")
    provider_url: str = Field(min_length=1, description="Deployment provider URL.")
    api_key: str = Field(min_length=1, description="Deployment provider API key.")

    @field_validator("provider_key", "provider_url", "api_key")
    @classmethod
    def normalize_required_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "Field must not be empty or whitespace."
            raise ValueError(msg)
        return normalized

    @field_validator("provider_tenant_id")
    @classmethod
    def normalize_provider_tenant_id(cls, value: str | None) -> str | None:
        return _normalize_optional_str(value)


class ProviderAccountUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    provider_tenant_id: str | None = Field(default=None, description="Provider tenant/organization id.")
    provider_key: str | None = Field(default=None, description="Deployment provider key.")
    provider_url: str | None = Field(default=None, description="Deployment provider URL.")
    api_key: str | None = Field(default=None, description="Deployment provider API key.")

    @field_validator("provider_tenant_id", "provider_key", "provider_url", "api_key")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> ProviderAccountUpdate:
        if all(
            value is None for value in (self.provider_tenant_id, self.provider_key, self.provider_url, self.api_key)
        ):
            msg = "At least one field must be provided for update."
            raise ValueError(msg)
        return self


class ProviderAccountResponse(BaseModel):
    id: UUID  # Langflow DB
    provider_tenant_id: str | None  # provider-owned tenant/org identifier
    provider_key: str
    provider_url: str
    created_at: datetime | None
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# Deployment resource schemas
# ---------------------------------------------------------------------------


class DeploymentTypeListResponse(BaseModel):
    """Supported deployment types for a provider account."""

    deployment_types: list[DeploymentType]


class DeploymentSummary(BaseModel):
    """Compact deployment representation used for list items and duplicate results."""

    id: UUID  # Langflow DB
    name: str
    type: DeploymentType
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict[str, Any] | None = None  # provider-owned passthrough


class DeploymentGetResponse(DeploymentSummary):
    """Full deployment detail."""

    description: str | None = None


class DeploymentListItem(DeploymentSummary):
    """Extended deployment summary with list-specific fields."""

    resource_key: str = Field(description="Provider-owned stable resource identifier.")
    attached_count: int = Field(default=0, ge=0, description="Number of flow versions attached to this deployment.")


class DeploymentListResponse(BaseModel):
    deployments: list[DeploymentListItem]
    deployment_type: DeploymentType | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class ProviderAccountListResponse(BaseModel):
    providers: list[ProviderAccountResponse]
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class DeploymentCreateResponse(BaseModel):
    """API response for deployment creation."""

    id: UUID  # Langflow DB
    name: str
    description: str = ""
    type: DeploymentType | None = None
    provider_result: dict[str, Any] | None = None  # provider-owned passthrough


class DeploymentUpdateResponse(BaseModel):
    """API response for deployment update."""

    id: UUID  # Langflow DB
    provider_result: dict[str, Any] | None = None  # provider-owned passthrough


class DeploymentStatusResponse(BaseModel):
    """API response for deployment status/health."""

    id: UUID  # Langflow DB
    provider_data: dict[str, Any] | None = None  # provider-owned passthrough


class RedeployResponse(BaseModel):
    """API response for redeployment."""

    id: UUID  # Langflow DB
    provider_result: dict[str, Any] | None = None  # provider-owned passthrough


class DeploymentDuplicateResponse(DeploymentSummary):
    pass


class DeploymentDuplicateParams(BaseModel):
    """Parameters for duplicating a deployment."""

    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, description="Name for the duplicated deployment. Auto-generated if omitted.")
    description: str | None = Field(default=None, description="Description for the duplicated deployment.")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Flow versions sub-resource schemas
# ---------------------------------------------------------------------------


class FlowVersionsAttach(BaseModel):
    """Flow version ids to attach during deployment creation."""

    model_config = {"extra": "forbid"}

    ids: list[str] = Field(
        min_length=1,
        description="Flow version ids to attach to the deployment.",
    )

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, values: list[str]) -> list[str]:
        return _validate_str_id_list(values, field_name="ids")


class FlowVersionsPatch(BaseModel):
    """Add or remove flow version bindings on an existing deployment."""

    model_config = {"extra": "forbid"}

    add: list[str] | None = Field(
        None,
        description="Flow version ids to attach to the deployment. Omit to leave unchanged.",
    )
    remove: list[str] | None = Field(
        None,
        description="Flow version ids to detach from the deployment. Omit to leave unchanged.",
    )

    @field_validator("add", "remove")
    @classmethod
    def validate_id_lists(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return _validate_str_id_list(values, field_name="flow_version_ids")

    @model_validator(mode="after")
    def validate_operations(self):
        add_values = self.add or []
        remove_values = self.remove or []

        if not add_values and not remove_values:
            msg = "At least one of 'add' or 'remove' must be provided."
            raise ValueError(msg)

        overlap = set(add_values).intersection(remove_values)
        if overlap:
            ids = ", ".join(sorted(overlap))
            msg = f"Flow version ids cannot be present in both 'add' and 'remove': {ids}."
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Deployment config sub-resource schemas (API-owned)
# ---------------------------------------------------------------------------


class DeploymentConfigCreate(BaseModel):
    """Config input for deployment creation.

    Exactly one of ``reference_id`` or ``raw_payload`` must be provided.
    """

    model_config = {"extra": "forbid"}

    reference_id: str | None = Field(
        default=None,
        min_length=1,
        description="Provider-owned config reference id to bind to the deployment.",
    )
    raw_payload: DeploymentConfig | None = Field(
        default=None,
        description="Config payload to create and bind to the deployment.",
    )

    @field_validator("reference_id")
    @classmethod
    def normalize_reference_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            msg = "reference_id must not be empty or whitespace."
            raise ValueError(msg)
        return normalized

    @model_validator(mode="after")
    def validate_exactly_one(self) -> DeploymentConfigCreate:
        if (self.reference_id is None) == (self.raw_payload is None):
            msg = "Exactly one of 'reference_id' or 'raw_payload' must be provided."
            raise ValueError(msg)
        return self


class DeploymentConfigBindingUpdate(BaseModel):
    """Config binding patch for an existing deployment."""

    model_config = {"extra": "forbid"}

    config_id: str | None = Field(
        default=None,
        description="Provider-owned config id to bind to the deployment. Use null to unbind.",
    )

    @field_validator("config_id")
    @classmethod
    def normalize_config_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            msg = "config_id must not be empty or whitespace."
            raise ValueError(msg)
        return normalized


# ---------------------------------------------------------------------------
# Deployment create / update request schemas
# ---------------------------------------------------------------------------


class DeploymentCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider_id: UUID = Field(description="Langflow DB provider account id.")
    spec: BaseDeploymentData = Field(description="Deployment metadata (service-layer schema, no ID fields).")
    project_id: UUID | None = Field(
        default=None,
        description="Langflow DB project id to persist the deployment under. Defaults to user's Starter Project.",
    )
    flow_version_ids: FlowVersionsAttach | None = Field(
        default=None,
        description="Flow version ids to attach to the deployment.",
    )
    config: DeploymentConfigCreate | None = Field(default=None, description="Deployment configuration.")


class DeploymentUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    spec: BaseDeploymentDataUpdate | None = Field(
        default=None, description="Deployment metadata updates (service-layer schema, no ID fields)."
    )
    flow_version_ids: FlowVersionsPatch | None = Field(
        default=None,
        description="Flow version attach/detach operations.",
    )
    config: DeploymentConfigBindingUpdate | None = Field(default=None, description="Deployment configuration update.")

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> DeploymentUpdateRequest:
        if self.spec is None and self.flow_version_ids is None and self.config is None:
            msg = "At least one of 'spec', 'flow_version_ids', or 'config' must be provided."
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Execution sub-resource schemas
# ---------------------------------------------------------------------------


class ExecutionCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider_id: UUID = Field(description="Langflow DB provider account id.")
    deployment_id: UUID = Field(description="Langflow DB deployment id.")
    provider_input: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned execution input payload.",
    )


class _ExecutionResponseBase(BaseModel):
    """Shared fields for execution responses."""

    execution_id: str  # provider-owned opaque identifier
    deployment_id: UUID  # Langflow DB
    provider_result: dict[str, Any] | None = None  # provider-owned passthrough


class ExecutionCreateResponse(_ExecutionResponseBase):
    """Response returned when an execution is created.

    Intentionally distinct from ``ExecutionStatusResponse`` even though both
    currently share the same shape, mirroring the service-layer separation.
    """


class ExecutionStatusResponse(_ExecutionResponseBase):
    """Response returned when querying an execution status.

    Intentionally distinct from ``ExecutionCreateResponse`` even though both
    currently share the same shape, mirroring the service-layer separation.
    """
