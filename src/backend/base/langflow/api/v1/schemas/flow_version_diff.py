"""Pydantic schemas for the flow version comparison endpoint.

These live here rather than beside the ``FlowVersion`` table model so the diff
feature stays in files no schema migration touches.

``DiffFieldChange`` omits ``before``/``after`` entirely when ``redacted`` is set.
The diff engine leaves those keys unset rather than setting them to None, and the
endpoint serialises with ``response_model_exclude_unset=True``, so a withheld
value is absent from the payload while a field that genuinely changed *to* null
still reports an explicit null. ``exclude_none`` would collapse those two cases
into one and let a client mistake "hidden" for "cleared".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DiffSideRef(BaseModel):
    """Identifies one side of a comparison."""

    kind: Literal["version", "draft"]
    version_id: UUID | None = None
    version_number: int | None = None
    version_tag: str | None = None
    description: str | None = None
    created_at: datetime | None = None


class DiffSummary(BaseModel):
    """Counts describing the whole comparison.

    These stay exact even when per-node detail is truncated.
    """

    nodes_added: int = 0
    nodes_removed: int = 0
    nodes_modified: int = 0
    nodes_unchanged: int = 0
    edges_added: int = 0
    edges_removed: int = 0
    edges_unchanged: int = 0
    fields_changed: int = 0
    code_fields_changed: int = 0
    secrets_changed: int = Field(
        default=0,
        description="Changed fields whose values were withheld because the scrubber touched them.",
    )


class DiffNodeRef(BaseModel):
    """A bounded reference to a node — never the node payload itself."""

    id: str
    display_name: str | None = None
    component_type: str | None = None
    node_type: str | None = None


class DiffValueChange(BaseModel):
    """A before/after pair for a scalar node attribute."""

    before: str | None = None
    after: str | None = None


class DiffFieldChange(BaseModel):
    """One template field that differs between the two sides.

    ``before`` and ``after`` are absent whenever ``redacted`` is true. A redacted
    entry still reports that the field changed, which is the whole point: an
    operator can see that a credential moved without the diff disclosing it.
    """

    name: str
    display_name: str | None = None
    status: Literal["added", "removed", "modified"]
    redacted: bool = False
    before: Any | None = None
    after: Any | None = None
    before_truncated: bool = False
    after_truncated: bool = False


class DiffCodeChange(BaseModel):
    """Line-level changes to a component code field.

    ``unified_diff`` is rendered server-side so the client needs no diff library.
    It is None when the change is redacted or the field exceeded the size cap.
    """

    field_name: str
    display_name: str | None = None
    added_lines: int = 0
    removed_lines: int = 0
    unified_diff: str | None = None
    truncated: bool = False
    redacted: bool = False


class DiffNodeChange(DiffNodeRef):
    """A node present on both sides whose contents differ."""

    display_name_change: DiffValueChange | None = None
    field_changes: list[DiffFieldChange] = Field(default_factory=list)
    code_changes: list[DiffCodeChange] = Field(default_factory=list)
    other_changed_keys: list[str] = Field(
        default_factory=list,
        description="Dotted paths of node changes outside the template, e.g. 'data.node.outputs'.",
    )


class DiffEdgeRef(BaseModel):
    """A reference to an edge that was added or removed.

    Rewiring an edge changes its identity, so it surfaces as a removal plus an
    addition. There is no modified-edge state.
    """

    id: str
    source: str | None = None
    target: str | None = None
    source_handle_name: str | None = None
    target_handle_name: str | None = None


class DiffNodeGroups(BaseModel):
    """Added, removed and modified nodes."""

    added: list[DiffNodeRef] = Field(default_factory=list)
    removed: list[DiffNodeRef] = Field(default_factory=list)
    modified: list[DiffNodeChange] = Field(default_factory=list)


class DiffEdgeGroups(BaseModel):
    """Added and removed edges."""

    added: list[DiffEdgeRef] = Field(default_factory=list)
    removed: list[DiffEdgeRef] = Field(default_factory=list)


class FlowVersionDiffResponse(BaseModel):
    """The full comparison between two flow versions, or a version and the draft."""

    base: DiffSideRef
    target: DiffSideRef
    summary: DiffSummary
    nodes: DiffNodeGroups
    edges: DiffEdgeGroups
    identical: bool = False
    truncated: bool = Field(
        default=False,
        description="True when per-node detail was capped. Summary counts remain exact.",
    )


__all__ = [
    "DiffCodeChange",
    "DiffEdgeGroups",
    "DiffEdgeRef",
    "DiffFieldChange",
    "DiffNodeChange",
    "DiffNodeGroups",
    "DiffNodeRef",
    "DiffSideRef",
    "DiffSummary",
    "DiffValueChange",
    "FlowVersionDiffResponse",
]
