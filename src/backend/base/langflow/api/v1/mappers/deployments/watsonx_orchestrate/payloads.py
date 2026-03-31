"""Watsonx deployment payload models at API boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from lfx.services.adapters.deployment.schema import DeploymentType
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


class WatsonxApiFlowArtifactProviderData(CreateFlowArtifactProviderData):
    """Watsonx create-time flow artifact provider_data contract."""

    project_id: str = Field(min_length=1)


class WatsonxApiBindOperation(BaseModel):
    """Bind operation using a flow-version reference."""

    model_config = {"extra": "forbid"}

    op: Literal["bind"]
    flow_version_id: UUID
    app_ids: list[str] = Field(min_length=1)


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

    existing_app_ids: list[str] | None = None
    raw_payloads: list[WatsonxApiUpdateConnectionRawPayload] | None = None


class WatsonxApiDeploymentPayloadBase(BaseModel):
    """Shared API payload fields/validation for Watsonx create and update operations."""

    model_config = {"extra": "forbid"}

    connections: WatsonxApiUpdateConnections = Field(default_factory=WatsonxApiUpdateConnections)

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxApiDeploymentPayloadBase:
        existing_app_ids = set(self.connections.existing_app_ids or [])
        raw_app_ids = {raw.app_id for raw in (self.connections.raw_payloads or [])}
        collisions = existing_app_ids.intersection(raw_app_ids)
        if collisions:
            msg = (
                "connections.existing_app_ids collides with raw app ids from connections.raw_payloads: "
                f"{list(collisions)}"
            )
            raise ValueError(msg)

        valid_app_ids = existing_app_ids.union(raw_app_ids)
        referenced_app_ids: set[str] = set()

        for operation in getattr(self, "operations", []):
            if isinstance(operation, (WatsonxApiBindOperation, WatsonxApiUnbindOperation)):
                for app_id in operation.app_ids:
                    referenced_app_ids.add(app_id)
                    if app_id not in valid_app_ids:
                        msg = (
                            "operation app_ids must be declared in "
                            "connections.existing_app_ids or connections.raw_payloads[*].app_id: "
                            f"[{app_id!r}]"
                        )
                        raise ValueError(msg)
            if isinstance(operation, WatsonxApiUnbindOperation):
                for app_id in operation.app_ids:
                    if app_id in raw_app_ids:
                        msg = f"unbind.operation app_ids must reference connections.existing_app_ids only: [{app_id!r}]"
                        raise ValueError(msg)

        unused_existing_app_ids = existing_app_ids.difference(referenced_app_ids)
        if unused_existing_app_ids:
            msg = (
                "connections.existing_app_ids contains ids not referenced by operations: "
                f"{list(unused_existing_app_ids)}"
            )
            raise ValueError(msg)
        unused_raw_app_ids = raw_app_ids.difference(referenced_app_ids)
        if unused_raw_app_ids:
            msg = (
                "connections.raw_payloads contains app_id values not referenced by operations: "
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

    resource_name_prefix: WatsonxApiResourceNamePrefix | None = Field(
        default=None,
        description=(
            "Provider-specific naming/deconfliction hint applied only when creating resources: "
            "applied to names of created tools and deployments."
        ),
    )
    operations: list[WatsonxApiBindOperation] = Field(default_factory=list)
    existing_agent_id: str | None = Field(
        default=None,
        description=(
            "Provider-owned agent id to update/reuse instead of creating a new agent. "
            "When provided, operations are optional and may be empty for DB-only onboarding."
        ),
    )

    @field_validator("resource_name_prefix")
    @classmethod
    def validate_resource_name_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        validate_resource_name_prefix_for_provider(value)
        return value

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
        has_raw_connections = bool(self.connections.raw_payloads)
        if (has_operations or has_raw_connections) and self.resource_name_prefix is None:
            msg = "resource_name_prefix is required when operations or connections.raw_payloads are provided."
            raise ValueError(msg)
        if self.existing_agent_id is None and not has_operations:
            msg = "operations must include at least one bind operation for new agent creation."
            raise ValueError(msg)
        return self


class WatsonxApiToolAppBinding(BaseModel):
    """API response shape for a Watsonx tool binding."""

    model_config = {"extra": "forbid"}

    flow_version_id: UUID
    app_ids: list[str] = Field(default_factory=list)

    @field_validator("app_ids", mode="before")
    @classmethod
    def normalize_app_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(app_id).strip() for app_id in value if str(app_id).strip()]


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


class WatsonxApiProviderDeploymentListItem(BaseModel):
    """Provider-only deployment item returned in list provider_data."""

    resource_key: str = Field(min_length=1, description="Provider-owned deployment identifier.")
    name: str
    type: DeploymentType
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_data: dict[str, Any] | None = None


class WatsonxApiDeploymentListProviderData(BaseModel):
    """Provider-level metadata attached to DeploymentListResponse.provider_data."""

    entries: list[WatsonxApiProviderDeploymentListItem] = Field(default_factory=list)


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
