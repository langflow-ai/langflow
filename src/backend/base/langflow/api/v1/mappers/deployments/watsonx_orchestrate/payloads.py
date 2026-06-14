"""Watsonx deployment payload models at API boundary."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import UUID

from lfx.services.adapters.deployment.schema import DeploymentType
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from langflow.api.v1.schemas.deployments import ValidatedUrl
from langflow.services.database.models.deployment_provider_account.utils import validate_provider_url

if TYPE_CHECKING:
    from langflow.api.v1.schemas.deployments import DeploymentCreateRequest

# Keep API-boundary scalar normalization local to this module instead of
# importing adapter-layer aliases, so mapper contracts can evolve independently.
NormalizedStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


def _validate_non_empty_string(value: str) -> str:
    if not value.strip():
        msg = "String must not be empty."
        raise ValueError(msg)
    return value


NonEmptyString = Annotated[str, AfterValidator(_validate_non_empty_string)]


class WatsonxApiProviderAccountCreate(BaseModel):
    """WXO provider-account provider_data contract at API boundary.

    This schema is owned by the WXO mapper and parsed once to validate the
    provider-account provider_data payload before URL policy checks, credential
    verification payload shaping, and DB field extraction.
    """

    model_config = {"extra": "forbid"}

    url: ValidatedUrl
    tenant_id: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1)] = None
    api_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WatsonxApiProviderAccountUpdate(BaseModel):
    """WXO mutable provider-account fields for update requests.

    Only credential rotation is supported after create. URL and tenant are
    immutable and therefore intentionally absent from this schema.
    """

    model_config = {"extra": "forbid"}

    api_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WatsonxApiProviderAccountResponse(BaseModel):
    """WXO provider-account provider_data contract for API responses."""

    model_config = {"extra": "forbid"}

    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    tenant_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

    @field_validator("url")
    @classmethod
    def validate_url_without_rewriting(cls, value: str) -> str:
        # Validate URL policy but preserve stored representation.
        validate_provider_url(value, field_name="url")
        return value


class WatsonxApiAddFlowItem(BaseModel):
    """Create-time flow item (tool is created/attached if absent)."""

    model_config = {"extra": "forbid"}

    flow_version_id: UUID
    app_ids: list[NormalizedStr] = Field(
        default_factory=list,
        description=(
            "Connection app ids to bind. Use an empty list to create/attach "
            "the flow version as a tool with no connection bindings."
        ),
    )
    tool_display_name: NormalizedStr | None = Field(
        default=None,
        description=("Optional user-provided tool label. When omitted, the label is derived from the flow name."),
    )


class WatsonxApiUpsertFlowItem(BaseModel):
    """Update-time flow item with per-item add/remove app-id deltas."""

    model_config = {"extra": "forbid"}

    flow_version_id: UUID
    add_app_ids: list[NormalizedStr] = Field(
        default_factory=list,
        description=("Connection app ids to bind. Use an empty list to avoid adding new bindings."),
    )
    remove_app_ids: list[NormalizedStr] = Field(
        default_factory=list,
        description=("Connection app ids to unbind. Use an empty list to avoid removing bindings."),
    )
    tool_display_name: NormalizedStr | None = Field(
        default=None,
        description=("Optional user-provided tool label. When omitted, the label is derived from the flow name."),
    )


class WatsonxApiCreateUpsertToolItem(BaseModel):
    """Create-time existing provider tool item (add connections only)."""

    model_config = {"extra": "forbid"}

    tool_id: NormalizedStr = Field(description="Provider-owned tool identifier.")
    add_app_ids: list[NormalizedStr] = Field(
        default_factory=list,
        description=("Connection app ids to bind. Use an empty list to attach the tool without connection bindings."),
    )


class WatsonxApiUpsertToolItem(BaseModel):
    """Update-time existing provider tool item with per-item add/remove app-id deltas."""

    model_config = {"extra": "forbid"}

    tool_id: NormalizedStr = Field(description="Provider-owned tool identifier.")
    add_app_ids: list[NormalizedStr] = Field(
        default_factory=list,
        description=("Connection app ids to bind. Use an empty list to avoid adding new bindings."),
    )
    remove_app_ids: list[NormalizedStr] = Field(
        default_factory=list,
        description=("Connection app ids to unbind. Use an empty list to avoid removing bindings."),
    )


class WatsonxApiConnectionCredentialItem(BaseModel):
    """API-facing connection credential declaration."""

    model_config = {"extra": "forbid"}

    key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    source: Literal["raw", "variable"] = "variable"


class WatsonxApiKeyValueConnectionPayload(BaseModel):
    """API-facing key-value connection payload for app id.

    Today this API only accepts key-value connections, so ``connections`` is a
    flat list of this payload shape with no explicit ``type`` discriminator.
    When additional connection types are introduced, a ``type`` field can be
    added with a default of ``"key_value"`` for backward compatibility.
    """

    model_config = {"extra": "forbid"}

    app_id: NormalizedStr
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


def _collect_api_referenced_app_ids(operations: list[Any], *, attr_name: str = "app_ids") -> set[str]:
    referenced_app_ids: set[str] = set()
    for operation in operations:
        operation_app_ids = getattr(operation, attr_name, None)
        if not operation_app_ids:
            continue
        referenced_app_ids.update(operation_app_ids)
    return referenced_app_ids


def _validate_api_remove_not_raw(*, operations: list[Any], raw_app_ids: set[str], attr_name: str, label: str) -> None:
    for operation in operations:
        remove_app_ids = getattr(operation, attr_name, None)
        if not remove_app_ids:
            continue
        invalid_raw = sorted(raw_app_ids.intersection(set(remove_app_ids)))
        if invalid_raw:
            msg = f"{label} must not reference connections app_ids: {invalid_raw}"
            raise ValueError(msg)


def _validate_api_add_remove_overlap(*, operations: list[Any], label: str) -> None:
    for operation in operations:
        add_app_ids = set(getattr(operation, "add_app_ids", []) or [])
        remove_app_ids = set(getattr(operation, "remove_app_ids", []) or [])
        overlap = sorted(add_app_ids.intersection(remove_app_ids))
        if overlap:
            msg = f"{label} add_app_ids and remove_app_ids must not overlap: {overlap}"
            raise ValueError(msg)


def _validate_api_remove_conflicts(
    *,
    remove_ids: list[Any],
    upsert_operations: list[Any],
    remove_label: str,
    upsert_attr_name: str,
) -> None:
    normalized_remove_ids = {str(remove_id).strip() for remove_id in remove_ids if str(remove_id).strip()}
    normalized_upsert_ids = {
        str(getattr(operation, upsert_attr_name, "")).strip()
        for operation in upsert_operations
        if str(getattr(operation, upsert_attr_name, "")).strip()
    }
    conflicts = sorted(normalized_remove_ids.intersection(normalized_upsert_ids))
    if conflicts:
        msg = f"{remove_label} cannot be combined with upsert for the same id: {conflicts}"
        raise ValueError(msg)


def _validate_api_unused_raw_app_ids(*, raw_app_ids: set[str], referenced_app_ids: set[str]) -> None:
    unused_raw_app_ids = sorted(raw_app_ids.difference(referenced_app_ids))
    if unused_raw_app_ids:
        msg = f"connections contains app_id values not referenced by operations: {unused_raw_app_ids}"
        raise ValueError(msg)


def _validate_api_unique_connection_app_ids(*, connections: list[WatsonxApiKeyValueConnectionPayload]) -> None:
    app_id_counts = Counter(connection.app_id for connection in connections)
    duplicates = sorted(app_id for app_id, count in app_id_counts.items() if count > 1)
    if duplicates:
        msg = f"connections contains duplicate app_id values: {duplicates}"
        raise ValueError(msg)


class WatsonxApiDeploymentUpdatePayload(BaseModel):
    """Watsonx provider_data API contract for deployment update operations.

    All operation fields default to empty lists so LLM-only updates
    (changing the model without any tool/connection changes) can be
    expressed without providing operation entries.
    """

    model_config = {"extra": "forbid"}

    display_name: NormalizedStr | None = Field(
        default=None,
        description="Optional user-facing label to set on the wxO agent.",
    )
    llm: NormalizedStr | None = Field(
        default=None,
        description=(
            "Optional provider model identifier to use for the deployment agent. "
            "When omitted, the current model is preserved."
        ),
    )
    connections: list[WatsonxApiKeyValueConnectionPayload] = Field(default_factory=list)
    upsert_flows: list[WatsonxApiUpsertFlowItem] = Field(default_factory=list)
    upsert_tools: list[WatsonxApiUpsertToolItem] = Field(default_factory=list)
    remove_flows: list[UUID] = Field(default_factory=list)
    remove_tools: list[NormalizedStr] = Field(default_factory=list)

    @field_validator("display_name", "llm", mode="before")
    @classmethod
    def reject_null_optional_strings(cls, value: Any, info: ValidationInfo) -> Any:
        if value is None:
            msg = f"{info.field_name} cannot be set to null."
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxApiDeploymentUpdatePayload:
        _validate_api_unique_connection_app_ids(connections=self.connections)
        raw_app_ids = {raw.app_id for raw in self.connections}
        referenced_app_ids = _collect_api_referenced_app_ids(self.upsert_flows, attr_name="add_app_ids")
        referenced_app_ids.update(_collect_api_referenced_app_ids(self.upsert_tools, attr_name="add_app_ids"))
        _validate_api_remove_not_raw(
            operations=self.upsert_flows,
            raw_app_ids=raw_app_ids,
            attr_name="remove_app_ids",
            label="upsert_flows.remove_app_ids",
        )
        _validate_api_remove_not_raw(
            operations=self.upsert_tools,
            raw_app_ids=raw_app_ids,
            attr_name="remove_app_ids",
            label="upsert_tools.remove_app_ids",
        )
        _validate_api_add_remove_overlap(operations=self.upsert_flows, label="upsert_flows")
        _validate_api_add_remove_overlap(operations=self.upsert_tools, label="upsert_tools")
        _validate_api_remove_conflicts(
            remove_ids=self.remove_flows,
            upsert_operations=self.upsert_flows,
            remove_label="remove_flows",
            upsert_attr_name="flow_version_id",
        )
        _validate_api_remove_conflicts(
            remove_ids=self.remove_tools,
            upsert_operations=self.upsert_tools,
            remove_label="remove_tools",
            upsert_attr_name="tool_id",
        )
        _validate_api_unused_raw_app_ids(raw_app_ids=raw_app_ids, referenced_app_ids=referenced_app_ids)
        return self


class WatsonxApiDeploymentCreatePayload(BaseModel):
    """Watsonx provider_data API contract for deployment create operations."""

    model_config = {"extra": "forbid"}

    display_name: NormalizedStr | None = Field(
        default=None,
        description=(
            "User-facing label to set on a new wxO agent. "
            "Required unless tracking an existing wxO agent in Langflow (via ``existing_agent_id`` field)."
        ),
    )
    llm: NormalizedStr | None = Field(
        default=None,
        description=(
            "Provider model identifier to use for a new wxO agent."
            "Required unless tracking an existing wxO agent in Langflow (via ``existing_agent_id`` field)."
        ),
    )
    connections: list[WatsonxApiKeyValueConnectionPayload] = Field(default_factory=list)
    add_flows: list[WatsonxApiAddFlowItem] = Field(default_factory=list)
    upsert_tools: list[WatsonxApiCreateUpsertToolItem] = Field(default_factory=list)
    existing_agent_id: NormalizedStr | None = Field(
        default=None,
        description=(
            "Provider-owned agent id to track in Langflow instead of creating a new wxO agent. "
            "When provided, the request must not include fields that would update the wxO agent."
        ),
    )

    @model_validator(mode="after")
    def validate_create_operation_requirements(self) -> WatsonxApiDeploymentCreatePayload:
        if "existing_agent_id" in self.model_fields_set:
            if self.existing_agent_id is None:
                msg = "provider_data.existing_agent_id cannot be set to null."
                raise ValueError(msg)
            if len(self.model_fields_set) > 1:
                msg = (
                    "existing_agent_id is only for tracking existing wxO agents in Langflow and cannot include "
                    "fields that update the wxO agent. Update the deployment after it is tracked."
                )
                raise ValueError(msg)
            return self
        if self.display_name is None:
            msg = "provider_data.display_name is required for new agent creation."
            raise ValueError(msg)
        if self.llm is None:
            msg = "provider_data.llm is required for new agent creation."
            raise ValueError(msg)
        # TODO: Allow wxO agent creation without initial flows/tools once the adapter create path supports it.
        if not (self.add_flows or self.upsert_tools):
            msg = "provider_data must include at least one add_flows or upsert_tools item for new agent creation."
            raise ValueError(msg)
        _validate_api_unique_connection_app_ids(connections=self.connections)
        raw_app_ids = {raw.app_id for raw in self.connections}
        referenced_app_ids = _collect_api_referenced_app_ids(self.add_flows, attr_name="app_ids")
        referenced_app_ids.update(_collect_api_referenced_app_ids(self.upsert_tools, attr_name="add_app_ids"))
        _validate_api_unused_raw_app_ids(raw_app_ids=raw_app_ids, referenced_app_ids=referenced_app_ids)
        return self

    def validate_with_outer_fields(self, outer_payload: DeploymentCreateRequest) -> None:
        if self.existing_agent_id is None or "description" not in outer_payload.model_fields_set:
            return
        msg = "When existing_agent_id is provided, Langflow uses the description already set for the agent in wxO."
        raise ValueError(msg)


class WatsonxApiCreatedTool(BaseModel):
    """API response shape for a tool created from a Langflow flow version."""

    model_config = {"extra": "forbid"}

    flow_version_id: UUID
    tool_id: NonEmptyString = Field(description="Provider-owned tool identifier.")

    @field_validator("flow_version_id", mode="before")
    @classmethod
    def normalize_flow_version_id(cls, value: Any) -> UUID:
        if isinstance(value, UUID):
            return value
        if not isinstance(value, str):
            msg = "flow_version_id must be provided as a UUID string or UUID object."
            raise ValueError(msg)  # noqa: TRY004
        try:
            return UUID(value)
        except ValueError as exc:
            msg = "flow_version_id must be a valid UUID."
            raise ValueError(msg) from exc


class WatsonxApiDeploymentCreateResultData(BaseModel):
    """Provider-result payload used by Watsonx mapper create shapers."""

    model_config = {"extra": "ignore"}

    name: NonEmptyString = Field(description="Provider technical agent name.")
    display_name: NonEmptyString
    created_app_ids: list[NonEmptyString] = Field(default_factory=list)
    created_tools: list[WatsonxApiCreatedTool] = Field(default_factory=list)

    @classmethod
    def from_provider_result(cls, provider_result: Any) -> WatsonxApiDeploymentCreateResultData:
        return cls.model_validate(provider_result)


class WatsonxApiDeploymentUpdateResultData(BaseModel):
    """Provider-result payload used by Watsonx mapper update shapers."""

    model_config = {"extra": "ignore"}

    name: NonEmptyString = Field(description="Provider technical agent name.")
    display_name: NonEmptyString
    created_app_ids: list[NonEmptyString] = Field(default_factory=list)
    created_tools: list[WatsonxApiCreatedTool] = Field(default_factory=list)

    @classmethod
    def from_provider_result(cls, provider_result: Any) -> WatsonxApiDeploymentUpdateResultData:
        return cls.model_validate(provider_result)


class WatsonxApiModelOut(BaseModel):
    """Minimal API-boundary model metadata needed for deployment LLM listing."""

    model_config = {"extra": "ignore"}

    model_name: NonEmptyString


class WatsonxApiDeploymentLlmListResultData(BaseModel):
    """API-boundary payload used by mapper LLM-list response shaping."""

    model_config = {"extra": "forbid"}

    models: list[WatsonxApiModelOut] = Field(default_factory=list)


class WatsonxApiProviderDeploymentListItem(BaseModel):
    """Provider-only deployment item returned in list provider_data."""

    model_config = {"extra": "forbid"}

    id: NonEmptyString = Field(description="Provider-owned deployment identifier.")
    name: NonEmptyString
    display_name: NonEmptyString
    type: DeploymentType
    description: str
    created_at: datetime
    updated_at: datetime
    tool_ids: list[NonEmptyString] = Field(default_factory=list)
    llm: NonEmptyString
    environments: list[NonEmptyString] = Field(default_factory=list)


class WatsonxApiDeploymentListItemProviderData(BaseModel):
    """Per-item provider_data surfaced on synced wxO deployment list rows."""

    model_config = {"extra": "forbid"}

    name: NonEmptyString
    display_name: NonEmptyString
    llm: NonEmptyString
    environments: list[NonEmptyString]


class WatsonxApiDeploymentGetProviderData(BaseModel):
    """Provider_data surfaced on wxO deployment detail responses."""

    model_config = {"extra": "forbid"}

    llm: NonEmptyString
    name: NonEmptyString
    display_name: NonEmptyString
    environments: list[NonEmptyString]


class WatsonxApiDeploymentListProviderData(BaseModel):
    """Provider-level metadata attached to DeploymentListResponse.provider_data."""

    deployments: list[WatsonxApiProviderDeploymentListItem] = Field(default_factory=list)


class WatsonxApiConfigListItem(BaseModel):
    """API-facing config list item payload under config-list provider_data."""

    model_config = {"extra": "forbid"}

    connection_id: NonEmptyString
    app_id: NonEmptyString
    type: NonEmptyString
    environment: NonEmptyString


class WatsonxApiConfigListProviderData(BaseModel):
    """Provider-level metadata attached to DeploymentConfigListResponse."""

    model_config = {"extra": "forbid"}

    connections: list[WatsonxApiConfigListItem] = Field(default_factory=list)
    page: int | None = Field(default=None, ge=1)
    size: int | None = Field(default=None, ge=1)
    total: int | None = Field(default=None, ge=0)


class WatsonxApiSnapshotListItem(BaseModel):
    """API-facing snapshot list item payload under snapshot-list provider_data."""

    model_config = {"extra": "forbid"}

    id: NonEmptyString
    name: NonEmptyString
    display_name: NonEmptyString
    connections: dict[NonEmptyString, NonEmptyString] = Field(default_factory=dict)


class WatsonxApiSnapshotListProviderData(BaseModel):
    """Provider-level metadata attached to DeploymentSnapshotListResponse."""

    model_config = {"extra": "forbid"}

    tools: list[WatsonxApiSnapshotListItem] = Field(default_factory=list)
    page: int | None = Field(default=None, ge=1)
    size: int | None = Field(default=None, ge=1)
    total: int | None = Field(default=None, ge=0)


class WatsonxApiDeploymentFlowVersionItemData(BaseModel):
    """API-facing provider_data contract for deployment flow-version list items.

    ``tool_name`` is the provider technical name, while ``tool_display_name`` is
    the user-facing label. Missing or blank values indicate corrupt provider
    data and the mapper intentionally rejects them with a 500 so the issue
    surfaces immediately.
    """

    model_config = {"extra": "forbid"}

    app_ids: list[NonEmptyString] = Field(default_factory=list)
    tool_name: NonEmptyString
    tool_display_name: NonEmptyString


class WatsonxApiExecutionInput(BaseModel):
    """API-facing provider_data payload for POST deployment runs."""

    model_config = {"extra": "forbid"}

    input: str | None = None
    message: dict[str, Any] | None = None
    thread_id: str | None = None

    @model_validator(mode="after")
    def validate_input_or_message_exclusive(self) -> WatsonxApiExecutionInput:
        has_input = self.input is not None
        has_message = self.message is not None
        if has_input == has_message:
            msg = "provider_data must include exactly one of 'input' or 'message'."
            raise ValueError(msg)
        return self


class _WatsonxApiAgentExecutionResultBase(BaseModel):
    """Shared fields for API-facing agent execution result payloads.

    All provider-owned identifiers and metadata live here inside
    ``provider_data``.  The enclosing response only carries Langflow-owned
    fields (``deployment_id``).  ``deployment_id`` (Langflow DB UUID) is
    intentionally omitted from this schema to avoid ownership confusion.
    """

    model_config = {"extra": "allow"}

    id: NonEmptyString | None = None
    agent_id: NonEmptyString | None = None
    thread_id: NonEmptyString | None = None
    status: str | None = None
    result: Any | None = None
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    cancelled_at: str | None = None
    last_error: str | None = None

    @classmethod
    def from_provider_result(cls, provider_result: Any) -> _WatsonxApiAgentExecutionResultBase:
        if not isinstance(provider_result, dict):
            return cls()
        return cls.model_validate(provider_result)


class WatsonxApiAgentExecutionCreateResultData(_WatsonxApiAgentExecutionResultBase):
    """API-facing provider_result payload returned when an agent execution is created."""


class WatsonxApiAgentExecutionStatusResultData(_WatsonxApiAgentExecutionResultBase):
    """API-facing provider_result payload returned when querying agent execution status."""
