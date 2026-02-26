import datetime
import json
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

DeploymentProviderName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]  # the name of the deployment provider.

DeploymentProviderId = UUID  # primary key of a deployment provider account registration.

AccountId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]  # the provider account / tenant id.


class DeploymentType(str, Enum):
    """Deployment types supported by Langflow."""

    AGENT = "agent"
    MCP = "mcp"


class ArtifactType(str, Enum):
    """Artifact types supported by Langflow."""

    FLOW = "flow"
    DOCUMENT = "document"


class BaseFlowArtifact(BaseModel):
    """Model representing a payload for a flow."""

    model_config = ConfigDict(extra="allow")  # e.g., viewport - good for viewing the flow in the UI

    id: UUID = Field(description="Unique identifier for the flow")
    name: str = Field(description="The name of the flow")
    description: str | None = Field(None, description="The description of the flow")
    data: dict = Field(description="The data of the flow")
    tags: list[str] | None = Field(None, description="The tags of the flow")
    provider_data: dict | None = Field(
        None,
        description="Provider-specific flow metadata consumed only by the active deployment adapter.",
    )

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


SnapshotList = Annotated[list[BaseFlowArtifact] | list[BaseDocumentArtifact], Field(min_length=1)]


class SnapshotItem(BaseModel):
    """Model representing a result for a snapshot item."""

    id: UUID | str = Field(description="The id of the snapshot item")
    name: str = Field(description="The name of the snapshot item")
    description: str | None = Field(None, description="The description of the snapshot item")
    provider_data: dict | None = Field(None, description="The data of the snapshot item from the provider")


class SnapshotGetResult(SnapshotItem):
    """Model representing a result for retrieving a single snapshot payload."""

    artifact_type: ArtifactType = Field(description="The type of artifact stored in the snapshot.")
    value: BaseFlowArtifact | BaseDocumentArtifact = Field(description="The artifact payload stored in the snapshot.")


class SnapshotListResult(BaseModel):
    """Model representing a result for a snapshot list operation."""

    snapshots: list[SnapshotItem] = Field(description="The list of snapshots")
    provider_result: dict | None = Field(
        None, description="The result of the snapshot list operation from the provider"
    )
    artifact_type: ArtifactType | Literal["_ALL"] = Field(
        default="_ALL",
        description="The type of the snapshot items being referenced.",
    )


class SnapshotItemsCreate(BaseModel):
    """Model representing a payload for a snapshot."""

    artifact_type: ArtifactType = Field(description="The type of the snapshot items being referenced.")
    raw_payloads: SnapshotList

    @model_validator(mode="after")
    def validate_value_matches_artifact_type(self) -> "SnapshotItemsCreate":
        validate_value_matches_artifact_type(self.raw_payloads, self.artifact_type)
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


class SnapshotItems(BaseModel):
    """Snapshot input for deployment create.

    Accept either snapshot reference IDs or raw artifact payloads.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_type: ArtifactType = Field(description="The type of the snapshot items being referenced.")
    reference_ids: list[str] | None = Field(
        None,
        description="Snapshot reference ids to use for this deployment.",
    )
    raw_payloads: SnapshotList | None = Field(
        None,
        description="Raw snapshot payloads to create and bind for this deployment.",
    )

    @field_validator("reference_ids")
    @classmethod
    def validate_reference_ids(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return _normalize_and_validate_id_list_for_duplicates(v, field_name="reference_ids")

    @model_validator(mode="after")
    def validate_snapshot_source(self) -> "SnapshotItems":
        has_reference_ids = self.reference_ids is not None
        has_raw_payloads = self.raw_payloads is not None

        if has_reference_ids == has_raw_payloads:
            msg = "Exactly one of 'reference_ids' or 'raw_payloads' must be provided."
            raise ValueError(msg)

        if self.raw_payloads is not None:
            validate_value_matches_artifact_type(self.raw_payloads, self.artifact_type)

        return self


class SnapshotDeploymentBindingUpdate(BaseModel):
    """Snapshot deployment binding patch payload.

    Add or remove snapshot bindings for the deployment by reference ids.
    """

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
        return _normalize_and_validate_id_list_for_duplicates(v, field_name="snapshot_id")

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


EnvVarKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EnvVarSource(str, Enum):
    RAW = "raw"
    VARIABLE = "variable"


class EnvVarValueSpec(BaseModel):
    """Environment variable resolution spec."""

    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Raw value or variable name, depending on the selected source."
    )
    source: EnvVarSource = Field(
        default=EnvVarSource.VARIABLE,
        description="How to interpret `value`: resolve from variable service or use raw value as-is.",
    )


EnvVarValue = EnvVarValueSpec


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


class ConfigItemResult(BaseModel):
    """Model representing a result for a config item."""

    id: UUID | str = Field(description="The id of the config")
    name: str | None = Field(None, description="The name of the config")
    description: str | None = Field(None, description="The description of the config")
    provider_data: dict | None = Field(None, description="The config data from the provider")


class ConfigListResult(BaseModel):
    """Model representing a result for a config list operation."""

    configs: list[ConfigItemResult] = Field(description="The list of configs")
    provider_result: dict | None = Field(None, description="The result of the config list operation from the provider")


class ConfigItem(BaseModel):
    """Config input for deployment create.

    Exactly one of `reference_id` or `raw_payload` must be provided.
    """

    reference_id: str | None = Field(
        None,
        description="Existing config reference id to bind to the deployment.",
    )
    raw_payload: BaseConfigData | None = Field(
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


class ConfigUpdate(BaseModel):
    """Config update payload."""

    name: str | None = Field(None, description="The name of the config")
    description: str | None = Field(None, description="The description of the config")
    environment_variables: dict[EnvVarKey, EnvVarValue] | None = Field(None, description="Environment variables")


class ConfigDeploymentBindingUpdate(BaseModel):
    """Config deployment binding patch payload."""

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


class BaseDeploymentData(BaseModel):
    """Model representing a data for a deployment."""

    name: str = Field(description="The name of the deployment")
    description: str = Field(default="", description="The description of the deployment")
    type: DeploymentType = Field(description="The type of the deployment")
    provider_spec: dict | None = Field(None, description="The data of the deployment from the provider")


class DeploymentCreateResult(BaseDeploymentData):
    """Model representing a result for a deployment creation operation."""

    id: UUID | str = Field(description="The id of the created deployment")
    provider_result: dict | None = Field(
        None, description="The result of the deployment creation operation from the provider"
    )


class DeploymentDeleteResult(BaseModel):
    """Model representing a result for a deployment deletion operation."""

    id: UUID | str = Field(description="The id of the deleted deployment")
    provider_result: dict | None = Field(
        None, description="The result of the deployment deletion operation from the provider"
    )


class DeploymentItem(BaseModel):
    """Model representing a result for a deployment list item."""

    id: UUID | str = Field(description="The id of the deployment")
    name: str = Field(description="The name of the deployment")
    type: DeploymentType = Field(description="The type of the deployment")
    created_at: datetime.datetime | None = Field(None, description="The created timestamp of the deployment")
    updated_at: datetime.datetime | None = Field(None, description="The last updated timestamp of the deployment")
    provider_data: dict | None = Field(None, description="The data of the deployment from the provider")


class DeploymentDetailItem(DeploymentItem):
    """Model representing a detailed deployment payload."""

    description: str | None = Field(None, description="The description of the deployment")


class DeploymentListPaginationOptions(BaseModel):
    """Provider-agnostic pagination request options for deployment lists."""

    page_number: int = Field(default=1, ge=1, description="1-based page number to request.")
    page_size: int = Field(default=20, ge=1, description="Maximum number of items to request per page.")


class DeploymentList(BaseModel):
    """Model representing a result for a deployment list operation."""

    deployments: list[DeploymentItem] = Field(description="The list of deployments")
    deployment_type: DeploymentType | None = Field(None, description="The type of the deployment")
    page: int = Field(default=1, ge=1, description="Current page number (1-based).")
    page_size: int = Field(default=20, ge=1, description="Requested page size.")
    total: int | None = Field(default=None, ge=0, description="Total known rows for the query.")
    provider_result: dict | None = Field(
        None, description="The result of the deployment list operation from the provider"
    )


class DeploymentListFilterOptions(BaseModel):
    """Filter options for deployment list operations."""

    provider_filter: dict[str, Any] | None = Field(
        None,
        description="Provider-specific list filter payload.",
    )
    deployment_type: DeploymentType | None = Field(None, description="The type of the deployment")
    snapshot_id: UUID | str | None = Field(None, description="The id of the snapshot being used by the deployment")
    config_id: UUID | str | None = Field(None, description="The id of the config being used by the deployment")
    flow_id: UUID | str | None = Field(None, description="The id of the flow being used by the deployment")
    project_id: UUID | str | None = Field(None, description="The id of the project associated with the deployment")

    @field_validator("snapshot_id", "config_id", "flow_id", "project_id")
    @classmethod
    def validate_filter_ids(cls, value: UUID | str | None, info) -> str | None:
        if value is None:
            return None
        return _normalize_and_validate_id(str(value), field_name=info.field_name)


class SnapshotResult(BaseModel):
    """Model representing a result for a snapshot creation operation."""

    ids: list[UUID | str] = Field(description="The ids of the created snapshots")
    provider_result: dict | None = Field(
        None, description="The result of the snapshot creation operation from the provider"
    )


class DeploymentCreate(BaseModel):
    """Deployment create payload."""

    # provider: DeploymentProviderName = Field(description="The name of the deployment provider.")
    # account_id: str = Field(
    #     description="The id of the account / tenant/ organization registered with the deployment provider."
    # )
    spec: BaseDeploymentData = Field(description="The base metadata of the deployment")
    snapshot: SnapshotItems | None = Field(None, description="The snapshots of the deployment")
    config: ConfigItem | None = Field(None, description="The config of the deployment")


DEPLOYMENT_CREATE_SCHEMA = json.dumps(DeploymentCreate.model_json_schema(), indent=2)


class BaseDeploymentDataUpdate(BaseModel):
    """Deployment base update payload."""

    name: str | None = Field(None, description="The name of the deployment")
    description: str | None = Field(None, description="The description of the deployment")


class DeploymentUpdate(BaseModel):
    """Deployment update payload."""

    spec: BaseDeploymentDataUpdate | None = Field(None, description="The metadata of the deployment")
    snapshot: SnapshotDeploymentBindingUpdate | None = Field(None, description="The snapshot of the deployment")
    config: ConfigDeploymentBindingUpdate | None = Field(None, description="The config of the deployment")


class DeploymentUpdateResult(BaseModel):
    """Model representing a result for a deployment update operation."""

    id: UUID | str = Field(description="The id of the updated deployment")
    provider_result: dict | None = Field(
        None, description="The result of the deployment update operation from the provider"
    )


class DeploymentRedeploymentResult(BaseModel):
    """Model representing a deployment redeployment operation result."""

    id: UUID | str = Field(description="The id of the redeployed deployment")
    status: str = Field(description="The deployment status reported by the provider")
    provider_result: dict | None = Field(
        None, description="The result of the deployment redeployment operation from the provider"
    )


class DeploymentStatusResult(BaseModel):
    """Model representing a deployment status response."""

    id: UUID | str = Field(description="The id of the deployment")
    status: str | None = Field(None, description="The normalized deployment health status")
    provider_data: dict | None = Field(None, description="The provider health payload")


class DeploymentExecution(BaseModel):
    """Provider-agnostic deployment execution payload."""

    deployment_id: UUID | str = Field(description="The id of the deployment to execute.")
    deployment_type: DeploymentType = Field(description="The deployment type to execute.")
    input: str | dict[str, Any] | None = Field(
        None,
        description="Provider-agnostic execution input payload.",
    )
    provider_input: dict[str, Any] | None = Field(
        None,
        description="Provider-specific execution options and overrides.",
    )

    @field_validator("deployment_id")
    @classmethod
    def validate_deployment_id(cls, value: UUID | str) -> UUID | str:
        if isinstance(value, str):
            return _normalize_and_validate_id(value, field_name="deployment_id")
        return value


class DeploymentExecutionResult(BaseModel):
    """Model representing a deployment execution response."""

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
    provider_result: dict | None = Field(
        default=None,
        description="Provider-specific execution metadata and identifiers.",
    )


class DeploymentExecutionStatus(BaseModel):
    """Provider-agnostic execution status lookup payload."""

    deployment_id: UUID | str = Field(description="The id of the deployment execution owner.")
    deployment_type: DeploymentType = Field(description="The deployment type that is being executed.")
    provider_input: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific identifiers for status retrieval (e.g., task_id/run_id/thread_id).",
    )

    @field_validator("deployment_id")
    @classmethod
    def validate_deployment_id(cls, value: UUID | str) -> UUID | str:
        if isinstance(value, str):
            return _normalize_and_validate_id(value, field_name="deployment_id")
        return value


class ConfigListFilterOptions(BaseModel):
    """Filter options for deployment config list operations."""

    provider_filter: dict[str, Any] | None = Field(
        None,
        description="Provider-specific list filter payload.",
    )


class SnapshotListFilterOptions(BaseModel):
    """Filter options for snapshot list operations."""

    provider_filter: dict[str, Any] | None = Field(
        None,
        description="Provider-specific list filter payload.",
    )


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
