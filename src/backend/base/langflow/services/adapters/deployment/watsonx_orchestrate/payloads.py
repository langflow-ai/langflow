"""Watsonx Orchestrate deployment payload contracts."""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Any, Literal

from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
from lfx.services.adapters.deployment.schema import BaseFlowArtifact, EnvVarKey, EnvVarValueSpec, NormalizedId
from lfx.services.adapters.payload import AdapterPayload, PayloadSlot
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from langflow.services.adapters.deployment.watsonx_orchestrate.resource_name_prefix import (
    validate_resource_name_prefix_for_provider,
)

RawToolName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ResourceNamePrefixInput = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


def _normalize_non_empty_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)):
        msg = "Expected an iterable of IDs, got a string-like value."
        raise TypeError(msg)
    try:
        return [normalized for item in value if (normalized := str(item).strip())]
    except TypeError as err:
        msg = "Expected an iterable of IDs."
        raise TypeError(msg) from err


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
        description=("App id used for operation references. Newly created connections preserve this app_id.")
    )
    environment_variables: dict[EnvVarKey, EnvVarValueSpec] | None = Field(None, description="Environment variables.")
    provider_config: AdapterPayload | None = Field(None, description="Provider-specific connection configuration.")


class WatsonxUpdateTools(BaseModel):
    """Tool pool available to update operations."""

    model_config = ConfigDict(extra="forbid")

    raw_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]] | None = Field(
        default=None,
        description="Raw tool payloads keyed by BaseFlowArtifact.name.",
    )

    @model_validator(mode="after")  # wxO api raises 409 conflict status code for names of existing tools
    def validate_unique_raw_tool_names(self) -> WatsonxUpdateTools:
        raw_payloads = self.raw_payloads or []
        name_counts = Counter(payload.name for payload in raw_payloads)
        duplicates = sorted(name for name, count in name_counts.items() if count > 1)
        if duplicates:
            msg = f"tools.raw_payloads contains duplicate tool names: {duplicates}"
            raise ValueError(msg)
        return self


class WatsonxUpdateConnections(BaseModel):
    """Connection pool available to update operations."""

    model_config = ConfigDict(extra="forbid")

    raw_payloads: list[WatsonxConnectionRawPayload] | None = Field(
        default=None,
        description=("Raw connection payloads keyed by app_id. Newly created connections preserve this app_id."),
    )

    @model_validator(mode="after")
    def validate_unique_raw_app_ids(self) -> WatsonxUpdateConnections:
        raw_payloads = self.raw_payloads or []
        app_id_counts = Counter(payload.app_id for payload in raw_payloads)
        duplicates = sorted(app_id for app_id, count in app_id_counts.items() if count > 1)
        if duplicates:
            msg = f"connections.raw_payloads contains duplicate app_id values: {duplicates}"
            raise ValueError(msg)
        return self


class WatsonxBindAppRef(BaseModel):
    """Connection selector used by bind operations."""

    model_config = ConfigDict(extra="forbid")

    app_id: NormalizedId | None = None
    app_id_of_raw: NormalizedId | None = None

    @model_validator(mode="after")
    def validate_exactly_one_selector(self) -> WatsonxBindAppRef:
        provided = [self.app_id is not None, self.app_id_of_raw is not None]
        if sum(provided) != 1:
            msg = "Exactly one of 'app_id' or 'app_id_of_raw' must be provided."
            raise ValueError(msg)
        return self

    @property
    def operation_app_id(self) -> str:
        if self.app_id is not None:
            return str(self.app_id)
        if self.app_id_of_raw is not None:
            return str(self.app_id_of_raw)
        msg = "Invalid WatsonxBindAppRef: no app id selector was provided."
        raise ValueError(msg)

    @property
    def is_raw(self) -> bool:
        return self.app_id_of_raw is not None

    @property
    def is_existing(self) -> bool:
        return self.app_id is not None


def _collect_operation_reference_state(
    *,
    operations: list[Any],
    raw_tool_names: set[str],
    raw_app_ids: set[str],
) -> tuple[set[str], set[str], list[WatsonxToolRefBinding]]:
    referenced_raw_app_ids: set[str] = set()
    invalid_unbind_raw_app_ids: set[str] = set()
    tool_refs: list[WatsonxToolRefBinding] = []

    for operation in operations:
        if isinstance(operation, WatsonxBindOperation):
            if operation.tool.tool_id_with_ref is not None:
                tool_refs.append(operation.tool.tool_id_with_ref)
            if operation.tool.name_of_raw is not None and operation.tool.name_of_raw not in raw_tool_names:
                msg = f"bind.tool.name_of_raw not found in tools.raw_payloads: [{operation.tool.name_of_raw!r}]"
                raise ValueError(msg)
            for app_ref in operation.app_refs:
                if app_ref.is_raw:
                    referenced_raw_app_ids.add(app_ref.operation_app_id)
            continue

        if isinstance(operation, WatsonxUnbindOperation):
            tool_refs.append(operation.tool)
            invalid_unbind_raw_app_ids.update(raw_app_ids.intersection(operation.app_ids))
            continue

        if isinstance(operation, WatsonxRemoveToolOperation):
            tool_refs.append(operation.tool)

    return referenced_raw_app_ids, invalid_unbind_raw_app_ids, tool_refs


def _validate_bind_raw_app_ids_are_declared(
    *,
    raw_app_ids: set[str],
    referenced_raw_app_ids: set[str],
) -> None:
    missing_raw_app_ids = sorted(referenced_raw_app_ids.difference(raw_app_ids))
    if missing_raw_app_ids:
        first_missing_app_id = missing_raw_app_ids[0]
        msg = (
            "bind operation app_id_of_raw must be declared in "
            "connections.raw_payloads[*].app_id: "
            f"[{first_missing_app_id!r}]"
        )
        raise ValueError(msg)


def _validate_unbind_app_ids_reference_existing(
    *,
    invalid_unbind_raw_app_ids: set[str],
) -> None:
    invalid_unbind_app_ids = sorted(invalid_unbind_raw_app_ids)
    if invalid_unbind_app_ids:
        msg = f"unbind.operation app_ids must reference existing app ids only: [{invalid_unbind_app_ids[0]!r}]"
        raise ValueError(msg)


def _validate_all_declared_raw_app_ids_are_referenced(
    *,
    raw_app_ids: set[str],
    referenced_raw_app_ids: set[str],
) -> None:
    unused_raw_app_ids = sorted(raw_app_ids.difference(referenced_raw_app_ids))
    if unused_raw_app_ids:
        msg = (
            "connections.raw_payloads contains app_id values not referenced by bind operation refs: "
            f"{unused_raw_app_ids}"
        )
        raise ValueError(msg)


def _collect_bind_existing_app_ids(*, operations: list[Any]) -> set[str]:
    return {
        app_ref.operation_app_id
        for operation in operations
        if isinstance(operation, WatsonxBindOperation)
        for app_ref in operation.app_refs
        if app_ref.is_existing
    }


def _validate_existing_bind_app_ids_do_not_collide_with_raw_payloads(
    *,
    raw_app_ids: set[str],
    bind_existing_app_ids: set[str],
) -> None:
    collisions = sorted(raw_app_ids.intersection(bind_existing_app_ids))
    if collisions:
        msg = (
            "bind app_id values must not overlap connections.raw_payloads[*].app_id; "
            "use app_id_of_raw for raw connections: "
            f"[{collisions[0]!r}]"
        )
        raise ValueError(msg)


def _validate_no_conflicting_update_operations(*, operations: list[Any]) -> None:
    bind_existing_tool_ids: set[str] = set()
    remove_tool_ids: set[str] = set()
    bind_existing_app_ids_by_tool: dict[str, set[str]] = {}
    unbind_app_ids_by_tool: dict[str, set[str]] = {}

    for operation in operations:
        if isinstance(operation, WatsonxBindOperation) and operation.tool.tool_id_with_ref is not None:
            tool_id = operation.tool.tool_id_with_ref.tool_id
            bind_existing_tool_ids.add(tool_id)
            bind_existing_app_ids = set(operation.app_ids_of_existing())
            if bind_existing_app_ids:
                bind_existing_app_ids_by_tool.setdefault(tool_id, set()).update(bind_existing_app_ids)
            continue
        if isinstance(operation, WatsonxUnbindOperation):
            unbind_app_ids_by_tool.setdefault(operation.tool.tool_id, set()).update(operation.app_ids)
            continue
        if isinstance(operation, WatsonxRemoveToolOperation):
            remove_tool_ids.add(operation.tool.tool_id)

    bind_remove_conflicts = sorted(bind_existing_tool_ids.intersection(remove_tool_ids))
    if bind_remove_conflicts:
        msg = f"update operations conflict: bind and remove_tool target the same tool: [{bind_remove_conflicts[0]!r}]"
        raise ValueError(msg)

    shared_tool_ids = sorted(bind_existing_app_ids_by_tool.keys() & unbind_app_ids_by_tool.keys())
    for tool_id in shared_tool_ids:
        overlap = sorted(bind_existing_app_ids_by_tool[tool_id].intersection(unbind_app_ids_by_tool[tool_id]))
        if overlap:
            msg = (
                "update operations conflict: bind and unbind target the same tool/app pair: "
                f"tool_id={tool_id!r}, app_id={overlap[0]!r}"
            )
            raise ValueError(msg)


def _normalize_bind_app_refs(value: list[WatsonxBindAppRef]) -> list[WatsonxBindAppRef]:
    normalized: list[WatsonxBindAppRef] = []
    seen: set[tuple[str, str]] = set()
    selector_kind_by_app_id: dict[str, str] = {}
    for ref in value:
        selector_kind = "raw" if ref.is_raw else "existing"
        app_id = ref.operation_app_id
        previous_selector_kind = selector_kind_by_app_id.get(app_id)
        if previous_selector_kind is not None and previous_selector_kind != selector_kind:
            msg = (
                "bind app_refs contains mixed selector kinds for the same app_id: "
                f"{app_id!r} appears as both {previous_selector_kind!r} and {selector_kind!r}."
            )
            raise ValueError(msg)
        selector_kind_by_app_id[app_id] = selector_kind
        key = (selector_kind, app_id)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(ref)
    return normalized


def _validate_tool_ref_consistency(tool_refs: list[WatsonxToolRefBinding]) -> None:
    """Reject conflicting source_ref values for the same tool_id across operations."""
    seen: dict[str, str] = {}
    for ref in tool_refs:
        existing_source_ref = seen.get(ref.tool_id)
        if existing_source_ref is not None and existing_source_ref != ref.source_ref:
            msg = f"Conflicting source_ref for tool_id={ref.tool_id!r}: {existing_source_ref!r} vs {ref.source_ref!r}"
            raise ValueError(msg)
        seen[ref.tool_id] = ref.source_ref


class WatsonxToolReference(BaseModel):
    """Tool selector for bind operations."""

    model_config = ConfigDict(extra="forbid")

    tool_id_with_ref: WatsonxToolRefBinding | None = Field(
        default=None,
        description="Existing provider tool reference with source_ref correlation.",
    )
    name_of_raw: RawToolName | None = Field(
        default=None,
        description="Name of a tool entry declared in tools.raw_payloads.",
    )

    @model_validator(mode="after")
    def validate_exactly_one_selector(self) -> WatsonxToolReference:
        has_tool_id_with_ref = self.tool_id_with_ref is not None
        has_name_of_raw = self.name_of_raw is not None
        if has_tool_id_with_ref == has_name_of_raw:
            msg = "Exactly one of 'tool.tool_id_with_ref' or 'tool.name_of_raw' must be provided."
            raise ValueError(msg)
        return self


class WatsonxBindOperation(BaseModel):
    """Bind a selected tool to a selected app id."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["bind"]
    tool: WatsonxToolReference
    app_refs: list[WatsonxBindAppRef] = Field(
        min_length=1,
        description=("Operation app references to bind. Each entry must specify 'app_id' or 'app_id_of_raw'."),
    )

    @field_validator("app_refs")
    @classmethod
    def dedupe_app_refs(cls, value: list[WatsonxBindAppRef]) -> list[WatsonxBindAppRef]:
        return _normalize_bind_app_refs(value)

    def all_app_ids(self) -> list[str]:
        return [app_ref.operation_app_id for app_ref in self.app_refs]

    def app_ids_of_existing(self) -> list[str]:
        return [app_ref.operation_app_id for app_ref in self.app_refs if app_ref.is_existing]


class WatsonxUnbindOperation(BaseModel):
    """Unbind app connection from a tool."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["unbind"]
    tool: WatsonxToolRefBinding = Field(description="Existing provider tool reference with source_ref correlation.")
    app_ids: list[NormalizedId] = Field(
        min_length=1,
        description=("Operation app ids to unbind. Must reference existing app ids only."),
    )

    @field_validator("app_ids")
    @classmethod
    def dedupe_app_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class WatsonxRemoveToolOperation(BaseModel):
    """Detach an existing tool from the deployment."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["remove_tool"]
    tool: WatsonxToolRefBinding = Field(
        description="Existing provider tool reference with source_ref correlation.",
    )


WatsonxUpdateOperation = Annotated[
    WatsonxBindOperation | WatsonxUnbindOperation | WatsonxRemoveToolOperation,
    Field(discriminator="op"),
]


class WatsonxDeploymentUpdatePayload(BaseModel):
    """Watsonx provider_data contract for deployment update patch operations.

    Notes:
    - bind operations identify app references in operations[*].app_refs.
    - unbind operations use operations[*].app_ids (existing app ids only).
    - resource_name_prefix is applied only when creating resources
      (for raw tool names).
    - resource_name_prefix is a provider-specific naming/deconfliction hint.
    - put_tools performs a standalone full replacement of the agent's tool
      list.  The agent will have exactly these tool IDs and no others.
      It cannot be combined with operations, tools, connections, or
      resource_name_prefix (the validator rejects such payloads).
      This should only be used by rollback to restore pre-update
      attachment state.
    """

    model_config = ConfigDict(extra="forbid")

    resource_name_prefix: ResourceNamePrefixInput | None = Field(
        default=None,
        description=(
            "Provider-specific naming/deconfliction hint applied only when creating resources: "
            "applied to created tool names."
        ),
    )
    tools: WatsonxUpdateTools = Field(default_factory=WatsonxUpdateTools)
    connections: WatsonxUpdateConnections = Field(default_factory=WatsonxUpdateConnections)
    operations: list[WatsonxUpdateOperation] = Field(default_factory=list)
    put_tools: list[NormalizedId] | None = Field(
        default=None,
        description=(
            "Declarative list of existing provider tool IDs the deployment should have. "
            "Performs a standalone full replacement of the agent's tool list — "
            "cannot be combined with operations, tools, connections, or resource_name_prefix. "
            "This should only be used by rollback to restore pre-update attachment state."
        ),
    )

    @field_validator("put_tools")
    @classmethod
    def dedupe_put_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))

    @field_validator("resource_name_prefix")
    @classmethod
    def validate_resource_name_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        validate_resource_name_prefix_for_provider(value)
        return value

    @model_validator(mode="after")
    def validate_has_work(self) -> WatsonxDeploymentUpdatePayload:
        if self.put_tools is not None:
            has_other = (
                self.operations or self.tools.raw_payloads or self.connections.raw_payloads or self.resource_name_prefix
            )
            if has_other:
                msg = "put_tools is a standalone full replacement and cannot be combined with other fields."
                raise ValueError(msg)
            return self
        if not self.operations:
            msg = "At least one of 'operations' or 'put_tools' must be provided."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxDeploymentUpdatePayload:
        if self.put_tools is not None:
            return self
        raw_tool_names = {payload.name for payload in (self.tools.raw_payloads or [])}

        raw_app_ids = {payload.app_id for payload in (self.connections.raw_payloads or [])}
        bind_existing_app_ids = _collect_bind_existing_app_ids(operations=self.operations)
        referenced_raw_app_ids, invalid_unbind_raw_app_ids, tool_refs = _collect_operation_reference_state(
            operations=self.operations,
            raw_tool_names=raw_tool_names,
            raw_app_ids=raw_app_ids,
        )
        _validate_existing_bind_app_ids_do_not_collide_with_raw_payloads(
            raw_app_ids=raw_app_ids,
            bind_existing_app_ids=bind_existing_app_ids,
        )
        _validate_bind_raw_app_ids_are_declared(
            raw_app_ids=raw_app_ids,
            referenced_raw_app_ids=referenced_raw_app_ids,
        )
        _validate_unbind_app_ids_reference_existing(invalid_unbind_raw_app_ids=invalid_unbind_raw_app_ids)

        _validate_all_declared_raw_app_ids_are_referenced(
            raw_app_ids=raw_app_ids,
            referenced_raw_app_ids=referenced_raw_app_ids,
        )
        _validate_no_conflicting_update_operations(operations=self.operations)
        _validate_tool_ref_consistency(tool_refs)

        return self


class WatsonxDeploymentCreatePayload(BaseModel):
    """Watsonx provider_data contract for deployment create operations."""

    model_config = ConfigDict(extra="forbid")

    resource_name_prefix: ResourceNamePrefixInput = Field(
        description=(
            "Provider-specific naming/deconfliction hint applied only when creating resources: "
            "applied to created tool names and deployment names."
        )
    )
    tools: WatsonxUpdateTools = Field(default_factory=WatsonxUpdateTools)
    connections: WatsonxUpdateConnections = Field(default_factory=WatsonxUpdateConnections)
    operations: list[WatsonxBindOperation] = Field(min_length=1)

    @field_validator("resource_name_prefix")
    @classmethod
    def validate_resource_name_prefix(cls, value: str) -> str:
        validate_resource_name_prefix_for_provider(value)
        return value

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxDeploymentCreatePayload:
        raw_tool_names = {payload.name for payload in (self.tools.raw_payloads or [])}

        raw_app_ids = {payload.app_id for payload in (self.connections.raw_payloads or [])}
        bind_existing_app_ids = _collect_bind_existing_app_ids(operations=self.operations)
        referenced_raw_app_ids, _, tool_refs = _collect_operation_reference_state(
            operations=self.operations,
            raw_tool_names=raw_tool_names,
            raw_app_ids=raw_app_ids,
        )
        _validate_existing_bind_app_ids_do_not_collide_with_raw_payloads(
            raw_app_ids=raw_app_ids,
            bind_existing_app_ids=bind_existing_app_ids,
        )
        _validate_bind_raw_app_ids_are_declared(
            raw_app_ids=raw_app_ids,
            referenced_raw_app_ids=referenced_raw_app_ids,
        )
        _validate_all_declared_raw_app_ids_are_referenced(
            raw_app_ids=raw_app_ids,
            referenced_raw_app_ids=referenced_raw_app_ids,
        )
        _validate_tool_ref_consistency(tool_refs)
        return self


class WatsonxToolRefBinding(BaseModel):
    """Correlates a source_ref (e.g. flow version id) with a provider tool_id.

    Used for both newly-created and pre-existing tools so callers can translate
    between adapter-level tool ids and higher-level source references.
    """

    model_config = ConfigDict(extra="forbid")

    source_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    tool_id: NormalizedId


class WatsonxResultToolRefBinding(WatsonxToolRefBinding):
    """Tool ref binding with provenance flag for adapter results.

    Extends the base binding with a ``created`` flag so consumers can
    distinguish tools that were created during the operation from
    pre-existing tools whose refs were passed through for correlation.
    """

    created: bool = Field(description="True when the tool was created during this operation, False for pre-existing.")


class WatsonxDeploymentCreateResultData(BaseModel):
    """Normalized provider result payload for deployment create."""

    model_config = ConfigDict(extra="ignore")

    created_app_ids: list[NormalizedId] = Field(default_factory=list)
    tools_with_refs: list[WatsonxToolRefBinding] = Field(
        default_factory=list,
        description=(
            "Source_ref/tool_id bindings for all tools involved in create operations "
            "(both pre-existing and newly created)."
        ),
    )
    tool_app_bindings: list[WatsonxToolAppBinding] = Field(default_factory=list)

    @field_validator("created_app_ids", mode="before")
    @classmethod
    def normalize_created_app_ids(cls, value: Any) -> list[str]:
        return _normalize_non_empty_str_list(value)


class WatsonxToolAppBinding(BaseModel):
    """Normalized tool-app binding item for deployment result payloads."""

    model_config = ConfigDict(extra="forbid")

    tool_id: NormalizedId
    app_ids: list[NormalizedId] = Field(default_factory=list)

    @field_validator("app_ids", mode="before")
    @classmethod
    def normalize_app_ids(cls, value: Any) -> list[str]:
        return _normalize_non_empty_str_list(value)


class WatsonxDeploymentUpdateResultData(BaseModel):
    """Normalized provider result payload for deployment update."""

    model_config = ConfigDict(extra="ignore")

    created_app_ids: list[NormalizedId] = Field(default_factory=list)
    created_snapshot_ids: list[NormalizedId] = Field(default_factory=list)
    added_snapshot_bindings: list[WatsonxResultToolRefBinding] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxToolAppBinding] | None = None

    @field_validator("created_app_ids", mode="before")
    @classmethod
    def normalize_created_app_ids(cls, value: Any) -> list[str]:
        return _normalize_non_empty_str_list(value)

    @field_validator("created_snapshot_ids", mode="before")
    @classmethod
    def normalize_created_snapshot_ids(cls, value: Any) -> list[str]:
        return _normalize_non_empty_str_list(value)


class WatsonxAgentExecutionResultData(BaseModel):
    """Normalized provider result payload for agent execution create/status."""

    model_config = ConfigDict(extra="allow")

    execution_id: NormalizedId | None = None
    agent_id: NormalizedId | None = Field(
        default=None,
        description="WXO agent identifier (resource_key in Langflow DB).",
    )
    status: str | None = None
    result: Any | None = None
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    cancelled_at: str | None = None
    last_error: str | None = None


class WatsonxProviderUpdateApplyResult(BaseModel):
    """Public adapter contract for update helper apply results."""

    model_config = ConfigDict(extra="forbid")

    created_app_ids: list[NormalizedId] = Field(default_factory=list)
    added_snapshot_ids: list[NormalizedId] = Field(default_factory=list)
    added_snapshot_bindings: list[WatsonxResultToolRefBinding] = Field(default_factory=list)


class WatsonxProviderCreateApplyResult(BaseModel):
    """Public adapter contract for create helper apply results."""

    model_config = ConfigDict(extra="forbid")

    agent_id: NormalizedId
    created_app_ids: list[NormalizedId] = Field(default_factory=list)
    tools_with_refs: list[WatsonxToolRefBinding] = Field(
        default_factory=list,
        description=(
            "Source_ref/tool_id bindings for all tools involved in create operations "
            "(both pre-existing and newly created)."
        ),
    )
    tool_app_bindings: list[WatsonxToolAppBinding] = Field(default_factory=list)
    prefixed_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WatsonxVerifyCredentialsPayload(BaseModel):
    """WXO credential shape for provider account verification."""

    model_config = ConfigDict(extra="forbid")

    api_key: str


# Canonical watsonx deployment payload registry. Adapter service and mapper
# consume this same object to keep slot ownership explicit and avoid drift.
PAYLOAD_SCHEMAS = DeploymentPayloadSchemas(
    deployment_create=PayloadSlot(WatsonxDeploymentCreatePayload),
    flow_artifact=PayloadSlot(WatsonxFlowArtifactProviderData),
    deployment_create_result=PayloadSlot(WatsonxDeploymentCreateResultData),
    deployment_update=PayloadSlot(WatsonxDeploymentUpdatePayload),
    deployment_update_result=PayloadSlot(WatsonxDeploymentUpdateResultData),
    execution_create_result=PayloadSlot(WatsonxAgentExecutionResultData),
    execution_status_result=PayloadSlot(WatsonxAgentExecutionResultData),
    verify_credentials=PayloadSlot(WatsonxVerifyCredentialsPayload),
)
