from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class DeploymentType(str, Enum):
    """Deployment type."""
    AGENT = "agent"
    MCP = "mcp"


class SnapshotType(str, Enum):
    """Snapshot type."""
    FLOW = "flow"


class FlowPayload(BaseModel):
    """Model representing a payload for a flow."""
    id: UUID = Field(description="Unique identifier for the flow")
    data: dict = Field(description="The data of the flow") # TODO: validate presence of nodes and edges
    name: str = Field(description="The name of the flow")
    description: str | None = Field(None, description="The description of the flow")
    tags: list[str] | None = Field(None, description="The tags of the flow")


class SnapshotReference(BaseModel):
    """Model representing a reference for a snapshot."""
    format: Literal["reference_id"]
    type: SnapshotType = Field(description="The type of the snapshot")
    value: list[str] = Field(min_length=1)

    @field_validator("value")
    @classmethod
    def validate_ids(cls, v: list[str]) -> list[str]:
        return _normalize_and_validate_id_list(v, field_name="value")


class SnapshotPayload(BaseModel):
    """Model representing a payload for a snapshot."""
    format: Literal["raw_payload"]
    type: SnapshotType = Field(description="The type of the snapshot")
    value: list[FlowPayload] = Field(min_length=1)


SnapshotDeploymentBindingCreate = Annotated[
    SnapshotReference | SnapshotPayload,
    Field(discriminator="format"),
]


class SnapshotCreate(BaseModel):
    """Snapshot create payload."""
    type: SnapshotType = Field(description="The type of the snapshot")


class SnapshotDeploymentBindingUpdate(BaseModel):
    """Snapshot deployment binding patch payload."""
    format: Literal["reference_id"] = "reference_id"
    add: list[str] | None = Field(
        None,
        description="Snapshot reference ids to attach to the deployment. Omit to leave unchanged.",
    )
    remove: list[str] | None = Field(
        None,
        description="Snapshot reference ids to detach from the deployment. Omit to leave unchanged.",
    )

    @field_validator("add", "remove")
    @classmethod
    def validate_id_lists(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return _normalize_and_validate_id_list(v, field_name="snapshot_id")

    @model_validator(mode="after")
    def validate_operations(self):
        """Ensure patch contains explicit and non-conflicting operations."""
        add_values = self.add or []
        remove_values = self.remove or []

        overlap = set(add_values).intersection(remove_values)
        if overlap:
            ids = ", ".join(sorted(overlap))
            msg = f"Snapshot ids cannot be present in both 'add' and 'remove': {ids}."
            raise ValueError(msg)

        return self


class BaseConfigData(BaseModel):
    """Model representing a data for a config."""
    name: str = Field(description="The name of the config")
    description: str | None = Field(None, description="The description of the config")
    environment_variables: dict[str, str] = Field(description="Environment variables")


class ConfigReference(BaseModel):
    format: Literal["reference_id"]
    value: str

    @field_validator("value")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _normalize_and_validate_id(v, field_name="value")


class ConfigPayload(BaseModel):
    format: Literal["raw_payload"]
    value: BaseConfigData


ConfigDeploymentBindingCreate = Annotated[
    ConfigReference | ConfigPayload,
    Field(discriminator="format"),
]


class ConfigUpdate(BaseModel):
    """Config update payload."""
    id: str | UUID = Field(description="The id of the config")
    name: str | None = Field(None, description="The name of the config")
    description: str | None = Field(None, description="The description of the config")
    environment_variables: dict[str, str] | None = Field(None, description="Environment variables")

    @field_validator("id")
    @classmethod
    def validate_config_id(cls, v: str | UUID) -> str | UUID:
        return _normalize_and_validate_id(v, field_name="id")


class ConfigDeploymentBindingUpdate(BaseModel):
    """Config deployment binding patch payload."""
    format: Literal["reference_id"] = "reference_id"
    config_id: str |  UUID | None = Field(
        None,
        min_length=1,
        description="Config reference id to bind to the deployment. Use null to unbind.",
    )

    @field_validator("config_id")
    @classmethod
    def validate_config_id(cls, v: str | UUID | None) -> str | UUID | None:
        if isinstance(v, str):
            return _normalize_and_validate_id(v, field_name="config_id")
        return v


class BaseDeploymentData(BaseModel):
    """Model representing a data for a deployment."""
    id: str | UUID | None = Field(default=None, description="The id of the deployment")
    name: str = Field(description="The name of the deployment")
    description: str = Field(default="", description="The description of the deployment")
    type: DeploymentType = Field(default=DeploymentType.AGENT, description="The type of the deployment")

    @field_validator("id")
    @classmethod
    def validate_deployment_id(cls, v: str | UUID | None) -> str | UUID | None:
        if isinstance(v, str):
            return _normalize_and_validate_id(v, field_name="id")
        return v


class DeploymentCreate(BaseModel):
    """Deployment create payload."""
    base_data: BaseDeploymentData = Field(description="The base metadata of the deployment")
    snapshot: SnapshotDeploymentBindingCreate = Field(description="The snapshot of the deployment")
    config: ConfigDeploymentBindingCreate = Field(description="The config of the deployment")


class BaseDeploymentDataUpdate(BaseModel):
    """Deployment base update payload."""
    name: str | None = Field(None, description="The name of the deployment")
    description: str | None = Field(None, description="The description of the deployment")


class DeploymentUpdate(BaseModel):
    """Deployment update payload."""
    base_data: BaseDeploymentDataUpdate | None = Field(None, description="The metadata of the deployment")
    snapshot: SnapshotDeploymentBindingUpdate | None = Field(None, description="The snapshot of the deployment")
    config: ConfigDeploymentBindingUpdate | None = Field(None, description="The config of the deployment")


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
