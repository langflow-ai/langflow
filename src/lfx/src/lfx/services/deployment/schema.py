import datetime
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator


class DeploymentType(str, Enum):
    """Deployment types supported by Langflow."""

    AGENT = "agent"
    MCP = "mcp"


EnvVarKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EnvVarSource(str, Enum):
    RAW = "raw"
    VARIABLE = "variable"


class EnvVarValue(BaseModel):
    """Environment variable resolution spec."""

    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Raw value or variable name, depending on the selected source."
    )
    source: EnvVarSource = Field(
        default=EnvVarSource.VARIABLE,
        description="How to interpret `value`: resolve from variable service or use raw value as-is.",
    )


# -- Configs --


class ConfigCreateRequest(BaseModel):
    """Config create request."""

    name: str = Field(description="The name of the config")
    description: str | None = Field(None, description="The description of the config")
    environment_variables: dict[EnvVarKey, EnvVarValue] | None = Field(None, description="Environment variables")
    provider_config: dict | None = Field(None, description="Provider configuration")


class ConfigResponse(BaseModel):
    """Response from a config create/update operation."""

    id: UUID | str = Field(description="The id of the config")
    provider_response: dict | None = Field(None, description="Provider-specific response data")


class ConfigDetail(BaseModel):
    """Single config detail."""

    id: UUID | str = Field(description="The id of the config")
    name: str | None = Field(None, description="The name of the config")
    description: str | None = Field(None, description="The description of the config")
    provider_data: dict | None = Field(None, description="The config data from the provider")


class ConfigList(BaseModel):
    """Config list."""

    configs: list[ConfigDetail] = Field(description="The list of configs")
    provider_data: dict | None = Field(None, description="Provider-specific data")


class ConfigItem(BaseModel):
    """Config input for deployment create.

    Exactly one of `reference_id` or `raw_payload` must be provided.
    """

    reference_id: str | None = Field(
        None,
        description="Existing config reference id to bind to the deployment.",
    )
    raw_payload: ConfigCreateRequest | None = Field(
        None,
        description="Config payload to create and bind to the deployment.",
    )

    @field_validator("reference_id")
    @classmethod
    def validate_reference_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _normalize_and_validate_id(v, field_name="reference_id")

    @model_validator(mode="after")
    def validate_config_source(self) -> "ConfigItem":
        has_reference_id = self.reference_id is not None
        has_raw_payload = self.raw_payload is not None

        if has_reference_id == has_raw_payload:
            msg = "Exactly one of 'reference_id' or 'raw_payload' must be provided."
            raise ValueError(msg)

        return self


class ConfigUpdateRequest(BaseModel):
    """Config update request."""

    config_id: str = Field(description="The id of the config to update")
    name: str | None = Field(None, description="The name of the config")
    description: str | None = Field(None, description="The description of the config")
    environment_variables: dict[EnvVarKey, EnvVarValue] | None = Field(None, description="Environment variables")

    @field_validator("config_id")
    @classmethod
    def validate_config_id(cls, value: str) -> str:
        return _normalize_and_validate_id(value, field_name="config_id")


class ConfigBindingUpdate(BaseModel):
    """Patch payload for binding/unbinding a config on a deployment."""

    config_id: str | UUID | None = Field(
        None,
        description="Config reference id to bind to the deployment. Use null to unbind.",
    )

    @field_validator("config_id")
    @classmethod
    def validate_config_id(cls, v: str | UUID | None) -> str | UUID | None:
        if isinstance(v, str):
            return _normalize_and_validate_id(v, field_name="config_id")
        return v


class ConfigDeleteRequest(BaseModel):
    """Config delete request."""

    config_id: str = Field(description="The id of the config to delete")

    @field_validator("config_id")
    @classmethod
    def validate_config_id(cls, value: str) -> str:
        return _normalize_and_validate_id(value, field_name="config_id")


class ConfigListParams(BaseModel):
    """Query params for config list operations."""

    provider_params: dict[str, Any] | None = Field(
        None,
        description="Provider-specific list filter payload.",
    )


# -- Deployments --


class DeploymentSpec(BaseModel):
    """Core deployment metadata (used for create)."""

    name: str = Field(description="The name of the deployment")
    description: str = Field(default="", description="The description of the deployment")
    type: DeploymentType = Field(description="The type of the deployment")
    provider_spec: dict | None = Field(None, description="Provider-specific input data")


class DeploymentSpecUpdate(BaseModel):
    """Deployment metadata update payload."""

    name: str | None = Field(None, description="The name of the deployment")
    description: str | None = Field(None, description="The description of the deployment")


class DeploymentCreateRequest(BaseModel):
    """Deployment create payload."""

    spec: DeploymentSpec = Field(description="The base metadata of the deployment")
    project_id: UUID | None = Field(
        None,
        description="The project id associated with the deployment.",
    )
    config: ConfigItem | None = Field(None, description="The config of the deployment")


class DeploymentUpdateRequest(BaseModel):
    """Deployment update payload."""

    spec: DeploymentSpecUpdate | None = Field(None, description="The metadata of the deployment")
    config: ConfigBindingUpdate | None = Field(None, description="The config binding update")


class DeploymentItem(BaseModel):
    """Deployment summary/detail model."""

    id: UUID | str = Field(description="The id of the deployment")
    name: str = Field(description="The name of the deployment")
    description: str | None = Field(None, description="The description of the deployment")
    type: DeploymentType = Field(description="The type of the deployment")
    created_at: datetime.datetime | None = Field(None, description="The created timestamp of the deployment")
    updated_at: datetime.datetime | None = Field(None, description="The last updated timestamp of the deployment")
    provider_data: dict | None = Field(None, description="Provider-specific data")


class DeploymentList(BaseModel):
    """Response from a deployment list operation."""

    deployments: list[DeploymentItem] = Field(description="The list of deployments")
    provider_response: dict | None = Field(None, description="Provider-specific response data")


class DeploymentListParams(BaseModel):
    """Query params for deployment list operations."""

    provider_params: dict[str, Any] | None = Field(
        None,
        description="Provider-specific query params payload.",
    )
    deployment_types: list[DeploymentType] | None = Field(
        None,
        description="Deployment types to include in the result set.",
    )
    deployment_ids: list[UUID | str] | None = Field(
        None,
        description="Deployment ids to include in the result set.",
    )
    config_ids: list[UUID | str] | None = Field(
        None,
        description="Config ids to include in the result set.",
    )

    @field_validator("deployment_types")
    @classmethod
    def validate_deployment_types(cls, value: list[DeploymentType] | None) -> list[DeploymentType] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))

    @field_validator("deployment_ids", "config_ids")
    @classmethod
    def validate_filter_ids(cls, value: list[UUID | str] | None, info) -> list[str] | None:
        if value is None:
            return None
        normalized_ids = _normalize_and_validate_id_list(
            [str(item) for item in value],
            field_name=info.field_name,
        )
        return list(dict.fromkeys(normalized_ids))


# -- Deployment requests --


class DeploymentDeleteRequest(BaseModel):
    """Deployment delete request payload."""

    deployment_id: UUID | str = Field(description="The id of the deployment to delete.")

    @field_validator("deployment_id")
    @classmethod
    def validate_deployment_id(cls, value: UUID | str) -> UUID | str:
        if isinstance(value, str):
            return _normalize_and_validate_id(value, field_name="deployment_id")
        return value


# -- Deployment responses --


class DeploymentCreateResponse(DeploymentSpec):
    """Response from a deployment create operation."""

    id: UUID | str = Field(description="The id of the created deployment")
    config_id: UUID | str | None = Field(
        default=None,
        description="Config id produced or bound during deployment creation.",
    )
    provider_response: dict | None = Field(None, description="Provider-specific response data")


class DeploymentUpdateResponse(BaseModel):
    """Response from a deployment update operation."""

    id: UUID | str = Field(description="The id of the updated deployment")
    provider_response: dict | None = Field(None, description="Provider-specific response data")


class DeploymentDeleteResponse(BaseModel):
    """Response from a deployment delete operation."""

    id: UUID | str = Field(description="The id of the deleted deployment")
    provider_response: dict | None = Field(None, description="Provider-specific response data")


class DeploymentRedeployResponse(BaseModel):
    """Response from a redeploy operation."""

    id: UUID | str = Field(description="The id of the redeployed deployment")
    status: str = Field(description="The deployment status reported by the provider")
    provider_response: dict | None = Field(None, description="Provider-specific response data")


class DeploymentStatus(BaseModel):
    """Deployment status."""

    id: UUID | str = Field(description="The id of the deployment")
    status: str | None = Field(None, description="The normalized deployment health status")
    provider_data: dict | None = Field(None, description="The provider health payload")


# -- Executions --


class DeploymentExecutionRequest(BaseModel):
    """Request payload for executing a deployment."""

    deployment_id: UUID | str = Field(description="The id of the deployment to execute.")
    deployment_type: DeploymentType = Field(description="The deployment type to execute.")
    payload: str | dict[str, Any] | None = Field(
        None,
        description="Provider-agnostic execution payload.",
    )
    provider_params: dict[str, Any] | None = Field(
        None,
        description="Provider-specific execution options and overrides.",
    )

    @field_validator("deployment_id")
    @classmethod
    def validate_deployment_id(cls, value: UUID | str) -> UUID | str:
        if isinstance(value, str):
            return _normalize_and_validate_id(value, field_name="deployment_id")
        return value


class DeploymentExecutionResponse(BaseModel):
    """Response from a deployment execution."""

    execution_id: str | None = Field(
        default=None,
        description="Opaque execution identifier for status polling.",
    )
    deployment_id: UUID | str = Field(description="The id of the deployment that was executed.")
    deployment_type: DeploymentType = Field(description="The deployment type that was executed.")
    status: str | None = Field(default=None, description="Normalized execution status.")
    output: str | dict[str, Any] | None = Field(
        default=None,
        description="Provider-agnostic output payload, when available.",
    )
    provider_response: dict | None = Field(
        default=None,
        description="Provider-specific execution metadata and identifiers.",
    )


class DeploymentExecutionStatusRequest(BaseModel):
    """Request payload for checking execution status."""

    deployment_id: UUID | str = Field(description="The id of the deployment execution owner.")
    deployment_type: DeploymentType = Field(description="The deployment type that is being executed.")
    provider_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific identifiers for status retrieval (e.g., task_id/run_id/thread_id).",
    )

    @field_validator("deployment_id")
    @classmethod
    def validate_deployment_id(cls, value: UUID | str) -> UUID | str:
        if isinstance(value, str):
            return _normalize_and_validate_id(value, field_name="deployment_id")
        return value


# -- Helpers --


def _normalize_and_validate_id(value: str, *, field_name: str) -> str:
    """Normalize identifier values and reject blank strings."""
    normalized = value.strip()
    if not normalized:
        msg = f"'{field_name}' must not be empty or whitespace."
        raise ValueError(msg)
    return normalized


def _normalize_and_validate_id_list(values: list[str], *, field_name: str) -> list[str]:
    """Normalize identifier lists and reject blank entries."""
    return [_normalize_and_validate_id(value, field_name=field_name) for value in values]
