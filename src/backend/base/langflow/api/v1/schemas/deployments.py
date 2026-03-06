"""Deployment API schemas.

Identifier domains
------------------
This module draws a strict boundary between two identifier domains:

* **Langflow-managed (UUID)** -- database primary keys owned by the Langflow
  backend. All ``id``, ``provider_id``, ``project_id``, and ``deployment_id``
  fields on API request/response schemas are UUIDs that reference rows in the
  Langflow database. ``provider_id`` specifically maps to
  ``deployment_provider_account.id`` in persistence models.

* **Provider-owned (str)** -- opaque references assigned by the external
  deployment provider. These appear as ``reference_id``, ``config_id``,
  ``resource_key``, ``execution_id``, ``provider_tenant_id``, and inside
  ``provider_*`` payload dicts. They are typed as ``str`` because the provider
  may use any format.

The ``provider_data`` / ``provider_spec`` dicts are opaque pass-through
containers whose contents are entirely defined by the provider adapter.
Langflow forwards these payloads but does not define their schema.

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

    provider_tenant_id: str | None = Field(
        default=None,
        min_length=1,
        description="Provider-owned tenant/organization id. Langflow persists this opaque value.",
    )
    provider_key: str = Field(min_length=1, description="Deployment provider key.")
    provider_url: str = Field(
        min_length=1,
        description="Provider service URL persisted in Langflow DB for provider-account resolution.",
    )
    api_key: str = Field(
        min_length=1,
        description=(
            "Provider credential material. Stored by Langflow as secret data and never returned in read responses."
        ),
    )

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

    provider_tenant_id: str | None = Field(
        default=None,
        description="Provider-owned tenant/organization id. Omit to keep existing value, null to clear.",
    )
    provider_key: str | None = Field(default=None, description="Deployment provider key.")
    provider_url: str | None = Field(
        default=None,
        description="Provider service URL. Omit to keep existing value.",
    )
    api_key: str | None = Field(
        default=None,
        description="Provider credential material. Omit to keep existing value; provided value replaces stored secret.",
    )

    @field_validator("provider_tenant_id", "provider_key", "provider_url", "api_key")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> ProviderAccountUpdate:
        if not self.model_fields_set:
            msg = "At least one field must be provided for update."
            raise ValueError(msg)
        return self


class ProviderAccountResponse(BaseModel):
    id: UUID = Field(description="Langflow DB provider-account UUID (`deployment_provider_account.id`).")
    provider_tenant_id: str | None = Field(
        default=None,
        description="Provider-owned tenant/organization identifier persisted as opaque text.",
    )
    provider_key: str = Field(description="Provider adapter key used by Langflow.")
    provider_url: str = Field(description="Provider service URL persisted in Langflow DB.")
    created_at: datetime | None = Field(default=None, description="Langflow DB row creation timestamp.")
    updated_at: datetime | None = Field(default=None, description="Langflow DB row update timestamp.")


# ---------------------------------------------------------------------------
# Deployment resource schemas
# ---------------------------------------------------------------------------


class DeploymentTypeListResponse(BaseModel):
    """Supported deployment types for a provider account."""

    deployment_types: list[DeploymentType]


class _DeploymentResponseBase(BaseModel):
    """Shared fields for deployment response schemas."""

    id: UUID = Field(description="Langflow DB deployment UUID.")
    name: str
    type: DeploymentType
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque payload returned by the deployment provider.",
    )


class DeploymentSummary(_DeploymentResponseBase):
    """Base deployment representation used for detail and duplicate responses."""

    description: str | None = None


class DeploymentGetResponse(DeploymentSummary):
    """Full deployment detail."""


class DeploymentListItem(_DeploymentResponseBase):
    """Deployment representation used in list responses."""

    resource_key: str = Field(description="Provider-owned stable resource identifier.")
    attached_count: int = Field(default=0, ge=0, description="Number of flow versions attached to this deployment.")


class _PaginatedResponse(BaseModel):
    """Shared pagination fields for list responses."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class DeploymentListResponse(_PaginatedResponse):
    deployments: list[DeploymentListItem]
    deployment_type: DeploymentType | None = None


class ProviderAccountListResponse(_PaginatedResponse):
    providers: list[ProviderAccountResponse]


class DeploymentCreateResponse(_DeploymentResponseBase):
    """API response for deployment creation."""

    description: str | None = None


class DeploymentUpdateResponse(_DeploymentResponseBase):
    """API response for deployment update."""

    description: str | None = None


class DeploymentStatusResponse(_DeploymentResponseBase):
    """API response for deployment status/health."""


class RedeployResponse(_DeploymentResponseBase):
    """API response for redeployment."""


class DeploymentDuplicateResponse(DeploymentSummary):
    pass


# ---------------------------------------------------------------------------
# Flow versions sub-resource schemas
# ---------------------------------------------------------------------------


class FlowVersionsAttach(BaseModel):
    """Flow version ids to attach during deployment creation."""

    model_config = {"extra": "forbid"}

    # Typed as str (not UUID) because the service layer uses a flexible IdLike
    # type (UUID | NormalizedId) and the query-parameter variant must also accept
    # plain strings for ergonomic multi-value query params.
    ids: list[str] = Field(
        min_length=1,
        description="Langflow flow version ids to attach to the deployment.",
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
        description="Langflow flow version ids to attach to the deployment. Omit to leave unchanged.",
    )
    remove: list[str] | None = Field(
        None,
        description="Langflow flow version ids to detach from the deployment. Omit to leave unchanged.",
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

    provider_id: UUID = Field(description="Langflow DB provider-account UUID (`deployment_provider_account.id`).")
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

    provider_id: UUID = Field(description="Langflow DB provider-account UUID (`deployment_provider_account.id`).")
    deployment_id: UUID = Field(description="Langflow DB deployment UUID.")
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque execution input payload.",
    )


class _ExecutionResponseBase(BaseModel):
    """Shared fields for execution responses."""

    execution_id: str | None = Field(default=None, description="Provider-owned opaque execution identifier.")
    deployment_id: UUID = Field(description="Langflow DB deployment UUID.")
    provider_data: dict[str, Any] | None = Field(
        default=None,
        description="Provider-owned opaque execution result payload.",
    )


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
