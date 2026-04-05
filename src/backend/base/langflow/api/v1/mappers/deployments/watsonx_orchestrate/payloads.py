"""Watsonx deployment payload models at API boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from lfx.services.adapters.deployment.schema import DeploymentType
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from langflow.api.v1.mappers.deployments.contracts import CreateFlowArtifactProviderData

WatsonxApiLlmName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


class WatsonxApiFlowArtifactProviderData(CreateFlowArtifactProviderData):
    """Watsonx create-time flow artifact provider_data contract."""

    project_id: str = Field(min_length=1)


class WatsonxApiBindOperation(BaseModel):
    """Bind operation using a flow-version reference."""

    model_config = {"extra": "forbid"}

    op: Literal["bind"]
    flow_version_id: UUID
    app_ids: list[str] = Field(
        description=(
            "Connection app ids to bind. Use an empty list to create/attach "
            "the flow version as a tool with no connection bindings."
        ),
    )
    tool_name: str | None = Field(
        default=None,
        description=("Optional user-provided tool name. When omitted, the tool name is derived from the flow name."),
    )


class WatsonxApiUnbindOperation(BaseModel):
    """Unbind operation for an attached flow-version tool."""

    model_config = {"extra": "forbid"}

    op: Literal["unbind"]
    flow_version_id: UUID
    app_ids: list[str] = Field(min_length=1)


class WatsonxApiRemoveToolOperation(BaseModel):
    """Remove-tool operation for an attached flow-version tool.

    Resolves tool_id from flow_version_deployment_attachment and detaches
    the tool from the agent.  The attachment record is also deleted.
    """

    model_config = {"extra": "forbid"}

    op: Literal["remove_tool"]
    flow_version_id: UUID


# ---------------------------------------------------------------------------
# Tool-id-based operations
#
# These operations give clients direct control over WXO tools by provider
# tool_id, without requiring a Langflow flow_version_id.  They run in
# parallel to the flow-version-id operations above:
#
# - flow_version_id ops are convenient: Langflow resolves the tool_id
#   from internal attachment state and manages the attachment lifecycle.
# - tool_id ops are explicit: the client supplies the provider tool_id
#   directly.  These operations do NOT create or modify
#   flow_version_deployment_attachment records -- they are purely
#   provider-side agent composition changes.
# ---------------------------------------------------------------------------


class WatsonxApiBindToolOperation(BaseModel):
    """Attach an existing tool to the agent and optionally bind connections.

    Subsumes a separate "add_tool" operation: at the adapter level, a bind
    with ``tool_id_with_ref`` handles both "add tool to agent if not
    present" and "bind connections" in a single code path.  Empty
    ``app_ids`` means attach-only (no connection bindings).
    """

    model_config = {"extra": "forbid"}

    op: Literal["bind_tool"]
    tool_id: str = Field(min_length=1, description="Provider-owned tool identifier.")
    app_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Connection app ids to bind.  Use an empty list to attach "
            "the tool to the agent without binding connections."
        ),
    )


class WatsonxApiUnbindToolOperation(BaseModel):
    """Unbind connections from an existing tool (tool stays attached).

    Only modifies connection bindings on the tool; does not detach
    the tool from the agent.
    """

    model_config = {"extra": "forbid"}

    op: Literal["unbind_tool"]
    tool_id: str = Field(min_length=1, description="Provider-owned tool identifier.")
    app_ids: list[str] = Field(min_length=1)


class WatsonxApiRemoveToolByIdOperation(BaseModel):
    """Detach a tool from the agent by provider tool_id."""

    model_config = {"extra": "forbid"}

    op: Literal["remove_tool_by_id"]
    tool_id: str = Field(min_length=1, description="Provider-owned tool identifier.")


WatsonxApiUpdateOperation = Annotated[
    WatsonxApiBindOperation
    | WatsonxApiUnbindOperation
    | WatsonxApiRemoveToolOperation
    | WatsonxApiBindToolOperation
    | WatsonxApiUnbindToolOperation
    | WatsonxApiRemoveToolByIdOperation,
    Field(discriminator="op"),
]


class WatsonxApiConnectionCredentialItem(BaseModel):
    """API-facing connection credential declaration."""

    model_config = {"extra": "forbid"}

    key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    source: Literal["raw", "variable"] = "variable"


class WatsonxApiKeyValueConnectionPayload(BaseModel):
    """API-facing key-value connection payload for app id."""

    model_config = {"extra": "forbid"}

    app_id: str = Field(min_length=1)
    credentials: list[WatsonxApiConnectionCredentialItem] | None = None

    @field_validator("credentials")
    @classmethod
    def validate_unique_credential_keys(
        cls,
        value: list[WatsonxApiConnectionCredentialItem] | None,
    ) -> list[WatsonxApiConnectionCredentialItem] | None:
        if value is None:
            return None
        seen: set[str] = set()
        duplicates: set[str] = set()
        for item in value:
            if item.key in seen:
                duplicates.add(item.key)
            seen.add(item.key)
        if duplicates:
            msg = f"credentials contains duplicate key values: {sorted(duplicates)}"
            raise ValueError(msg)
        return value


class WatsonxApiUpdateConnections(BaseModel):
    """Connection declarations used by update operations."""

    model_config = {"extra": "forbid"}

    key_value: list[WatsonxApiKeyValueConnectionPayload] | None = None


def _collect_api_referenced_app_ids(operations: list[Any]) -> set[str]:
    referenced_app_ids: set[str] = set()
    for operation in operations:
        operation_app_ids = getattr(operation, "app_ids", None)
        if not operation_app_ids:
            continue
        referenced_app_ids.update(operation_app_ids)
    return referenced_app_ids


def _validate_api_unbind_not_raw(*, operations: list[Any], raw_app_ids: set[str]) -> None:
    for operation in operations:
        if isinstance(operation, WatsonxApiUnbindOperation):
            invalid_raw = sorted(raw_app_ids.intersection(set(operation.app_ids)))
            if invalid_raw:
                msg = f"unbind.operation app_ids must not reference connections.key_value app_ids: {invalid_raw}"
                raise ValueError(msg)
            continue
        if isinstance(operation, WatsonxApiUnbindToolOperation):
            invalid_raw = sorted(raw_app_ids.intersection(set(operation.app_ids)))
            if invalid_raw:
                msg = f"unbind_tool.operation app_ids must not reference connections.key_value app_ids: {invalid_raw}"
                raise ValueError(msg)


def _validate_api_tool_id_operations(operations: list[Any]) -> None:
    bind_tool_ids: set[str] = set()
    unbind_tool_ids: set[str] = set()
    remove_tool_ids: set[str] = set()
    for operation in operations:
        if isinstance(operation, WatsonxApiBindToolOperation):
            bind_tool_ids.add(operation.tool_id.strip())
            continue
        if isinstance(operation, WatsonxApiUnbindToolOperation):
            unbind_tool_ids.add(operation.tool_id.strip())
            continue
        if isinstance(operation, WatsonxApiRemoveToolByIdOperation):
            remove_tool_ids.add(operation.tool_id.strip())
    remove_conflicts = remove_tool_ids.intersection(bind_tool_ids | unbind_tool_ids)
    if remove_conflicts:
        msg = (
            "remove_tool_by_id cannot be combined with bind_tool/unbind_tool "
            f"for the same tool_id: {sorted(remove_conflicts)}"
        )
        raise ValueError(msg)


def _validate_api_unused_raw_app_ids(*, raw_app_ids: set[str], referenced_app_ids: set[str]) -> None:
    unused_raw_app_ids = sorted(raw_app_ids.difference(referenced_app_ids))
    if unused_raw_app_ids:
        msg = f"connections.key_value contains app_id values not referenced by operations: {unused_raw_app_ids}"
        raise ValueError(msg)


class WatsonxApiDeploymentUpdatePayload(BaseModel):
    """Watsonx provider_data API contract for deployment update operations.

    ``operations`` defaults to an empty list so that LLM-only updates
    (changing the model without any tool/connection changes) can be
    expressed without providing operations.
    """

    model_config = {"extra": "forbid"}

    llm: WatsonxApiLlmName = Field(description="Provider model identifier to use for the deployment agent.")
    connections: WatsonxApiUpdateConnections = Field(default_factory=WatsonxApiUpdateConnections)
    operations: list[WatsonxApiUpdateOperation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxApiDeploymentUpdatePayload:
        raw_app_ids = {raw.app_id for raw in (self.connections.key_value or [])}
        referenced_app_ids = _collect_api_referenced_app_ids(self.operations)
        _validate_api_unbind_not_raw(operations=self.operations, raw_app_ids=raw_app_ids)
        _validate_api_tool_id_operations(self.operations)
        _validate_api_unused_raw_app_ids(raw_app_ids=raw_app_ids, referenced_app_ids=referenced_app_ids)
        return self


WatsonxApiCreateOperation = Annotated[
    WatsonxApiBindOperation | WatsonxApiBindToolOperation,
    Field(discriminator="op"),
]


class WatsonxApiDeploymentCreatePayload(BaseModel):
    """Watsonx provider_data API contract for deployment create operations."""

    model_config = {"extra": "forbid"}

    llm: WatsonxApiLlmName = Field(description="Provider model identifier to use for the deployment agent.")
    connections: WatsonxApiUpdateConnections = Field(default_factory=WatsonxApiUpdateConnections)
    operations: list[WatsonxApiCreateOperation] = Field(default_factory=list)
    existing_agent_id: str | None = Field(
        default=None,
        description=(
            "Provider-owned agent id to update/reuse instead of creating a new agent. "
            "When provided, operations are optional and may be empty for DB-only onboarding."
        ),
    )

    @field_validator("existing_agent_id")
    @classmethod
    def validate_existing_agent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            msg = "existing_agent_id must not be empty or whitespace."
            raise ValueError(msg)
        return normalized

    @model_validator(mode="after")
    def validate_create_operation_requirements(self) -> WatsonxApiDeploymentCreatePayload:
        has_operations = bool(self.operations)
        if self.existing_agent_id is None and not has_operations:
            msg = "operations must include at least one bind or bind_tool operation for new agent creation."
            raise ValueError(msg)
        raw_app_ids = {raw.app_id for raw in (self.connections.key_value or [])}
        referenced_app_ids = _collect_api_referenced_app_ids(self.operations)
        _validate_api_unused_raw_app_ids(raw_app_ids=raw_app_ids, referenced_app_ids=referenced_app_ids)
        return self


class WatsonxApiToolAppBinding(BaseModel):
    """API response shape for a Watsonx tool binding.

    Always includes ``tool_id`` (the provider-owned tool identifier).
    ``flow_version_id`` is populated when the tool was created or
    referenced through a flow-version-id operation; it is ``None``
    for tool-id-based operations whose ``source_ref`` is not a valid
    Langflow UUID.
    """

    model_config = {"extra": "forbid"}

    flow_version_id: UUID | None = None
    tool_id: str = Field(min_length=1, description="Provider-owned tool identifier.")
    app_ids: list[str] = Field(default_factory=list)

    @field_validator("app_ids", mode="before")
    @classmethod
    def normalize_app_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(app_id).strip() for app_id in value if str(app_id).strip()]


class WatsonxApiDeploymentCreateResultData(BaseModel):
    """Normalized provider-result payload used by Watsonx mapper create shapers."""

    model_config = {"extra": "ignore"}

    created_app_ids: list[str] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxApiToolAppBinding] | None = None

    @field_validator("created_app_ids", mode="before")
    @classmethod
    def normalize_created_app_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [normalized for app_id in value if (normalized := str(app_id).strip())]

    @classmethod
    def from_provider_result(cls, provider_result: Any) -> WatsonxApiDeploymentCreateResultData:
        if not isinstance(provider_result, dict):
            return cls()
        return cls.model_validate(provider_result)

    def to_api_provider_data(self) -> dict[str, Any] | None:
        """Return API-safe provider_data subset for deployment create responses."""
        payload = self.model_dump(mode="json", include={"created_app_ids", "tool_app_bindings"}, exclude_none=True)
        return payload or None


class WatsonxApiDeploymentUpdateResultData(BaseModel):
    """Normalized provider-result payload used by Watsonx mapper update shapers."""

    model_config = {"extra": "ignore"}

    created_app_ids: list[str] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxApiToolAppBinding] | None = None

    @field_validator("created_app_ids", mode="before")
    @classmethod
    def normalize_created_app_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [normalized for app_id in value if (normalized := str(app_id).strip())]

    @classmethod
    def from_provider_result(cls, provider_result: Any) -> WatsonxApiDeploymentUpdateResultData:
        if not isinstance(provider_result, dict):
            return cls()
        return cls.model_validate(provider_result)

    def to_api_provider_data(self) -> dict[str, Any] | None:
        """Return API-safe provider_data subset for deployment update responses."""
        payload = self.model_dump(mode="json", include={"created_app_ids", "tool_app_bindings"}, exclude_none=True)
        return payload or None


class WatsonxApiModelOut(BaseModel):
    """Minimal API-boundary model metadata needed for deployment LLM listing."""

    model_config = {"extra": "ignore"}

    model_name: str = Field(min_length=1)

    @field_validator("model_name")
    @classmethod
    def normalize_model_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "model_name must not be empty."
            raise ValueError(msg)
        return normalized


class WatsonxApiDeploymentLlmListResultData(BaseModel):
    """API-boundary payload used by mapper LLM-list response shaping."""

    model_config = {"extra": "forbid"}

    models: list[WatsonxApiModelOut] = Field(default_factory=list)


class WatsonxApiProviderDeploymentListItem(BaseModel):
    """Provider-only deployment item returned in list provider_data."""

    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1, description="Provider-owned deployment identifier.")
    name: str
    type: DeploymentType
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    tool_ids: list[str] = Field(default_factory=list)
    environment: str | None = None

    @field_validator("tool_ids", mode="before")
    @classmethod
    def normalize_tool_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [normalized for tool_id in value if (normalized := str(tool_id).strip())]

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: Any) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None


class WatsonxApiDeploymentListProviderData(BaseModel):
    """Provider-level metadata attached to DeploymentListResponse.provider_data."""

    deployments: list[WatsonxApiProviderDeploymentListItem] = Field(default_factory=list)


class WatsonxApiConfigListItem(BaseModel):
    """API-facing config list item payload under config-list provider_data."""

    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("id", "name", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            msg = "Config list item fields 'id' and 'name' must be non-empty strings."
            raise ValueError(msg)
        return normalized


class WatsonxApiConfigListProviderData(BaseModel):
    """Provider-level metadata attached to DeploymentConfigListResponse."""

    model_config = {"extra": "forbid"}

    tool_ids: list[str] | None = None
    connections: list[WatsonxApiConfigListItem] = Field(default_factory=list)
    page: int | None = Field(default=None, ge=1)
    size: int | None = Field(default=None, ge=1)
    total: int | None = Field(default=None, ge=0)

    @field_validator("tool_ids", mode="before")
    @classmethod
    def normalize_tool_ids(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        return [str(tool_id).strip() for tool_id in value if str(tool_id).strip()]


class WatsonxApiSnapshotListItem(BaseModel):
    """API-facing snapshot list item payload under snapshot-list provider_data."""

    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    connections: dict[str, str] = Field(default_factory=dict)

    @field_validator("id", "name", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            msg = "Snapshot list item fields 'id' and 'name' must be non-empty strings."
            raise ValueError(msg)
        return normalized


class WatsonxApiSnapshotListProviderData(BaseModel):
    """Provider-level metadata attached to DeploymentSnapshotListResponse."""

    model_config = {"extra": "forbid"}

    tools: list[WatsonxApiSnapshotListItem] = Field(default_factory=list)
    page: int | None = Field(default=None, ge=1)
    size: int | None = Field(default=None, ge=1)
    total: int | None = Field(default=None, ge=0)


class WatsonxApiDeploymentFlowVersionItemData(BaseModel):
    """API-facing provider_data contract for deployment flow-version list items."""

    model_config = {"extra": "forbid"}

    app_ids: list[str] = Field(default_factory=list)

    @field_validator("app_ids", mode="before")
    @classmethod
    def normalize_app_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(app_id).strip() for app_id in value if str(app_id).strip()]


class _WatsonxApiAgentExecutionResultBase(BaseModel):
    """Shared fields for API-facing agent execution result payloads.

    All provider-owned identifiers and metadata live here inside
    ``provider_data``.  The enclosing response only carries Langflow-owned
    fields (``deployment_id``).  ``deployment_id`` (Langflow DB UUID) is
    intentionally omitted from this schema to avoid ownership confusion.
    """

    model_config = {"extra": "allow"}

    execution_id: str | None = None
    agent_id: str | None = None
    thread_id: str | None = None
    status: str | None = None
    result: Any | None = None
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    cancelled_at: str | None = None
    last_error: str | None = None

    @field_validator("execution_id", "agent_id", mode="before")
    @classmethod
    def normalize_optional_id(cls, value: Any) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

    @classmethod
    def from_provider_result(cls, provider_result: Any) -> _WatsonxApiAgentExecutionResultBase:
        if not isinstance(provider_result, dict):
            return cls()
        return cls.model_validate(provider_result)


class WatsonxApiAgentExecutionCreateResultData(_WatsonxApiAgentExecutionResultBase):
    """API-facing provider_result payload returned when an agent execution is created."""


class WatsonxApiAgentExecutionStatusResultData(_WatsonxApiAgentExecutionResultBase):
    """API-facing provider_result payload returned when querying agent execution status."""
