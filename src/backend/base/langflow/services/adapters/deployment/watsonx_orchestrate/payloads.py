"""Watsonx Orchestrate custom deployment update payload contracts."""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Literal

from lfx.services.adapters.deployment.schema import BaseFlowArtifact, EnvVarKey, EnvVarValueSpec, NormalizedId
from lfx.services.adapters.payload import AdapterPayload
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

RawToolName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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
    raw_payloads: list[BaseFlowArtifact] | None = Field(
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
    def validate_unique_raw_tool_names(self) -> WatsonxUpdateTools:
        raw_payloads = self.raw_payloads or []
        name_counts = Counter(payload.name for payload in raw_payloads)
        duplicates = sorted(name for name, count in name_counts.items() if count > 1)
        if duplicates:
            msg = f"tools.raw_payloads contains duplicate names: {duplicates}"
            raise ValueError(msg)
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
        collisions = sorted(existing_app_ids.intersection(raw_app_ids))
        if collisions:
            msg = f"connections.existing_app_ids collides with raw app ids from connections.raw_payloads: {collisions}"
            raise ValueError(msg)
        valid_app_ids = existing_app_ids.union(raw_app_ids)

        referenced_app_ids: set[str] = set()

        for operation in self.operations:
            if isinstance(operation, WatsonxBindOperation):
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
            if isinstance(operation, WatsonxUnbindOperation):
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

        unused_existing_app_ids = sorted(existing_app_ids.difference(referenced_app_ids))
        if unused_existing_app_ids:
            msg = f"connections.existing_app_ids contains ids not referenced by operations: {unused_existing_app_ids}"
            raise ValueError(msg)
        unused_raw_app_ids = sorted(raw_app_ids.difference(referenced_app_ids))
        if unused_raw_app_ids:
            msg = f"connections.raw_payloads contains app_id values not referenced by operations: {unused_raw_app_ids}"
            raise ValueError(msg)

        return self
