"""Watsonx Orchestrate deployment payload contracts."""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Any, Literal, TypeVar
from uuid import uuid4

from lfx.services.adapters.deployment.exceptions import InvalidContentError
from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
from lfx.services.adapters.deployment.schema import BaseFlowArtifact, EnvVarKey, EnvVarValueSpec, NormalizedId
from lfx.services.adapters.payload import AdapterPayload, PayloadSlot
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WXO_SANITIZE_RE,
    WXO_TRANSLATE,
)

RawToolName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NormalizedStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
LANGFLOW_WXO_RESOURCE_NAME_PREFIX = "langflow_"
T = TypeVar("T")


def normalize_wxo_name(name: str) -> str:
    return WXO_SANITIZE_RE.sub("", name.translate(WXO_TRANSLATE))


def validate_wxo_name(name: str, *, field_label: str) -> str:
    """Normalize and validate a wxO resource name."""
    normalized_name = normalize_wxo_name(str(name))
    if not normalized_name:
        msg = f"{field_label} must include at least one alphanumeric character."
        raise InvalidContentError(message=msg)
    if not normalized_name[0].isalpha():
        msg = f"{field_label} must start with a letter."
        raise InvalidContentError(message=msg)
    return normalized_name


def normalize_wxo_display_name_segment(display_name: str, *, resource: str) -> str:
    normalized_display_name = normalize_wxo_name(display_name).strip("_")
    if normalized_display_name:
        return normalized_display_name
    normalized_resource = normalize_wxo_name(resource).strip("_").lower()
    if not normalized_resource:
        msg = (
            "Display name did not include any alphanumeric characters, so fallback naming used the 'resource' "
            "argument. The 'resource' argument must include at least one alphanumeric character. "
            f"Received: '{resource}'"
        )
        raise InvalidContentError(message=msg)
    return normalized_resource


def build_langflow_wxo_resource_name(display_name: str, *, resource: str) -> str:
    normalized_display_name = normalize_wxo_display_name_segment(display_name, resource=resource)
    return f"{LANGFLOW_WXO_RESOURCE_NAME_PREFIX}{normalized_display_name}_{uuid4().hex[:8]}"


def validate_technical_name(name: str | None, *, field_label: str) -> str:
    technical_name = ensure_field_not_none(name, field_label=field_label)
    if not technical_name:
        msg = f"{field_label} must include at least one alphanumeric character."
        raise InvalidContentError(message=msg)
    if not technical_name[0].isalpha():
        msg = f"{field_label} must start with a letter."
        raise InvalidContentError(message=msg)
    if WXO_SANITIZE_RE.search(technical_name):
        msg = f"{field_label} must only contain letters, numbers, and underscores."
        raise InvalidContentError(message=msg)
    return technical_name


def ensure_field_not_none(value: T | None, *, field_label: str) -> T:
    """Validate that an explicitly provided field is not null."""
    if value is None:
        msg = f"{field_label} cannot be set to null."
        raise InvalidContentError(message=msg)
    return value


def ensure_field_not_empty(value: str | None, *, field_label: str) -> str:
    """Validate that an explicitly provided string field is neither null nor blank."""
    field_value = ensure_field_not_none(value, field_label=field_label)
    if not field_value.strip():
        msg = f"{field_label} cannot be empty."
        raise InvalidContentError(message=msg)
    return field_value


def validate_description(description: str | None, *, field_label: str) -> str | None:
    """Validate an explicit description update."""
    if description is not None and not description.strip():
        msg = f"{field_label} cannot be empty."
        raise InvalidContentError(message=msg)
    return description


def _validate_non_empty_string(value: str) -> str:
    if not value.strip():
        msg = "String must not be empty."
        raise ValueError(msg)
    return value


NonEmptyString = Annotated[str, AfterValidator(_validate_non_empty_string)]


class WatsonxFlowArtifactProviderData(BaseModel):
    """Provider metadata for watsonx flow artifacts."""

    model_config = ConfigDict(extra="forbid")

    project_id: NormalizedId = Field(description="Langflow project id carried for watsonx snapshot creation.")
    source_ref: NormalizedStr = Field(
        description="Adapter-neutral source reference used for create/update snapshot correlation.",
    )
    # Optional only at input time. Since tool_display_name is required, the
    # validator below always fills tool_name when the caller omits it.
    tool_name: NormalizedStr | None = Field(
        default=None,
        description="Provider technical wxO tool name. Generated from tool_display_name when omitted.",
    )
    tool_display_name: NormalizedStr = Field(
        description="User-facing wxO tool label.",
    )

    @model_validator(mode="after")
    def validate_or_generate_tool_name(self) -> WatsonxFlowArtifactProviderData:
        if self.tool_name is not None:
            try:
                self.tool_name = validate_technical_name(self.tool_name, field_label="Tool name")
            except InvalidContentError as exc:
                raise ValueError(exc.message) from exc
            return self

        try:
            self.tool_name = build_langflow_wxo_resource_name(self.tool_display_name, resource="Tool")
        except InvalidContentError as exc:
            raise ValueError(exc.message) from exc
        return self


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
        description="Raw tool payloads keyed by provider_data.tool_name.",
    )

    @model_validator(mode="after")
    def dedupe_raw_tool_technical_names(self) -> WatsonxUpdateTools:
        raw_payloads = self.raw_payloads or []
        if not raw_payloads:
            return self
        deduped_by_name: dict[str, BaseFlowArtifact[WatsonxFlowArtifactProviderData]] = {}
        for payload in raw_payloads:
            deduped_by_name.setdefault(payload.provider_data.tool_name, payload)
        self.raw_payloads = list(deduped_by_name.values())
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


def _validate_bind_operation_references(
    *,
    operations: list[WatsonxBindOperation],
    raw_tool_names: set[str],
) -> set[str]:
    referenced_app_ids: set[str] = set()
    for operation in operations:
        if operation.tool.name_of_raw is not None and operation.tool.name_of_raw not in raw_tool_names:
            msg = f"bind.tool.name_of_raw not found in tools.raw_payloads: [{operation.tool.name_of_raw!r}]"
            raise ValueError(msg)
        for app_id in operation.app_ids:
            referenced_app_ids.add(app_id)
    return referenced_app_ids


def _validate_tool_ref_consistency(operations: list[Any]) -> None:
    """Reject conflicting source_ref values for the same tool_id across operations."""
    seen: dict[str, str] = {}
    for operation in operations:
        ref: WatsonxToolRefBinding | None = None
        if isinstance(operation, WatsonxBindOperation):
            ref = operation.tool.tool_id_with_ref
        elif isinstance(operation, (WatsonxUnbindOperation, WatsonxRemoveToolOperation, WatsonxAttachToolOperation)):
            ref = operation.tool
        if ref is None:
            continue
        existing_source_ref = seen.get(ref.tool_id)
        if existing_source_ref is not None and existing_source_ref != ref.source_ref:
            msg = f"Conflicting source_ref for tool_id={ref.tool_id!r}: {existing_source_ref!r} vs {ref.source_ref!r}"
            raise ValueError(msg)
        seen[ref.tool_id] = ref.source_ref


def _validate_overlapping_existing_tool_operations(operations: list[Any]) -> None:
    bind_app_ids_by_tool: dict[str, set[str]] = {}
    unbind_app_ids_by_tool: dict[str, set[str]] = {}
    attach_tool_ids: set[str] = set()
    remove_tool_ids: set[str] = set()

    for operation in operations:
        if isinstance(operation, WatsonxBindOperation):
            ref = operation.tool.tool_id_with_ref
            if ref is None:
                continue
            bind_app_ids_by_tool.setdefault(ref.tool_id, set()).update(operation.app_ids)
            continue

        if isinstance(operation, WatsonxAttachToolOperation):
            tool_id = operation.tool.tool_id
            if tool_id in attach_tool_ids:
                msg = f"Duplicate attach_tool operation for tool_id: [{tool_id!r}]"
                raise ValueError(msg)
            attach_tool_ids.add(tool_id)
            continue

        if isinstance(operation, WatsonxUnbindOperation):
            unbind_app_ids_by_tool.setdefault(operation.tool.tool_id, set()).update(operation.app_ids)
            continue

        if isinstance(operation, WatsonxRemoveToolOperation):
            tool_id = operation.tool.tool_id
            if tool_id in remove_tool_ids:
                msg = f"Duplicate remove_tool operation for tool_id: [{tool_id!r}]"
                raise ValueError(msg)
            remove_tool_ids.add(tool_id)
            continue

    bind_tool_ids = set(bind_app_ids_by_tool)
    overlap_attach_bind = sorted(attach_tool_ids.intersection(bind_tool_ids))
    if overlap_attach_bind:
        msg = (
            "attach_tool cannot be combined with bind.tool.tool_id_with_ref for the same tool_id(s): "
            f"{overlap_attach_bind}"
        )
        raise ValueError(msg)

    for tool_id in sorted(remove_tool_ids):
        if tool_id in bind_tool_ids or tool_id in attach_tool_ids or tool_id in unbind_app_ids_by_tool:
            msg = f"remove_tool cannot be combined with bind/attach_tool/unbind for the same tool_id: [{tool_id!r}]"
            raise ValueError(msg)

    for tool_id, bind_app_ids in bind_app_ids_by_tool.items():
        overlap_app_ids = sorted(bind_app_ids.intersection(unbind_app_ids_by_tool.get(tool_id, set())))
        if overlap_app_ids:
            msg = f"bind and unbind app_ids overlap for the same tool_id [{tool_id!r}]: {overlap_app_ids}"
            raise ValueError(msg)


def _validate_all_declared_app_ids_are_referenced(
    *,
    raw_app_ids: set[str],
    referenced_app_ids: set[str],
) -> None:
    unused_raw_app_ids = sorted(raw_app_ids.difference(referenced_app_ids))
    if unused_raw_app_ids:
        msg = f"connections.raw_payloads contains app_id values not referenced by operations: {unused_raw_app_ids}"
        raise ValueError(msg)


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
    """Bind a selected tool to app ids."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["bind"]
    tool: WatsonxToolReference
    app_ids: list[NormalizedId] = Field(
        min_length=1,
        description=(
            "Operation app ids to bind. app_ids found in connections.raw_payloads "
            "reference new raw connections; all other app_ids are treated as existing connections."
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
    tool: WatsonxToolRefBinding = Field(description="Existing provider tool reference with source_ref correlation.")
    app_ids: list[NormalizedId] = Field(
        min_length=1,
        description=("Operation app ids to unbind. Must not reference connections.raw_payloads app_ids."),
    )

    @field_validator("app_ids")
    @classmethod
    def dedupe_app_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class WatsonxRenameToolOperation(BaseModel):
    """Update a Langflow-managed tool's user-facing label on the provider."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["rename_tool"]
    tool: WatsonxToolRefBinding = Field(
        description="Existing provider tool reference with source_ref correlation.",
    )
    tool_display_name: NormalizedStr = Field(description="User-facing wxO tool label.")


class WatsonxRemoveToolOperation(BaseModel):
    """Detach an existing tool from the deployment."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["remove_tool"]
    tool: WatsonxToolRefBinding = Field(
        description="Existing provider tool reference with source_ref correlation.",
    )


class WatsonxAttachToolOperation(BaseModel):
    """Attach an existing tool to the deployment without connection bindings."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["attach_tool"]
    tool: WatsonxToolRefBinding = Field(
        description="Existing provider tool reference with source_ref correlation.",
    )


WatsonxUpdateOperation = Annotated[
    WatsonxBindOperation
    | WatsonxUnbindOperation
    | WatsonxRenameToolOperation
    | WatsonxRemoveToolOperation
    | WatsonxAttachToolOperation,
    Field(discriminator="op"),
]

WatsonxCreateOperation = Annotated[
    WatsonxBindOperation | WatsonxAttachToolOperation,
    Field(discriminator="op"),
]


class WatsonxDeploymentUpdatePayload(BaseModel):
    """Watsonx provider_data contract for deployment update patch operations.

    Notes:
    - bind/unbind operations[*].app_ids are operation-side ids.
    - put_tools performs a standalone full replacement of the agent's tool
      list.  The agent will have exactly these tool IDs and no others.
      It cannot be combined with operations, tools, or connections
      (the validator rejects such payloads).
      This should only be used by rollback to restore pre-update
      attachment state.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: NormalizedStr | None = Field(
        default=None,
        description="User-facing label to set on the wxO agent.",
    )
    tools: WatsonxUpdateTools = Field(default_factory=WatsonxUpdateTools)
    connections: WatsonxUpdateConnections = Field(default_factory=WatsonxUpdateConnections)
    operations: list[WatsonxUpdateOperation] = Field(default_factory=list)
    put_tools: list[NormalizedId] | None = Field(
        default=None,
        description=(
            "Declarative list of existing provider tool IDs the deployment should have. "
            "Performs a standalone full replacement of the agent's tool list — "
            "cannot be combined with operations, tools, or connections. "
            "This should only be used by rollback to restore pre-update attachment state."
        ),
    )
    llm: NormalizedId | None = Field(
        default=None,
        description=("Provider language model identifier to use for the deployment agent."),
    )

    @field_validator("put_tools")
    @classmethod
    def dedupe_put_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))

    @property
    def has_tool_work(self) -> bool:
        """Whether this payload includes tool-level mutations (put_tools, operations, or raw tool creation).

        The service layer uses this to decide between the lightweight
        spec-only update path and the full provider-plan path.
        """
        return bool(self.put_tools is not None or self.operations or self.tools.raw_payloads)

    @model_validator(mode="after")
    def validate_has_work(self) -> WatsonxDeploymentUpdatePayload:
        if self.put_tools is not None:
            has_other = self.operations or self.tools.raw_payloads or self.connections.raw_payloads
            if has_other:
                msg = "put_tools is a standalone full replacement and cannot be combined with other fields."
                raise ValueError(msg)
            return self
        if not self.operations:
            has_connections = self.connections.raw_payloads
            if has_connections:
                msg = "connections require at least one bind/unbind operation that references app_ids."
                raise ValueError(msg)
            # Remaining valid no-operation cases:
            # - LLM-only update (no raw_payloads, no connections).
            # - raw_payloads without operations: tools are created and
            #   attached to the agent without connection bindings
            #   (connectionless-tool flow). The plan builder auto-creates
            #   entries for all declared raw_payloads even without explicit
            #   bind/attach_tool operations referencing them.
            # - empty/no-op provider_data can pass schema validation; the
            #   service layer rejects it when there are no spec updates.
            return self
        return self

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxDeploymentUpdatePayload:
        if self.put_tools is not None:
            return self
        raw_tool_names = {payload.provider_data.tool_name for payload in (self.tools.raw_payloads or [])}

        raw_app_ids = {payload.app_id for payload in (self.connections.raw_payloads or [])}
        bind_operations = [operation for operation in self.operations if isinstance(operation, WatsonxBindOperation)]
        referenced_app_ids = _validate_bind_operation_references(
            operations=bind_operations,
            raw_tool_names=raw_tool_names,
        )

        for operation in self.operations:
            if not isinstance(operation, WatsonxUnbindOperation):
                continue
            for app_id in operation.app_ids:
                referenced_app_ids.add(app_id)
                if app_id in raw_app_ids:
                    msg = f"unbind.operation app_ids must not reference connections.raw_payloads app_ids: [{app_id!r}]"
                    raise ValueError(msg)

        _validate_all_declared_app_ids_are_referenced(
            raw_app_ids=raw_app_ids,
            referenced_app_ids=referenced_app_ids,
        )
        _validate_tool_ref_consistency(self.operations)
        _validate_overlapping_existing_tool_operations(self.operations)

        return self


class WatsonxDeploymentCreatePayload(BaseModel):
    """Watsonx provider_data contract for deployment create operations."""

    model_config = ConfigDict(extra="forbid")

    display_name: NormalizedStr = Field(description="User-facing label to set on the wxO agent.")
    tools: WatsonxUpdateTools = Field(default_factory=WatsonxUpdateTools)
    connections: WatsonxUpdateConnections = Field(default_factory=WatsonxUpdateConnections)
    operations: list[WatsonxCreateOperation] = Field(default_factory=list)
    llm: NormalizedId = Field(description="Provider model identifier to use for the deployment agent.")

    @model_validator(mode="after")
    def validate_has_work(self) -> WatsonxDeploymentCreatePayload:
        if not self.operations and not self.tools.raw_payloads:
            msg = "At least one bind/attach_tool operation or tools.raw_payloads entry must be provided for create."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxDeploymentCreatePayload:
        raw_tool_names = {payload.provider_data.tool_name for payload in (self.tools.raw_payloads or [])}

        raw_app_ids = {payload.app_id for payload in (self.connections.raw_payloads or [])}
        bind_operations = [operation for operation in self.operations if isinstance(operation, WatsonxBindOperation)]
        referenced_app_ids = _validate_bind_operation_references(
            operations=bind_operations,
            raw_tool_names=raw_tool_names,
        )
        _validate_all_declared_app_ids_are_referenced(
            raw_app_ids=raw_app_ids,
            referenced_app_ids=referenced_app_ids,
        )
        _validate_tool_ref_consistency(self.operations)
        _validate_overlapping_existing_tool_operations(self.operations)
        return self


class WatsonxToolRefBinding(BaseModel):
    """Correlates a source_ref (e.g. flow version id) with a provider tool_id.

    Used for both newly-created and pre-existing tools so callers can translate
    between adapter-level tool ids and higher-level source references.
    """

    model_config = ConfigDict(extra="forbid")

    source_ref: NormalizedStr
    tool_id: NormalizedId


class WatsonxResultToolRefBinding(WatsonxToolRefBinding):
    """Tool ref binding with provenance flag for adapter results.

    Extends the base binding with a ``created`` flag so consumers can
    distinguish tools that were created during the operation from
    pre-existing tools whose refs were passed through for correlation.
    """

    created: bool = Field(description="True when the tool was created during this operation, False for pre-existing.")


class WatsonxDeploymentCreateResultData(BaseModel):
    """Provider result payload for deployment create."""

    model_config = ConfigDict(extra="ignore")

    display_name: NonEmptyString
    app_ids: list[NonEmptyString] = Field(default_factory=list)
    tools_with_refs: list[WatsonxToolRefBinding] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxToolAppBinding] = Field(default_factory=list)


class WatsonxToolAppBinding(BaseModel):
    """Tool-app binding item for deployment result payloads."""

    model_config = ConfigDict(extra="forbid")

    tool_id: NonEmptyString
    app_ids: list[NonEmptyString] = Field(default_factory=list)


class WatsonxDeploymentUpdateResultData(BaseModel):
    """Provider result payload for deployment update.

    Semantics:
    - ``created_snapshot_ids``: IDs of snapshot/tools created during this update.
    - ``added_snapshot_ids``: IDs of snapshot/tools newly attached to the agent
      by this update (includes ``created_snapshot_ids`` and newly attached
      pre-existing tools).
    - ``created_snapshot_bindings``: ``source_ref -> tool_id`` bindings for
      snapshots/tools created during this update.
    - ``added_snapshot_bindings``: ``source_ref -> tool_id`` bindings for
      snapshots/tools newly attached to the agent by this update.
    - ``removed_snapshot_bindings``: ``source_ref -> tool_id`` bindings for
      snapshots/tools detached from the agent by this update.
    - ``referenced_snapshot_bindings``: all operation-referenced bindings used
      for correlation/response shaping (includes created, added-existing,
      removed, and other touched existing refs).
    """

    model_config = ConfigDict(extra="ignore")

    name: NonEmptyString
    display_name: NonEmptyString
    description: str | None = None
    created_app_ids: list[NonEmptyString] = Field(default_factory=list)
    created_snapshot_ids: list[NonEmptyString] = Field(default_factory=list)
    added_snapshot_ids: list[NonEmptyString] = Field(default_factory=list)
    created_snapshot_bindings: list[WatsonxResultToolRefBinding] = Field(default_factory=list)
    # Newly attached snapshot/tool refs (created + newly attached existing).
    added_snapshot_bindings: list[WatsonxResultToolRefBinding] = Field(default_factory=list)
    # Detached snapshot/tool refs.
    removed_snapshot_bindings: list[WatsonxResultToolRefBinding] = Field(default_factory=list)
    # Full operation correlation set (created + existing refs).
    referenced_snapshot_bindings: list[WatsonxResultToolRefBinding] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxToolAppBinding] | None = None

    @field_validator("created_app_ids", "created_snapshot_ids", "added_snapshot_ids")
    @classmethod
    def dedupe_result_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class WatsonxAgentExecutionResultData(BaseModel):
    """Provider result payload for agent execution create/status."""

    model_config = ConfigDict(extra="allow")

    execution_id: NonEmptyString | None = None
    agent_id: NonEmptyString | None = Field(
        default=None,
        description="WXO agent identifier (resource_key in Langflow DB).",
    )
    thread_id: NonEmptyString | None = None
    status: str | None = None
    result: Any | None = None
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    cancelled_at: str | None = None
    last_error: str | None = None


class WatsonxModelOut(BaseModel):
    """Model metadata returned by wxO model catalog endpoints."""

    model_config = ConfigDict(extra="ignore")

    model_name: NonEmptyString


class WatsonxDeploymentLlmListResultData(BaseModel):
    """Provider result payload for deployment LLM listing."""

    model_config = ConfigDict(extra="forbid")

    models: list[WatsonxModelOut] = Field(default_factory=list)


class WatsonxSnapshotConnectionsProviderData(BaseModel):
    """Provider data contract for snapshot list items in snapshot-ids mode."""

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyString
    display_name: NonEmptyString
    connections: dict[NonEmptyString, NonEmptyString] = Field(default_factory=dict)


class WatsonxConfigItemProviderData(BaseModel):
    """Provider data contract for config list items."""

    model_config = ConfigDict(extra="forbid")

    type: NonEmptyString
    environment: NonEmptyString


class WatsonxDeploymentItemProviderData(BaseModel):
    """Provider data contract for deployment list items."""

    model_config = ConfigDict(extra="forbid")

    display_name: NonEmptyString
    description: str
    tool_ids: list[NonEmptyString]
    llm: NonEmptyString
    environments: list[NonEmptyString]


class WatsonxConfigListResultData(BaseModel):
    """Provider-result metadata contract for config listing.

    ``deployment_id`` is present for deployment-scoped listings and absent for
    tenant-scoped listings.
    """

    model_config = ConfigDict(extra="forbid")

    deployment_id: NonEmptyString | None = None
    tool_ids: list[NonEmptyString] | None = None


class WatsonxSnapshotListResultData(BaseModel):
    """Provider-result metadata contract for snapshot listing.

    ``deployment_id`` is present for deployment-scoped listings and absent for
    tenant-scoped listings.
    """

    model_config = ConfigDict(extra="forbid")

    deployment_id: NonEmptyString | None = None


class WatsonxProviderCreateApplyResult(BaseModel):
    """Public adapter contract for create helper apply results."""

    model_config = ConfigDict(extra="forbid")

    agent_id: NormalizedId
    app_ids: list[NormalizedId] = Field(default_factory=list)
    tools_with_refs: list[WatsonxToolRefBinding] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxToolAppBinding] = Field(default_factory=list)
    deployment_name: NormalizedStr
    display_name: NormalizedStr
    description: NormalizedStr


class WatsonxVerifyCredentialsPayload(BaseModel):
    """WXO credential shape for provider account verification."""

    model_config = ConfigDict(extra="forbid")

    api_key: NormalizedStr


# Canonical watsonx deployment payload registry. Adapter service and mapper
# consume this same object to keep slot ownership explicit and avoid drift.
PAYLOAD_SCHEMAS = DeploymentPayloadSchemas(
    deployment_create=PayloadSlot(WatsonxDeploymentCreatePayload),
    flow_artifact=PayloadSlot(WatsonxFlowArtifactProviderData),
    snapshot_item_data=PayloadSlot(WatsonxSnapshotConnectionsProviderData),
    config_item_data=PayloadSlot(WatsonxConfigItemProviderData),
    deployment_item_data=PayloadSlot(WatsonxDeploymentItemProviderData),
    deployment_create_result=PayloadSlot(WatsonxDeploymentCreateResultData),
    deployment_update=PayloadSlot(WatsonxDeploymentUpdatePayload),
    deployment_update_result=PayloadSlot(WatsonxDeploymentUpdateResultData),
    execution_create_result=PayloadSlot(WatsonxAgentExecutionResultData),
    execution_status_result=PayloadSlot(WatsonxAgentExecutionResultData),
    deployment_llm_list_result=PayloadSlot(WatsonxDeploymentLlmListResultData),
    config_list_result=PayloadSlot(WatsonxConfigListResultData),
    snapshot_list_result=PayloadSlot(WatsonxSnapshotListResultData),
    verify_credentials=PayloadSlot(WatsonxVerifyCredentialsPayload),
)
