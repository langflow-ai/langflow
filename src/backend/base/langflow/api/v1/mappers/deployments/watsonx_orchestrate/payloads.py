"""Watsonx deployment update payload models at API boundary."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class WatsonxApiUpdateToolReference(BaseModel):
    """Tool reference for Watsonx bind operations."""

    model_config = {"extra": "forbid"}

    flow_version_id: UUID


class WatsonxApiBindOperation(BaseModel):
    """Bind operation using a flow-version reference."""

    model_config = {"extra": "forbid"}

    op: Literal["bind"]
    tool: WatsonxApiUpdateToolReference
    app_ids: list[str] = Field(min_length=1)


class WatsonxApiUnbindOperation(BaseModel):
    """Unbind operation for an attached flow-version tool."""

    model_config = {"extra": "forbid"}

    op: Literal["unbind"]
    tool: WatsonxApiUpdateToolReference
    app_ids: list[str] = Field(min_length=1)


class WatsonxApiRemoveToolOperation(BaseModel):
    """Remove-tool operation for an attached flow-version tool."""

    model_config = {"extra": "forbid"}

    op: Literal["remove_tool"]
    tool: WatsonxApiUpdateToolReference


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


class WatsonxApiDeploymentUpdatePayload(BaseModel):
    """Watsonx provider_data API contract for deployment update operations."""

    model_config = {"extra": "forbid"}

    resource_name_prefix: str | None = None
    connections: WatsonxApiUpdateConnections = Field(default_factory=WatsonxApiUpdateConnections)
    operations: list[WatsonxApiUpdateOperation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_operation_references(self) -> WatsonxApiDeploymentUpdatePayload:
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

        for operation in self.operations:
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


class WatsonxApiToolAppBinding(BaseModel):
    """API response shape for a Watsonx tool binding."""

    model_config = {"extra": "forbid"}

    tool_id: str = Field(min_length=1)
    app_ids: list[str] = Field(default_factory=list)

    @field_validator("tool_id", mode="before")
    @classmethod
    def normalize_tool_id(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            msg = "tool_id cannot be empty"
            raise ValueError(msg)
        return normalized

    @field_validator("app_ids", mode="before")
    @classmethod
    def normalize_app_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(app_id).strip() for app_id in value if str(app_id).strip()]


class WatsonxApiDeploymentUpdateResultData(BaseModel):
    """Normalized provider-result payload used by Watsonx mapper update shapers."""

    model_config = {"extra": "ignore"}

    created_snapshot_ids: list[str] = Field(default_factory=list)
    tool_app_bindings: list[WatsonxApiToolAppBinding] | None = None

    @field_validator("created_snapshot_ids", mode="before")
    @classmethod
    def normalize_created_snapshot_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(snapshot_id).strip() for snapshot_id in value if str(snapshot_id).strip()]

    @classmethod
    def from_provider_result(cls, provider_result: Any) -> WatsonxApiDeploymentUpdateResultData:
        if not isinstance(provider_result, dict):
            return cls()
        return cls.model_validate(provider_result)

    def to_api_provider_data(self) -> dict[str, Any] | None:
        """Return API-safe provider_data subset for deployment update responses."""
        payload = self.model_dump(include={"tool_app_bindings"}, exclude_none=True)
        return payload or None
