from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from lfx.services.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    ConfigDeploymentBindingUpdate,
    ConfigItem,
    DeploymentOperationResult,
    DeploymentType,
    IdLike,
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


# ---------------------------------------------------------------------------
# Provider sub-resource schemas
# ---------------------------------------------------------------------------


class ProviderAccountCreate(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, description="Provider tenant/organization identifier.")
    provider_key: str = Field(min_length=1, description="Deployment adapter routing key.")
    backend_url: str = Field(min_length=1, description="Deployment provider backend URL.")
    api_key: str = Field(min_length=1, description="Deployment provider API key.")

    @field_validator("provider_key", "backend_url", "api_key")
    @classmethod
    def normalize_required_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "Field must not be empty or whitespace."
            raise ValueError(msg)
        return normalized

    @field_validator("account_id")
    @classmethod
    def normalize_account_id(cls, value: str | None) -> str | None:
        return _normalize_optional_str(value)


class ProviderAccountUpdate(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, description="Provider tenant/organization identifier.")
    provider_key: str | None = Field(default=None, min_length=1, description="Deployment adapter routing key.")
    backend_url: str | None = Field(default=None, min_length=1, description="Deployment provider backend URL.")
    api_key: str | None = Field(default=None, min_length=1, description="Deployment provider API key.")

    @field_validator("account_id", "provider_key", "backend_url", "api_key")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> ProviderAccountUpdate:
        if all(value is None for value in (self.account_id, self.provider_key, self.backend_url, self.api_key)):
            msg = "At least one field must be provided for update."
            raise ValueError(msg)
        return self


class ProviderAccountResponse(BaseModel):
    id: UUID
    account_id: str | None
    provider_key: str
    backend_url: str
    registered_at: datetime | None


# ---------------------------------------------------------------------------
# Deployment resource schemas
# ---------------------------------------------------------------------------


class DeploymentTypeListResponse(BaseModel):
    """Supported deployment types for a provider account."""

    deployment_types: list[DeploymentType]


class DeploymentSummary(BaseModel):
    """Compact deployment representation used for list items and duplicate results."""

    id: IdLike
    name: str
    type: DeploymentType
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict[str, Any] | None = None


class DeploymentGetResponse(DeploymentSummary):
    """Full deployment detail."""

    description: str | None = None


class DeploymentListItem(BaseModel):
    id: str
    resource_key: str
    type: DeploymentType
    name: str
    attached_count: int = Field(default=0, ge=0)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict | None = None


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


class RedeployResponse(DeploymentOperationResult):
    pass


class DeploymentDuplicateResponse(DeploymentSummary):
    pass


class DeploymentDuplicateParams(BaseModel):
    """Parameters for duplicating a deployment."""

    deployment_type: DeploymentType


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
        overlap = set(add_values).intersection(remove_values)
        if overlap:
            ids = ", ".join(sorted(overlap))
            msg = f"Flow version ids cannot be present in both 'add' and 'remove': {ids}."
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Deployment create / update request schemas
# ---------------------------------------------------------------------------


class DeploymentCreateRequest(BaseModel):
    provider_id: UUID = Field(description="Deployment provider account id for adapter routing.")
    spec: BaseDeploymentData = Field(description="The base metadata of the deployment.")
    project_id: UUID | None = Field(
        default=None,
        description="Langflow Project id to persist the deployment under. Defaults to user's Starter Project.",
    )
    flow_versions: FlowVersionsAttach | None = Field(
        default=None,
        description="Flow version ids used to build provider snapshots during deployment creation.",
    )
    config: ConfigItem | None = Field(default=None, description="Deployment config binding/create payload.")


class DeploymentUpdateRequest(BaseModel):
    spec: BaseDeploymentDataUpdate | None = Field(default=None, description="Deployment metadata updates.")
    flow_versions: FlowVersionsPatch | None = Field(
        default=None,
        description="Flow version attach/detach patch payload.",
    )
    config: ConfigDeploymentBindingUpdate | None = Field(default=None, description="Deployment config binding patch.")


# ---------------------------------------------------------------------------
# Execution sub-resource schemas
# ---------------------------------------------------------------------------


class ExecutionCreateRequest(BaseModel):
    provider_id: UUID = Field(description="Deployment provider account id for adapter routing.")
    deployment_id: IdLike
    deployment_type: DeploymentType
    input: str | dict[str, Any] | None = None
    provider_input: dict[str, Any] | None = None


class _ExecutionResponseBase(BaseModel):
    """Shared fields for execution responses."""

    execution_id: str | None = None
    deployment_id: IdLike
    deployment_type: DeploymentType | None = None
    status: str | None = None
    output: str | dict[str, Any] | None = None
    provider_result: dict[str, Any] | None = None


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
