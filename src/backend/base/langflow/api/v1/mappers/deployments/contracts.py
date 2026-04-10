"""Adapter-agnostic deployment mapper reconciliation contracts."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


class CreateFlowArtifactProviderData(BaseModel):
    """Baseline provider_data contract for create-time flow artifacts.

    Provider mappers may extend this shape via explicit subclass schemas.
    """

    model_config = ConfigDict(extra="forbid")

    source_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CreateSnapshotBinding(BaseModel):
    """Baseline create-time snapshot binding contract."""

    source_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    snapshot_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CreateSnapshotBindings(BaseModel):
    """Normalized create-time bindings collection."""

    snapshot_bindings: list[CreateSnapshotBinding] = Field(default_factory=list)

    def to_source_ref_map(self) -> dict[str, str]:
        return {binding.source_ref: binding.snapshot_id for binding in self.snapshot_bindings}


class UpdateSnapshotBinding(BaseModel):
    """Normalized update-time snapshot binding contract."""

    source_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    snapshot_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class UpdateSnapshotBindings(BaseModel):
    """Normalized update-time binding collection."""

    snapshot_bindings: list[UpdateSnapshotBinding] = Field(default_factory=list)

    def to_source_ref_map(self) -> dict[str, str]:
        return {binding.source_ref: binding.snapshot_id for binding in self.snapshot_bindings}


class CreatedSnapshotIds(BaseModel):
    """Normalized created snapshot ids emitted by mapper reconciliation."""

    ids: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]] = Field(default_factory=list)


class FlowVersionPatch(BaseModel):
    """Normalized add/remove patch used by attachment reconciliation."""

    add_flow_version_ids: list[UUID] = Field(default_factory=list)
    remove_flow_version_ids: list[UUID] = Field(default_factory=list)

    @field_validator("add_flow_version_ids", "remove_flow_version_ids")
    @classmethod
    def _dedupe_ids(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def _validate_no_overlap(self) -> FlowVersionPatch:
        overlap = set(self.add_flow_version_ids).intersection(self.remove_flow_version_ids)
        if overlap:
            ids = ", ".join(sorted(str(value) for value in overlap))
            msg = f"Flow version ids cannot be present in both add/remove operations: {ids}."
            raise ValueError(msg)
        return self
