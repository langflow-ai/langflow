from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

DeploymentType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
] # deployment adapters can have varying deployment types.


class ArtifactType(str, Enum):
    """Artifact type."""
    FLOW = "flow"
    DOCUMENT = "document"
# The artifacts to deploy belong to Langflow


class SnapshotFormat(str, Enum):
    REFERENCE_ID = "reference_id"
    RAW_PAYLOAD = "raw_payload"
# requests to the deployment service
# can be either a reference snapshot by
# id or provide a raw payload


class BaseFlowArtifact(BaseModel):
    """Model representing a payload for a flow."""
    model_config = ConfigDict(extra="allow") # e.g., viewport - good for viewing the flow in the UI

    id: UUID = Field(description="Unique identifier for the flow")
    data: dict = Field(description="The data of the flow")
    name: str = Field(description="The name of the flow")
    description: str | None = Field(None, description="The description of the flow")
    tags: list[str] | None = Field(None, description="The tags of the flow")

    # TODO: validate presence of nodes and edges in data

class BaseDocumentArtifact(BaseModel):
    """Model representing a payload for a document."""
    name: str = Field(description="The name of the document")
    description: str | None = Field(None, description="The description of the document")
    raw: bytes | str | dict = Field(description="The data of the document")

    # TODO: validate presence of raw data


ARTIFACT_MAP: dict[ArtifactType, type[BaseModel]] = {
    ArtifactType.FLOW: BaseFlowArtifact,
    ArtifactType.DOCUMENT: BaseDocumentArtifact,
}


SnapshotList = Annotated[
    list[BaseFlowArtifact] | list[BaseDocumentArtifact],
    Field(min_length=1)
]


class SnapshotReferenceItems(BaseModel):
    """Model representing a reference for a snapshot."""
    format: Literal[SnapshotFormat.REFERENCE_ID] = SnapshotFormat.REFERENCE_ID
    artifact_type: ArtifactType = Field(description="The type of the snapshot items being referenced.")
    value: list[str] = Field(min_length=1)

    @field_validator("value")
    @classmethod
    def validate_ids(cls, v: list[str]) -> list[str]:
        return _normalize_and_validate_id_list_for_duplicates(v, field_name="value")


class SnapshotItemsCreate(BaseModel):
    """Model representing a payload for a snapshot."""
    artifact_type: ArtifactType = Field(description="The type of the snapshot items being referenced.")
    value: SnapshotList

    @model_validator(mode="after")
    def validate_value_matches_artifact_type(self) -> "SnapshotItemsCreate":
        validate_value_matches_artifact_type(self.value, self.artifact_type)
        return self


class SnapshotPayloadItems(BaseModel):
    """Model representing a payload for a snapshot."""
    format: Literal[SnapshotFormat.RAW_PAYLOAD] = SnapshotFormat.RAW_PAYLOAD
    artifact_type: ArtifactType = Field(description="The type of the snapshot items being referenced.")
    value: SnapshotList

    @model_validator(mode="after")
    def validate_value_matches_artifact_type(self) -> "SnapshotPayloadItems":
        validate_value_matches_artifact_type(self.value, self.artifact_type)
        return self


def validate_value_matches_artifact_type(value: SnapshotList, artifact_type: ArtifactType) -> None:
    expected_model = ARTIFACT_MAP[artifact_type]

    for idx, item in enumerate(value):
        if not isinstance(item, expected_model):
            msg = (
                f"All items must be of type: '{expected_model.__name__}', "
                f"but value[{idx}] is of type '{type(item).__name__}'."
            )
            raise TypeError(msg)


SnapshotItems = Annotated[
    SnapshotReferenceItems | SnapshotPayloadItems,
    Field(discriminator="format"),
]


class SnapshotDeploymentBindingUpdate(BaseModel):
    """Snapshot deployment binding patch payload.

    Add or remove snapshot bindings for the deployment by reference ids.
    """
    format: Literal[SnapshotFormat.REFERENCE_ID] = SnapshotFormat.REFERENCE_ID
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


class ConfigFormat(str, Enum):
    REFERENCE_ID = "reference_id"
    RAW_PAYLOAD = "raw_payload"


EnvVarKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
EnvVarValue = str


class BaseConfigData(BaseModel):
    """Model representing a data for a config."""
    name: str = Field(description="The name of the config")
    description: str | None = Field(None, description="The description of the config")
    environment_variables: dict[EnvVarKey, EnvVarValue] | None = Field(None, description="Environment variables")
    # the provider might have additional configuration options that are not covered here
    provider_config: dict | None = Field(None, description="Provider configuration")


class ConfigResult(BaseModel):
    """Model representing a result for a config creation operation."""
    id: UUID | str = Field(description="The id of the created config")
    provider_result: dict | None = Field(
        None, description="The result of the config creation operation from the provider"
    )


class ConfigReference(BaseModel):
    format: Literal[ConfigFormat.REFERENCE_ID] = ConfigFormat.REFERENCE_ID
    value: str

    @field_validator("value")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _normalize_and_validate_id(v, field_name="value")


class ConfigPayload(BaseModel):
    format: Literal[ConfigFormat.RAW_PAYLOAD] = ConfigFormat.RAW_PAYLOAD
    value: BaseConfigData


ConfigItem = Annotated[
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
        if isinstance(v, str):
            return _normalize_and_validate_id(v, field_name="id")
        return v


class ConfigDeploymentBindingUpdate(BaseModel):
    """Config deployment binding patch payload."""
    format: Literal[ConfigFormat.REFERENCE_ID] = ConfigFormat.REFERENCE_ID
    config_id: str |  UUID | None = Field(
        None,
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
    name: str = Field(description="The name of the deployment")
    description: str = Field(default="", description="The description of the deployment")
    type: DeploymentType = Field(description="The type of the deployment")
    provider_data: dict | None = Field(None, description="The data of the deployment from the provider")


class DeploymentResult(BaseDeploymentData):
    """Model representing a result for a deployment creation operation."""
    id: UUID | str = Field(description="The id of the created deployment")
    provider_result: dict | None = Field(
        None, description="The result of the deployment creation operation from the provider"
    )

class SnapshotResult(BaseModel):
    """Model representing a result for a snapshot creation operation."""
    ids: list[UUID | str] = Field(description="The ids of the created snapshots")
    provider_result: dict | None = Field(
        None, description="The result of the snapshot creation operation from the provider"
    )

class DeploymentCreate(BaseModel):
    """Deployment create payload."""
    data: BaseDeploymentData = Field(description="The base metadata of the deployment")
    snapshot: SnapshotItems | None = Field(None, description="The snapshots of the deployment")
    config: ConfigItem | None = Field(None, description="The config of the deployment")


class BaseDeploymentDataUpdate(BaseModel):
    """Deployment base update payload."""
    name: str | None = Field(None, description="The name of the deployment")
    description: str | None = Field(None, description="The description of the deployment")


class DeploymentUpdate(BaseModel):
    """Deployment update payload."""
    data: BaseDeploymentDataUpdate | None = Field(None, description="The metadata of the deployment")
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


def _normalize_and_validate_id_list_for_duplicates(values: list[str], *, field_name: str) -> list[str]:
    """Normalize identifier lists and reject blank entries."""
    normalized_values = []
    visited = set()
    for value in values:
        normalized = _normalize_and_validate_id(value, field_name=field_name)
        normalized_values.append(normalized)
        visited.add(normalized)
        if len(visited) < len(normalized_values):
            msg = f"'{field_name}' must not contain duplicates: {normalized}."
            raise ValueError(msg)
    return normalized_values


def get_str_id(v: str | UUID) -> str:
    return str(v) if isinstance(v, UUID) else v


def get_uuid(v: str | UUID) -> UUID:
    return UUID(v) if isinstance(v, str) else v
