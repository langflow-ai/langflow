import datetime
import json
from enum import Enum
from functools import lru_cache
from typing import Annotated, Generic
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from lfx.services.adapters.deployment.payloads import (
    T_ConfigListParams,
    T_ConfigListResult,
    T_DeploymentConfig,
    T_DeploymentCreateResult,
    T_DeploymentItemData,
    T_DeploymentListParams,
    T_DeploymentListResult,
    T_DeploymentOperationResult,
    T_DeploymentSpec,
    T_DeploymentStatusData,
    T_DeploymentUpdate,
    T_ExecutionInput,
    T_ExecutionResult,
    T_ListParamsPayload,
    T_ProviderData,
    T_ProviderResult,
    T_SnapshotListParams,
    T_SnapshotListResult,
)
from lfx.services.adapters.payload import AdapterPayload

DeploymentProviderName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]  # the name of the deployment provider.

NormalizedId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
IdLike = UUID | NormalizedId


class DeploymentType(str, Enum):
    """Core deployment types recognized by LFX contracts."""

    # First-class deployment types recognized by the core schema.
    # Adapters may carry additional provider-specific classification in `provider_data`.
    AGENT = "agent"


class BaseFlowArtifact(BaseModel):
    """Model representing a payload for a flow."""

    model_config = ConfigDict(extra="allow")  # e.g., viewport - good for viewing the flow in the UI

    id: UUID = Field(description="Unique identifier for the flow")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="The name of the flow"
    )
    description: str | None = Field(None, description="The description of the flow")
    data: dict = Field(description="The data of the flow")
    tags: list[str] | None = Field(None, description="The tags of the flow")
    provider_data: dict | None = Field(
        None,
        description="Provider-specific flow metadata consumed only by the active deployment adapter.",
    )

    @field_validator("data")
    @classmethod
    def validate_data(cls, value: dict) -> dict:
        """Validate flow payload shape.

        Keep validation aligned with backend flow model expectations.
        """
        if "nodes" not in value:
            msg = "Flow must have nodes"
            raise ValueError(msg)
        if "edges" not in value:
            msg = "Flow must have edges"
            raise ValueError(msg)
        if not isinstance(value["nodes"], list):
            msg = "Flow 'nodes' must be a list"
            raise ValueError(msg)  # noqa: TRY004 - Pydantic validators must raise ValueError
        if not isinstance(value["edges"], list):
            msg = "Flow 'edges' must be a list"
            raise ValueError(msg)  # noqa: TRY004 - Pydantic validators must raise ValueError
        return value


SnapshotList = Annotated[list[BaseFlowArtifact], Field(min_length=1)]


class SnapshotItem(BaseModel):
    """Model representing a result for a snapshot item."""

    id: IdLike = Field(description="The id of the snapshot item")
    name: str = Field(description="The name of the snapshot item")
    provider_data: dict | None = Field(None, description="The data of the snapshot item from the provider")


class SnapshotItems(BaseModel):
    """Snapshot input for deployment create.

    Accept raw snapshot artifact payloads for deployment create.
    """

    model_config = ConfigDict(extra="forbid")

    raw_payloads: SnapshotList | None = Field(
        None,
        description="List of raw snapshot payloads to create and bind for this deployment. Omit to leave unchanged.",
    )
    ids: list[IdLike] | None = Field(
        None,
        description="List of existing snapshot ids to bind to the deployment. Omit to leave unchanged.",
    )

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, value: list[IdLike] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_and_dedupe_id_list(value, field_name="snapshot_id")

    @model_validator(mode="after")
    def validate_snapshot_source(self) -> "SnapshotItems":
        if not self.raw_payloads and not self.ids:
            msg = "At least one of 'raw_payloads' or 'ids' must be provided and non-empty."
            raise ValueError(msg)
        return self


class SnapshotDeploymentBindingUpdate(BaseModel):
    """Snapshot deployment binding patch payload.

    Supports three operations: bind existing snapshots by ID, create new
    snapshots from raw payloads, or unbind snapshots by ID.  At least one
    of the three fields must be provided.
    """

    add_ids: list[IdLike] | None = Field(
        None,
        description="Existing snapshot ids to attach to the deployment. Omit to leave unchanged.",
    )
    add_raw_payloads: SnapshotList | None = Field(
        None,
        description="Raw snapshot payloads to create and attach to the deployment. Omit to leave unchanged.",
    )
    remove_ids: list[IdLike] | None = Field(
        None,
        description="Snapshot ids to detach from the deployment. Omit to leave unchanged.",
    )

    @field_validator("add_ids", "remove_ids")
    @classmethod
    def validate_id_lists(cls, v: list[IdLike] | None) -> list[str] | None:
        # Post-validation: values are always normalized strings (UUIDs
        # are stringified by _normalize_and_dedupe_id_list).  The field
        # annotation remains list[IdLike] so Pydantic accepts UUID input.
        if v is None:
            return None
        return _normalize_and_dedupe_id_list(v, field_name="snapshot_id")

    @model_validator(mode="after")
    def validate_operations(self):
        """Ensure patch contains explicit and non-conflicting operations."""
        add_values = self.add_ids or []
        raw_values = self.add_raw_payloads or []
        remove_values = self.remove_ids or []

        if not add_values and not raw_values and not remove_values:
            msg = "At least one of 'add_ids', 'add_raw_payloads', or 'remove_ids' must be provided."
            raise ValueError(msg)

        # Overlap check covers add_ids vs remove_ids only.
        # add_raw_payloads carry flow-artifact IDs (Langflow domain),
        # while add_ids/remove_ids carry snapshot IDs (provider domain).
        overlap = set(add_values).intersection(remove_values)
        if overlap:
            ids = ", ".join(sorted(overlap))
            msg = f"Snapshot ids cannot be present in both 'add_ids' and 'remove_ids': {ids}."
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


class DeploymentConfig(BaseModel):
    """Deployment configuration payload, including environment variables and provider-specific settings."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="The name of the config"
    )
    description: str | None = Field(None, description="The description of the config")
    environment_variables: dict[EnvVarKey, EnvVarValueSpec] | None = Field(None, description="Environment variables")
    # the provider might have additional configuration options that are not covered here
    provider_config: T_DeploymentConfig | None = Field(None, description="Provider configuration")


class ConfigItem(BaseModel):
    """Config input for deployment create.

    Exactly one of `reference_id` or `raw_payload` must be provided.
    """

    reference_id: NormalizedId | None = Field(
        None,
        description="Existing config reference id to bind to the deployment.",
    )
    raw_payload: DeploymentConfig | None = Field(
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
        _validate_exactly_one_of(
            self,
            first_field="reference_id",
            second_field="raw_payload",
        )
        return self


class ConfigDeploymentBindingUpdate(BaseModel):
    """Config deployment binding patch payload.

    Exactly one of ``config_id``, ``raw_payload``, or ``unbind`` must be
    provided:

    * ``config_id`` — bind an existing config by reference.
    * ``raw_payload`` — create a new config and bind it.
    * ``unbind = True`` — detach the current config.
    """

    config_id: IdLike | None = Field(
        None,
        description="Config reference id to bind to the deployment.",
    )
    raw_payload: DeploymentConfig | None = Field(
        None,
        description="Config payload to create and bind to the deployment.",
    )
    unbind: bool = Field(
        default=False,
        description="Set to true to detach the current config from the deployment.",
    )

    @field_validator("config_id")
    @classmethod
    def validate_config_id(cls, v: IdLike | None) -> IdLike | None:
        if isinstance(v, str):
            return _normalize_and_validate_id(v, field_name="config_id")
        return v

    @model_validator(mode="after")
    def validate_config_source(self) -> "ConfigDeploymentBindingUpdate":
        provided = sum(
            [
                self.config_id is not None,
                self.raw_payload is not None,
                self.unbind,
            ]
        )
        if provided != 1:
            msg = "Exactly one of 'config_id', 'raw_payload', or 'unbind=true' must be provided."
            raise ValueError(msg)
        return self


class ConfigListItem(BaseModel):
    """Model representing a result for a config list item."""

    id: IdLike = Field(description="The id of the config item")
    name: str = Field(description="The name of the config item")
    created_at: datetime.datetime | None = Field(None, description="The created timestamp of the config item")
    updated_at: datetime.datetime | None = Field(None, description="The last updated timestamp of the config item")
    provider_data: dict | None = Field(None, description="The data of the config item from the provider")


class ProviderDataModel(BaseModel, Generic[T_ProviderData]):
    """Base model for provider metadata payloads."""

    provider_data: T_ProviderData | None = Field(None, description="The data from the provider")


class ProviderResultModel(BaseModel, Generic[T_ProviderResult]):
    """Base model for provider operation payloads."""

    provider_result: T_ProviderResult | None = Field(None, description="The result from the provider")


class ProviderSpecModel(BaseModel, Generic[T_DeploymentSpec]):
    """Base model for provider-specific input payloads."""

    provider_spec: T_DeploymentSpec | None = Field(None, description="The data of the deployment from the provider")


class BaseDeploymentData(ProviderSpecModel[T_DeploymentSpec]):
    """Model representing a data for a deployment."""

    name: str = Field(description="The name of the deployment")
    description: str = Field(default="", description="The description of the deployment")
    type: DeploymentType = Field(description="The type of the deployment")


class DeploymentCreateResult(ProviderResultModel[T_DeploymentCreateResult]):
    """Model representing a result for a deployment creation operation."""

    id: IdLike = Field(description="The id of the created deployment")
    config_id: IdLike | None = Field(
        default=None,
        description="Config id produced or bound during deployment creation.",
    )
    snapshot_ids: list[IdLike] = Field(
        default_factory=list,
        description="Snapshot ids produced or bound during deployment creation.",
    )


class DeploymentOperationResult(ProviderResultModel[T_DeploymentOperationResult]):
    """Base model for deployment operation responses by deployment id."""

    id: IdLike = Field(description="The id of the deployment")


class DeploymentDeleteResult(DeploymentOperationResult):
    """Model representing a result for a deployment deletion operation."""


class ItemResult(ProviderDataModel[T_DeploymentItemData]):
    """Model representing a result for a deployment list item."""

    id: IdLike = Field(description="The id of the deployment")
    name: str = Field(description="The name of the deployment")
    type: DeploymentType = Field(description="The type of the deployment")
    created_at: datetime.datetime | None = Field(None, description="The created timestamp of the deployment")
    updated_at: datetime.datetime | None = Field(None, description="The last updated timestamp of the deployment")


class DeploymentGetResult(ItemResult):
    """Model representing a detailed deployment payload."""

    description: str | None = Field(None, description="The description of the deployment")


class DeploymentDuplicateResult(ItemResult):
    """Model representing the result of a deployment duplication operation."""


class DeploymentListResult(ProviderResultModel[T_DeploymentListResult]):
    """Model representing a result for a deployment list operation."""

    deployments: list[ItemResult] = Field(description="The list of deployments")


class ConfigListResult(ProviderResultModel[T_ConfigListResult]):
    """Model representing a result for a config list operation."""

    configs: list[ConfigListItem] = Field(description="The list of configs")


class SnapshotListResult(ProviderResultModel[T_SnapshotListResult]):
    """Model representing a result for a snapshot list operation."""

    snapshots: list[SnapshotItem] = Field(description="The list of snapshots")


class _BaseListParams(BaseModel, Generic[T_ListParamsPayload]):
    """Shared list-filter fields."""

    provider_params: T_ListParamsPayload | None = Field(
        None,
        description="Provider-specific query params to filter by.",
    )
    deployment_ids: list[IdLike] | None = Field(
        None,
        description="Deployment ids to filter by.",
    )

    @staticmethod
    def _normalize_filter_id_values(value: list[IdLike] | None, *, field_name: str) -> list[str] | None:
        if value is None:
            return None
        normalized_ids = _normalize_and_validate_id_list(
            [str(item) for item in value],
            field_name=field_name,
        )
        # Keep first occurrence order while removing duplicates.
        return list(dict.fromkeys(normalized_ids))

    @field_validator("deployment_ids")
    @classmethod
    def validate_filter_ids(cls, value: list[IdLike] | None, info) -> list[str] | None:
        return cls._normalize_filter_id_values(value, field_name=info.field_name)


class DeploymentListParams(_BaseListParams[T_DeploymentListParams]):
    """Query params for deployment list operations."""

    deployment_types: list[DeploymentType] | None = Field(
        None,
        description="Deployment types to filter by.",
    )
    snapshot_ids: list[IdLike] | None = Field(
        None,
        description="Snapshot ids to filter by.",
    )
    config_ids: list[IdLike] | None = Field(
        None,
        description="Config ids to filter by.",
    )

    @field_validator("deployment_types")
    @classmethod
    def validate_deployment_types(cls, value: list[DeploymentType] | None) -> list[DeploymentType] | None:
        if value is None:
            return None
        # Keep first occurrence order while removing duplicates.
        return list(dict.fromkeys(value))

    @field_validator("snapshot_ids", "config_ids")
    @classmethod
    def validate_entity_filter_ids(cls, value: list[IdLike] | None, info) -> list[str] | None:
        return cls._normalize_filter_id_values(value, field_name=info.field_name)


class ConfigListParams(_BaseListParams[T_ConfigListParams]):
    """Query params for config list operations."""

    config_ids: list[IdLike] | None = Field(
        None,
        description="Config ids to filter by.",
    )

    @field_validator("config_ids")
    @classmethod
    def validate_config_ids(cls, value: list[IdLike] | None, info) -> list[str] | None:
        return cls._normalize_filter_id_values(value, field_name=info.field_name)


class SnapshotListParams(_BaseListParams[T_SnapshotListParams]):
    """Query params for snapshot list operations."""

    snapshot_ids: list[IdLike] | None = Field(
        None,
        description="Snapshot ids to filter by.",
    )

    @field_validator("snapshot_ids")
    @classmethod
    def validate_snapshot_ids(cls, value: list[IdLike] | None, info) -> list[str] | None:
        return cls._normalize_filter_id_values(value, field_name=info.field_name)


class DeploymentCreate(BaseModel):
    """Deployment create payload."""

    spec: BaseDeploymentData = Field(description="The base metadata of the deployment")
    snapshot: SnapshotItems | None = Field(None, description="The snapshots of the deployment")
    config: ConfigItem | None = Field(None, description="The config of the deployment")


@lru_cache(maxsize=1)
def get_deployment_create_schema() -> str:
    """Return serialized JSON schema for deployment create payload."""
    return json.dumps(DeploymentCreate.model_json_schema(), indent=2)


class BaseDeploymentDataUpdate(BaseModel):
    """Deployment base update payload."""

    name: str | None = Field(None, description="The name of the deployment")
    description: str | None = Field(None, description="The description of the deployment")

    @model_validator(mode="after")
    def validate_has_changes(self) -> "BaseDeploymentDataUpdate":
        if self.name is None and self.description is None:
            msg = "At least one of 'name' or 'description' must be provided."
            raise ValueError(msg)
        return self


class DeploymentUpdate(BaseModel):
    """Deployment update payload."""

    spec: BaseDeploymentDataUpdate | None = Field(None, description="The metadata of the deployment")
    snapshot: SnapshotDeploymentBindingUpdate | None = Field(None, description="The snapshot of the deployment")
    config: ConfigDeploymentBindingUpdate | None = Field(None, description="The config of the deployment")
    provider_data: T_DeploymentUpdate | None = Field(
        None,
        description="Provider-specific opaque payload for deployment update operations.",
    )

    @model_validator(mode="after")
    def validate_has_changes(self) -> "DeploymentUpdate":
        if not self.model_fields_set:
            msg = "At least one of 'spec', 'snapshot', 'config', or 'provider_data' must be provided."
            raise ValueError(msg)
        if self.spec is None and self.snapshot is None and self.config is None and self.provider_data is None:
            msg = "At least one of 'spec', 'snapshot', 'config', or 'provider_data' must be provided."
            raise ValueError(msg)
        return self


class DeploymentUpdateResult(DeploymentOperationResult):
    """Model representing a result for a deployment update operation."""

    snapshot_ids: list[IdLike] = Field(
        default_factory=list,
        description="Snapshot ids produced or bound during the update.",
    )


class RedeployResult(DeploymentOperationResult):
    """Model representing a deployment redeployment operation result."""


class DeploymentStatusResult(ProviderDataModel[T_DeploymentStatusData]):
    """Model representing a deployment status response.

    Inherits ``provider_data`` from ``ProviderDataModel`` to carry
    provider-reported health information.
    """

    id: IdLike = Field(description="The id of the deployment")


class ExecutionCreate(BaseModel):
    """Provider-agnostic deployment execution payload."""

    deployment_id: IdLike = Field(description="The id of the deployment to create an execution for.")
    deployment_type: DeploymentType | None = Field(
        default=None,
        description="Optional deployment type routing hint for execution creation.",
    )

    provider_data: T_ExecutionInput | None = Field(
        None,
        description="Provider-specific execution data.",
    )

    @field_validator("deployment_id")
    @classmethod
    def validate_deployment_id(cls, value: IdLike) -> IdLike:
        if isinstance(value, str):
            return _normalize_and_validate_id(value, field_name="deployment_id")
        return value


class ExecutionResultBase(ProviderResultModel[T_ExecutionResult]):
    """Base model for deployment execution responses."""

    execution_id: str | None = Field(
        default=None,
        description="Opaque execution identifier for status polling.",
    )
    deployment_id: IdLike = Field(description="The id of the deployment that was executed.")


class ExecutionCreateResult(ExecutionResultBase):
    """Result returned when an execution is created.

    This model intentionally remains distinct from ``ExecutionStatusResult`` even
    though both currently share the same shape. Callers should not mix the two
    response types: create responses and status responses represent different API
    stages and may diverge as the contract evolves.
    """


class ExecutionStatusResult(ExecutionResultBase):
    """Result returned when querying an execution status.

    This model intentionally remains distinct from ``ExecutionCreateResult`` even
    though both currently share the same shape. Callers should not mix the two
    response types: create responses and status responses represent different API
    stages and may diverge as the contract evolves.
    """


class DeploymentListTypesResult(ProviderResultModel[AdapterPayload]):
    """Model representing deployment types listing response."""

    deployment_types: list[DeploymentType] = Field(description="Supported deployment types.")


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


def _normalize_and_dedupe_id_list(values: list[IdLike], *, field_name: str) -> list[str]:
    """Normalize identifier lists and remove duplicates while preserving order."""
    normalized_values = _normalize_and_validate_id_list(
        [str(value) for value in values],
        field_name=field_name,
    )
    return list(dict.fromkeys(normalized_values))


def _validate_exactly_one_of(
    model: BaseModel,
    *,
    first_field: str,
    second_field: str,
) -> None:
    """Ensure exactly one of two model fields is provided."""
    has_first = getattr(model, first_field) is not None
    has_second = getattr(model, second_field) is not None

    if has_first == has_second:
        msg = f"Exactly one of '{first_field}' or '{second_field}' must be provided."
        raise ValueError(msg)


def get_str_id(v: IdLike) -> str:
    return str(v) if isinstance(v, UUID) else v


def get_uuid(v: UUID | str) -> UUID:
    """Return a UUID from a UUID object or UUID-formatted string.

    This helper is intentionally strict: opaque deployment identifiers like
    ``dep_1`` are valid ``IdLike`` values, but are not valid UUIDs.
    Use ``get_str_id`` when callers need to preserve opaque ids.
    """
    if isinstance(v, str):
        try:
            return UUID(v)
        except ValueError as exc:
            msg = f"Cannot convert identifier '{v}' to UUID. Use get_str_id() for opaque IDs."
            raise ValueError(msg) from exc
    return v
