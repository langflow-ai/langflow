"""Watsonx Orchestrate deployment payload contracts."""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Any, Literal

from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
from lfx.services.adapters.deployment.schema import BaseFlowArtifact, EnvVarKey, EnvVarValueSpec, NormalizedId
from lfx.services.adapters.payload import AdapterPayload, PayloadSlot
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

RawToolName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WatsonxFlowArtifactProviderData(BaseModel):
    """Provider metadata for watsonx flow artifacts."""

    model_config = ConfigDict(extra="forbid")

    project_id: NormalizedId = Field(description="Langflow project id carried for watsonx snapshot creation.")
    source_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Adapter-neutral source reference used for create/update snapshot correlation.",
    )


class WatsonxConnectionRawPayload(BaseModel):
    """Connection payload for creating a new watsonx connection/config."""

    app_id: NormalizedId = Field(
        description=(
            "App id used for operation references. resource_name_prefix is applied only when creating resources."
        )
    )
    environment_variables: dict[EnvVarKey, EnvVarValueSpec] | None = Field(None, description="Environment variables.")
    provider_config: AdapterPayload | None = Field(None, description="Provider-specific connection configuration.")


class WatsonxUpdateTools(BaseModel):
    """Tool pool available to update operations."""

    model_config = ConfigDict(extra="forbid")

    existing_ids: list[NormalizedId] | None = Field(
        default=None,
        description="Known existing provider tool ids available for operation references.",
    )
    raw_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]] | None = Field(
        default=None,
        description="Raw tool payloads keyed by BaseFlowArtifact.name.",
    )

    @field_validator("existing_ids")
    @classmethod
    def dedupe_existing_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def dedupe_raw_tool_names(self) -> WatsonxUpdateTools:
        raw_payloads = self.raw_payloads or []
        if not raw_payloads:
            return self
        # Stable first-win dedupe keyed by raw tool name.
        deduped_by_name: dict[str, BaseFlowArtifact[WatsonxFlowArtifactProviderData]] = {}
        for payload in raw_payloads:
            deduped_by_name.setdefault(payload.name, payload)
        self.raw_payloads = list(deduped_by_name.values())
        return self


class WatsonxUpdateConnections(BaseModel):
    """Connection pool available to update operations."""

    model_config = ConfigDict(extra="forbid")

    existing_app_ids: list[NormalizedId] | None = Field(
        default=None,
        description="Known existing app ids available for operation references.",
    )
    raw_payloads: list[WatsonxConnectionRawPayload] | None = Field(
        default=None,
        description=(
            "Raw connection payloads keyed by app_id. resource_name_prefix is applied only when resources are created."
        ),
    )

    @field_validator("existing_app_ids")
    @classmethod
    def dedupe_existing_app_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_unique_raw_app_ids(self) -> WatsonxUpdateConnections:
        raw_payloads = self.raw_payloads or []
        app_id_counts = Counter(payload.app_id for payload in raw_payloads)
        duplicates = sorted(app_id for app_id, count in app_id_counts.items() if count > 1)
        if duplicates:
            msg = f"connections.raw_payloads contains duplicate app_id values: {duplicates}"
            raise ValueError(msg)
        return self


def _validate_declared_app_id_pools(
    *,
    existing_app_ids: set[str],
    raw_app_ids: set[str],
) -> set[str]:
    collisions = sorted(existing_app_ids.intersection(raw_app_ids))
    if collisions:
        msg = f"connections.existing_app_ids collides with raw app ids from connections.raw_payloads: {collisions}"
        raise ValueError(msg)
    return existing_app_ids.union(raw_app_ids)


def _validate_bind_operation_references(
    *,
    operations: list[WatsonxBindOperation],
    raw_tool_names: set[str],
    existing_tool_ids: set[str],
    valid_app_ids: set[str],
) -> set[str]:
    referenced_app_ids: set[str] = set()
    for operation in operations:
        if operation.tool.name_of_raw is not None and operation.tool.name_of_raw not in raw_tool_names:
            msg = f"bind.tool.name_of_raw not found in tools.raw_payloads: [{operation.tool.name_of_raw!r}]"
            raise ValueError(msg)
        if operation.tool.reference_id is not None and operation.tool.reference_id not in existing_tool_ids:
            msg = f"bind.tool.reference_id not found in tools.existing_ids: [{operation.tool.reference_id!r}]"
            raise ValueError(msg)
        for app_id in operation.app_ids:
            referenced_app_ids.add(app_id)
            if app_id not in valid_app_ids:
                msg = (
                    "operation app_ids must be declared in "
                    "connections.existing_app_ids or connections.raw_payloads[*].app_id: "
                    f"[{app_id!r}]"
                )
                raise ValueError(msg)
    return referenced_app_ids


def _validate_all_declared_app_ids_are_referenced(
    *,
    existing_app_ids: set[str],
    raw_app_ids: set[str],
    referenced_app_ids: set[str],
) -> None:
    unused_existing_app_ids = sorted(existing_app_ids.difference(referenced_app_ids))
    if unused_existing_app_ids:
        msg = f"connections.existing_app_ids contains ids not referenced by operations: {unused_existing_app_ids}"
        raise ValueError(msg)
    unused_raw_app_ids = sorted(raw_app_ids.difference(referenced_app_ids))
    if unused_raw_app_ids:
        msg = f"connections.raw_payloads contains app_id values not referenced by operations: {unused_raw_app_ids}"
        raise ValueError(msg)


class WatsonxToolReference(BaseModel):
    """Tool selector for bind operations."""

    model_config = ConfigDict(extra="forbid")

    reference_id: NormalizedId | None = Field(
        default=None,
        description="Existing provider tool id.",
    )
    name_of_raw: RawToolName | None = Field(
        default=None,
        description="Name of a tool entry declared in tools.raw_payloads.",
    )

    @model_validator(mode="after")
    def validate_exactly_one_selector(self) -> WatsonxToolReference:
        has_reference_id = self.reference_id is not None
        has_name_of_raw = self.name_of_raw is not None
        if has_reference_id == has_name_of_raw:
            msg = "Exactly one of 'tool.reference_id' or 'tool.name_of_raw' must be provided."
            raise ValueError(msg)
        return self


class WatsonxBindOperation(BaseModel):
    """Bind a selected tool to a selected app id."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["bind"]
    tool: WatsonxToolReference
    app_ids: list[NormalizedId] = Field(
        min_length=1,
        description=(
            "Operation app ids to bind. Must match declared connection pools "
            "(connections.existing_app_ids or connections.raw_payloads[*].app_id)."
        ),
    )

    @field_validator("app_ids")
    @classmethod
    def dedupe_app_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class WatsonxUnbindOperation(BaseModel):
    """Unbind app connection from a tool."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["unbind"]
    tool_id: NormalizedId = Field(description="Existing provider tool id.")
    app_ids: list[NormalizedId] = Field(
        min_length=1,
        description=("Operation app ids to unbind. Must reference connections.existing_app_ids only."),
    )

    @field_validator("app_ids")
    @classmethod
    def dedupe_app_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class WatsonxRemoveToolOperation(BaseModel):
    """Detach an existing tool from the deployment."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["remove_tool"]
    tool_id: NormalizedId = Field(description="Existing provider tool id to remove from deployment.")


WatsonxUpdateOperation = Annotated[
    WatsonxBindOperation | WatsonxUnbindOperation | WatsonxRemoveToolOperation,
    Field(discriminator="op"),
]


class WatsonxDeploymentUpdatePayload(BaseModel):
    """Watsonx provider_data contract for deployment update patch operations.

    Notes:
    - operations[*].app_ids are operation-side ids.
    - resource_name_prefix is applied only when creating resources
      (for raw connections and raw tools).
    """

    model_config = ConfigDict(extra="forbid")

    resource_name_prefix: str | None = Field(
        default=None,
        description=(
            "Prefix applied only when creating resources: "
            "derived app ids from connections.raw_payloads[*].app_id and created tool names."
        ),
    )
    tools: WatsonxUpdateTools = Field(default_factory=WatsonxUpdateTools)
    connections: WatsonxUpdateConnections = Field(default_factory=WatsonxUpdateConnections)
    operations: list[WatsonxUpdateOperation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxDeploymentUpdatePayload:
        raw_tool_names = {payload.name for payload in (self.tools.raw_payloads or [])}
        existing_tool_ids = set(self.tools.existing_ids or [])

        existing_app_ids = set(self.connections.existing_app_ids or [])
        raw_app_ids = {payload.app_id for payload in (self.connections.raw_payloads or [])}
        valid_app_ids = _validate_declared_app_id_pools(
            existing_app_ids=existing_app_ids,
            raw_app_ids=raw_app_ids,
        )

        bind_operations = [operation for operation in self.operations if isinstance(operation, WatsonxBindOperation)]
        referenced_app_ids = _validate_bind_operation_references(
            operations=bind_operations,
            raw_tool_names=raw_tool_names,
            existing_tool_ids=existing_tool_ids,
            valid_app_ids=valid_app_ids,
        )

        for operation in self.operations:
            if not isinstance(operation, WatsonxUnbindOperation):
                continue
            for app_id in operation.app_ids:
                referenced_app_ids.add(app_id)
                if app_id not in valid_app_ids:
                    msg = (
                        "operation app_ids must be declared in "
                        "connections.existing_app_ids or connections.raw_payloads[*].app_id: "
                        f"[{app_id!r}]"
                    )
                    raise ValueError(msg)
                if app_id in raw_app_ids:
                    msg = f"unbind.operation app_ids must reference connections.existing_app_ids only: [{app_id!r}]"
                    raise ValueError(msg)

        _validate_all_declared_app_ids_are_referenced(
            existing_app_ids=existing_app_ids,
            raw_app_ids=raw_app_ids,
            referenced_app_ids=referenced_app_ids,
        )

        return self


class WatsonxDeploymentCreatePayload(BaseModel):
    """Watsonx provider_data contract for deployment create operations."""

    model_config = ConfigDict(extra="forbid")

    resource_name_prefix: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description=(
            "Prefix applied only when creating resources: "
            "derived app ids from connections.raw_payloads[*].app_id and created tool names."
        )
    )
    tools: WatsonxUpdateTools = Field(default_factory=WatsonxUpdateTools)
    connections: WatsonxUpdateConnections = Field(default_factory=WatsonxUpdateConnections)
    operations: list[WatsonxBindOperation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxDeploymentCreatePayload:
        raw_tool_names = {payload.name for payload in (self.tools.raw_payloads or [])}
        existing_tool_ids = set(self.tools.existing_ids or [])

        existing_app_ids = set(self.connections.existing_app_ids or [])
        raw_app_ids = {payload.app_id for payload in (self.connections.raw_payloads or [])}
        valid_app_ids = _validate_declared_app_id_pools(
            existing_app_ids=existing_app_ids,
            raw_app_ids=raw_app_ids,
        )
        referenced_app_ids = _validate_bind_operation_references(
            operations=self.operations,
            raw_tool_names=raw_tool_names,
            existing_tool_ids=existing_tool_ids,
            valid_app_ids=valid_app_ids,
        )
        _validate_all_declared_app_ids_are_referenced(
            existing_app_ids=existing_app_ids,
            raw_app_ids=raw_app_ids,
            referenced_app_ids=referenced_app_ids,
        )
        return self


class WatsonxCreateSnapshotBinding(BaseModel):
    """Normalized binding item for deployment create snapshot correlation."""

    model_config = ConfigDict(extra="forbid")

    source_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    snapshot_id: NormalizedId
    source_name: str | None = None
    provider_name: str | None = None

    @field_validator("source_name", "provider_name", mode="before")
    @classmethod
    def normalize_optional_value(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class WatsonxDeploymentCreateResultData(BaseModel):
    """Normalized provider result payload for deployment create."""

    model_config = ConfigDict(extra="ignore")

    snapshot_bindings: list[WatsonxCreateSnapshotBinding] = Field(default_factory=list)


class WatsonxToolAppBinding(BaseModel):
    """Normalized tool-app binding item for deployment update result."""

    model_config = ConfigDict(extra="forbid")

    tool_id: NormalizedId
    app_ids: list[NormalizedId] = Field(default_factory=list)

    @field_validator("app_ids", mode="before")
    @classmethod
    def normalize_app_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(app_id).strip() for app_id in value if str(app_id).strip()]


class WatsonxDeploymentUpdateResultData(BaseModel):
    """Normalized provider result payload for deployment update."""

    model_config = ConfigDict(extra="ignore")

    created_snapshot_ids: list[NormalizedId] = Field(default_factory=list)
    added_snapshot_bindings: list[WatsonxCreateSnapshotBinding] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxToolAppBinding] | None = None

    @field_validator("created_snapshot_ids", mode="before")
    @classmethod
    def normalize_created_snapshot_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(snapshot_id).strip() for snapshot_id in value if str(snapshot_id).strip()]


class WatsonxExecutionResultData(BaseModel):
    """Normalized provider result payload for execution create/status."""

    model_config = ConfigDict(extra="allow")

    run_id: NormalizedId | None = None
    execution_id: NormalizedId | None = None
    agent_id: NormalizedId | None = None
    deployment_id: NormalizedId | None = None


class WatsonxProviderUpdateApplyResult(BaseModel):
    """Public adapter contract for update helper apply results."""

    model_config = ConfigDict(extra="forbid")

    added_snapshot_ids: list[NormalizedId] = Field(default_factory=list)
    added_snapshot_bindings: list[WatsonxCreateSnapshotBinding] = Field(default_factory=list)


class WatsonxProviderCreateApplyResult(BaseModel):
    """Public adapter contract for create helper apply results."""

    model_config = ConfigDict(extra="forbid")

    agent_id: NormalizedId
    config_id: NormalizedId | None = None
    snapshot_ids: list[NormalizedId] = Field(default_factory=list)
    snapshot_bindings: list[WatsonxCreateSnapshotBinding] = Field(default_factory=list)
    prefixed_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


# Canonical watsonx deployment payload registry. Adapter service and mapper
# consume this same object to keep slot ownership explicit and avoid drift.
PAYLOAD_SCHEMAS = DeploymentPayloadSchemas(
    deployment_create=PayloadSlot(WatsonxDeploymentCreatePayload),
    flow_artifact=PayloadSlot(WatsonxFlowArtifactProviderData),
    deployment_create_result=PayloadSlot(WatsonxDeploymentCreateResultData),
    deployment_update=PayloadSlot(WatsonxDeploymentUpdatePayload),
    deployment_update_result=PayloadSlot(WatsonxDeploymentUpdateResultData),
    execution_create_result=PayloadSlot(WatsonxExecutionResultData),
    execution_status_result=PayloadSlot(WatsonxExecutionResultData),
)
