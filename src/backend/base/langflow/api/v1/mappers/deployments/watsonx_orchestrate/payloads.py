"""Watsonx deployment payload models at API boundary."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from langflow.api.v1.mappers.deployments.contracts import CreateFlowArtifactProviderData
from langflow.services.adapters.deployment.watsonx_orchestrate.resource_name_prefix import (
    validate_resource_name_prefix_for_provider,
)

WatsonxApiResourceNamePrefix = Annotated[
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


class WatsonxApiFlowArtifactProviderData(CreateFlowArtifactProviderData):
    """Watsonx create-time flow artifact provider_data contract."""

    project_id: str = Field(min_length=1)


class WatsonxApiBindAppRef(BaseModel):
    """Connection selector used by API bind operations."""

    model_config = {"extra": "forbid"}

    app_id: str | None = Field(default=None, min_length=1)
    app_id_of_raw: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_exactly_one_selector(self) -> WatsonxApiBindAppRef:
        provided = [self.app_id is not None, self.app_id_of_raw is not None]
        if sum(provided) != 1:
            msg = "Exactly one of 'app_id' or 'app_id_of_raw' must be provided."
            raise ValueError(msg)
        return self

    @property
    def operation_app_id(self) -> str:
        return str(self.app_id or self.app_id_of_raw or "").strip()

    @property
    def is_raw(self) -> bool:
        return self.app_id_of_raw is not None

    @property
    def is_existing(self) -> bool:
        return self.app_id is not None


def _normalize_bind_app_refs(value: list[WatsonxApiBindAppRef]) -> list[WatsonxApiBindAppRef]:
    normalized: list[WatsonxApiBindAppRef] = []
    seen: set[tuple[str, str]] = set()
    selector_kind_by_app_id: dict[str, str] = {}
    for ref in value:
        selector_kind = "existing" if ref.app_id is not None else "raw" if ref.app_id_of_raw is not None else "unknown"
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


class WatsonxApiBindOperation(BaseModel):
    """Bind operation using a flow-version reference."""

    model_config = {"extra": "forbid"}

    op: Literal["bind"]
    flow_version_id: UUID
    app_refs: list[WatsonxApiBindAppRef] = Field(min_length=1)

    @field_validator("app_refs")
    @classmethod
    def dedupe_app_refs(cls, value: list[WatsonxApiBindAppRef]) -> list[WatsonxApiBindAppRef]:
        return _normalize_bind_app_refs(value)

    @property
    def app_ids(self) -> list[str]:
        return [app_ref.operation_app_id for app_ref in self.app_refs]

    @property
    def existing_app_ids(self) -> list[str]:
        return [app_ref.operation_app_id for app_ref in self.app_refs if app_ref.is_existing]


class WatsonxApiUnbindOperation(BaseModel):
    """Unbind operation for an attached flow-version tool."""

    model_config = {"extra": "forbid"}

    op: Literal["unbind"]
    flow_version_id: UUID
    app_ids: list[str] = Field(min_length=1)


class WatsonxApiRemoveToolOperation(BaseModel):
    """Remove-tool operation for an attached flow-version tool."""

    model_config = {"extra": "forbid"}

    op: Literal["remove_tool"]
    flow_version_id: UUID


WatsonxApiUpdateOperation = Annotated[
    WatsonxApiBindOperation | WatsonxApiUnbindOperation | WatsonxApiRemoveToolOperation,
    Field(discriminator="op"),
]


class WatsonxApiUpdateConnectionRawPayload(BaseModel):
    """Raw connection payload for app id."""

    model_config = {"extra": "forbid"}

    app_id: str = Field(min_length=1)
    environment_variables: dict[str, Any] | None = None
    provider_config: dict[str, Any] | None = None


class WatsonxApiUpdateConnections(BaseModel):
    """Connection declarations used by update operations."""

    model_config = {"extra": "forbid"}

    raw_payloads: list[WatsonxApiUpdateConnectionRawPayload] | None = None


def _collect_api_operation_reference_state(
    *,
    operations: list[Any],
) -> tuple[set[str], set[str]]:
    referenced_raw_app_ids: set[str] = set()
    unbind_app_ids: set[str] = set()

    for operation in operations:
        if isinstance(operation, WatsonxApiBindOperation):
            for app_ref in operation.app_refs:
                if app_ref.is_raw:
                    referenced_raw_app_ids.add(app_ref.operation_app_id)
            continue
        if isinstance(operation, WatsonxApiUnbindOperation):
            unbind_app_ids.update(operation.app_ids)

    return referenced_raw_app_ids, unbind_app_ids


def _collect_api_bind_existing_app_ids(
    *,
    operations: list[Any],
) -> set[str]:
    return {
        app_ref.operation_app_id
        for operation in operations
        if isinstance(operation, WatsonxApiBindOperation)
        for app_ref in operation.app_refs
        if app_ref.is_existing
    }


class WatsonxApiDeploymentPayloadBase(BaseModel):
    """Shared API payload fields/validation for Watsonx create and update operations."""

    model_config = {"extra": "forbid"}

    connections: WatsonxApiUpdateConnections = Field(default_factory=WatsonxApiUpdateConnections)

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxApiDeploymentPayloadBase:
        operations = list(getattr(self, "operations", []))
        raw_app_ids = {raw.app_id for raw in (self.connections.raw_payloads or [])}
        bind_existing_app_ids = _collect_api_bind_existing_app_ids(operations=operations)
        referenced_raw_app_ids, unbind_app_ids = _collect_api_operation_reference_state(
            operations=operations,
        )

        existing_raw_collisions = sorted(bind_existing_app_ids.intersection(raw_app_ids))
        if existing_raw_collisions:
            msg = (
                "bind app_id values must not overlap connections.raw_payloads[*].app_id; "
                "use app_id_of_raw for raw connections: "
                f"[{existing_raw_collisions[0]!r}]"
            )
            raise ValueError(msg)

        missing_raw_app_ids = sorted(referenced_raw_app_ids.difference(raw_app_ids))
        if missing_raw_app_ids:
            msg = (
                "bind operation app_id_of_raw must be declared in "
                "connections.raw_payloads[*].app_id: "
                f"[{missing_raw_app_ids[0]!r}]"
            )
            raise ValueError(msg)

        invalid_unbind_app_ids = sorted(unbind_app_ids.intersection(raw_app_ids))
        if invalid_unbind_app_ids:
            msg = f"unbind.operation app_ids must reference existing app ids only: [{invalid_unbind_app_ids[0]!r}]"
            raise ValueError(msg)

        unused_raw_app_ids = raw_app_ids.difference(referenced_raw_app_ids)
        if unused_raw_app_ids:
            msg = (
                "connections.raw_payloads contains app_id values not referenced by bind operation refs: "
                f"{list(unused_raw_app_ids)}"
            )
            raise ValueError(msg)
        return self


class WatsonxApiDeploymentUpdatePayload(WatsonxApiDeploymentPayloadBase):
    """Watsonx provider_data API contract for deployment update operations."""

    resource_name_prefix: WatsonxApiResourceNamePrefix | None = Field(
        default=None,
        description=("Provider-specific naming/deconfliction hint applied only when creating resources."),
    )
    operations: list[WatsonxApiUpdateOperation] = Field(min_length=1)

    @field_validator("resource_name_prefix")
    @classmethod
    def validate_resource_name_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        validate_resource_name_prefix_for_provider(value)
        return value


class WatsonxApiDeploymentCreatePayload(WatsonxApiDeploymentPayloadBase):
    """Watsonx provider_data API contract for deployment create operations."""

    resource_name_prefix: WatsonxApiResourceNamePrefix = Field(
        description=(
            "Provider-specific naming/deconfliction hint applied only when creating resources: "
            "applied to names of created tools and deployments."
        ),
    )
    operations: list[WatsonxApiBindOperation] = Field(min_length=1)

    @field_validator("resource_name_prefix")
    @classmethod
    def validate_resource_name_prefix(cls, value: str) -> str:
        validate_resource_name_prefix_for_provider(value)
        return value


class WatsonxApiToolAppBinding(BaseModel):
    """API response shape for a Watsonx tool binding."""

    model_config = {"extra": "forbid"}

    flow_version_id: UUID
    app_ids: list[str] = Field(default_factory=list)

    @field_validator("app_ids", mode="before")
    @classmethod
    def normalize_app_ids(cls, value: Any) -> list[str]:
        return _normalize_non_empty_str_list(value)


class WatsonxApiToolFlowVersionRef(BaseModel):
    """API response shape for flow-version to tool bindings."""

    model_config = {"extra": "forbid"}

    flow_version_id: UUID
    tool_id: str = Field(min_length=1)

    @field_validator("tool_id", mode="before")
    @classmethod
    def normalize_tool_id(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            msg = "tool_id must not be empty."
            raise ValueError(msg)
        return normalized


class WatsonxApiDeploymentCreateResultData(BaseModel):
    """Normalized provider-result payload used by Watsonx mapper create shaper."""

    model_config = {"extra": "ignore"}

    created_app_ids: list[str] = Field(default_factory=list)
    tools_with_flow_version_refs: list[WatsonxApiToolFlowVersionRef] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxApiToolAppBinding] = Field(default_factory=list)

    @field_validator("created_app_ids", mode="before")
    @classmethod
    def normalize_created_app_ids(cls, value: Any) -> list[str]:
        return _normalize_non_empty_str_list(value)

    def to_api_provider_data(self) -> dict[str, Any] | None:
        payload = self.model_dump(
            mode="json",
            include={"created_app_ids", "tools_with_flow_version_refs", "tool_app_bindings"},
            exclude_none=True,
        )
        return payload or None


class WatsonxApiDeploymentUpdateResultData(BaseModel):
    """Normalized provider-result payload used by Watsonx mapper update shapers."""

    model_config = {"extra": "ignore"}

    created_app_ids: list[str] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxApiToolAppBinding] | None = None

    @field_validator("created_app_ids", mode="before")
    @classmethod
    def normalize_created_app_ids(cls, value: Any) -> list[str]:
        return _normalize_non_empty_str_list(value)

    @classmethod
    def from_provider_result(cls, provider_result: Any) -> WatsonxApiDeploymentUpdateResultData:
        if not isinstance(provider_result, dict):
            return cls()
        return cls.model_validate(provider_result)

    def to_api_provider_data(self) -> dict[str, Any] | None:
        """Return API-safe provider_data subset for deployment update responses."""
        payload = self.model_dump(mode="json", include={"created_app_ids", "tool_app_bindings"}, exclude_none=True)
        return payload or None


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
