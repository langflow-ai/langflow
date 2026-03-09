"""Deployment API request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    DeploymentConfig,
    DeploymentType,
)
from pydantic import AfterValidator, BaseModel, Field, SecretStr, ValidationInfo, field_validator, model_validator


def _validate_str_id_list(values: list[str], *, field_name: str) -> list[str]:
    if not values:
        msg = f"{field_name} must not be empty."
        raise ValueError(msg)
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            msg = f"{field_name} must not contain empty values."
            raise ValueError(msg)
        if value in seen:
            msg = f"{field_name} must not contain duplicate values: '{value}'."
            raise ValueError(msg)
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _normalize_str(value: str, *, field_name: str = "Field") -> str:
    normalized = value.strip()
    if not normalized:
        msg = f"'{field_name}' must not be empty or whitespace."
        raise ValueError(msg)
    return normalized


def _normalize_optional_str(value: str | None, *, field_name: str = "Field") -> str | None:
    if value is None:
        return None
    return _normalize_str(value, field_name=field_name)


def _strip_nonempty(value: str, info: ValidationInfo) -> str:
    return _normalize_str(value, field_name=info.field_name or "Field")


NonEmptyStr = Annotated[str, AfterValidator(_strip_nonempty)]


def _validate_flow_version_ids(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return _validate_str_id_list(values, field_name="flow_version_ids")


FlowVersionIdsQuery = Annotated[list[str] | None, AfterValidator(_validate_flow_version_ids)]


class DeploymentProviderAccountCreate(BaseModel):
    model_config = {"extra": "forbid"}

    provider_tenant_id: NonEmptyStr | None = Field(
        default=None,
        description="Provider-owned tenant/organization id.",
    )
    provider_key: NonEmptyStr = Field(description="Deployment provider key.")
    provider_url: NonEmptyStr = Field(description="Provider service URL.")
    api_key: SecretStr = Field(min_length=1, description="Provider credential material.")

    @field_validator("api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: str, info: ValidationInfo) -> str:
        return _normalize_str(value, field_name=info.field_name)


class DeploymentProviderAccountUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    provider_tenant_id: NonEmptyStr | None = Field(default=None)
    provider_key: NonEmptyStr | None = Field(default=None)
    provider_url: NonEmptyStr | None = Field(default=None)
    api_key: SecretStr | None = Field(default=None)

    @field_validator("api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: str | None, info: ValidationInfo) -> str | None:
        return _normalize_optional_str(value, field_name=info.field_name)

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> DeploymentProviderAccountUpdate:
        if not self.model_fields_set:
            msg = "At least one field must be provided for update."
            raise ValueError(msg)
        for field_name in ("provider_key", "provider_url", "api_key"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                msg = f"'{field_name}' cannot be set to null."
                raise ValueError(msg)
        return self


class DeploymentProviderAccountResponse(BaseModel):
    id: UUID
    provider_tenant_id: str | None = None
    provider_key: str
    provider_url: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DeploymentTypeListResponse(BaseModel):
    deployment_types: list[DeploymentType]


class _DeploymentResponseBase(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    type: DeploymentType
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict[str, Any] | None = None


class DeploymentGetResponse(_DeploymentResponseBase):
    resource_key: str
    attached_count: int = Field(default=0, ge=0)


class DeploymentListItem(_DeploymentResponseBase):
    resource_key: str
    attached_count: int = Field(default=0, ge=0)


class _PaginatedResponse(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class DeploymentListResponse(_PaginatedResponse):
    deployments: list[DeploymentListItem]
    deployment_type: DeploymentType | None = None


class DeploymentProviderAccountListResponse(_PaginatedResponse):
    providers: list[DeploymentProviderAccountResponse]


class DeploymentCreateResponse(_DeploymentResponseBase):
    pass


class DeploymentUpdateResponse(_DeploymentResponseBase):
    pass


class DeploymentStatusResponse(_DeploymentResponseBase):
    pass


class RedeployResponse(_DeploymentResponseBase):
    pass


class DeploymentDuplicateResponse(_DeploymentResponseBase):
    pass


class FlowVersionsAttach(BaseModel):
    model_config = {"extra": "forbid"}
    ids: list[str] = Field(min_length=1)

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, values: list[str]) -> list[str]:
        return _validate_str_id_list(values, field_name="ids")


class FlowVersionsPatch(BaseModel):
    model_config = {"extra": "forbid"}

    add: list[str] | None = None
    remove: list[str] | None = None

    @field_validator("add", "remove")
    @classmethod
    def validate_id_lists(cls, values: list[str] | None, info: ValidationInfo) -> list[str] | None:
        if values is None:
            return None
        return _validate_str_id_list(values, field_name=info.field_name)

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


class _StrictBaseDeploymentData(BaseDeploymentData):
    model_config = {"extra": "forbid"}


class _StrictBaseDeploymentDataUpdate(BaseDeploymentDataUpdate):
    model_config = {"extra": "forbid"}


class _StrictDeploymentConfig(DeploymentConfig):
    model_config = {"extra": "forbid"}


class DeploymentConfigCreate(BaseModel):
    model_config = {"extra": "forbid"}

    reference_id: NonEmptyStr | None = None
    raw_payload: _StrictDeploymentConfig | None = None

    @model_validator(mode="after")
    def validate_exactly_one(self) -> DeploymentConfigCreate:
        if (self.reference_id is None) == (self.raw_payload is None):
            msg = "Exactly one of 'reference_id' or 'raw_payload' must be provided."
            raise ValueError(msg)
        return self


class DeploymentConfigBindingUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    config_id: NonEmptyStr | None = None


class DeploymentCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider_id: UUID
    spec: _StrictBaseDeploymentData
    project_id: UUID | None = None
    flow_version_ids: FlowVersionsAttach | None = None
    config: DeploymentConfigCreate | None = None


class DeploymentUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    spec: _StrictBaseDeploymentDataUpdate | None = None
    flow_version_ids: FlowVersionsPatch | None = None
    config: DeploymentConfigBindingUpdate | None = None

    @model_validator(mode="after")
    def ensure_any_field_provided(self) -> DeploymentUpdateRequest:
        if not self.model_fields_set:
            msg = "At least one of 'spec', 'flow_version_ids', or 'config' must be provided."
            raise ValueError(msg)
        return self


class ExecutionCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider_id: UUID
    deployment_id: UUID
    provider_data: dict[str, Any] | None = None


class _ExecutionResponseBase(BaseModel):
    execution_id: str | None = None
    deployment_id: UUID
    provider_data: dict[str, Any] | None = None


class ExecutionCreateResponse(_ExecutionResponseBase):
    pass


class ExecutionStatusResponse(_ExecutionResponseBase):
    pass
