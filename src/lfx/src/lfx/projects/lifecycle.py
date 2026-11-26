"""Detached save records and the supported storage interface for project types.

Types are trusted Python, not sandboxed code. Contexts belong to one transaction
attempt. A type must never retain a context or perform external effects in a hook.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class ProjectConfigError(ValueError):
    """A safe, actionable configuration error, independent of any HTTP framework."""

    def __init__(self, message: str, *, field_path: str | None = None):
        super().__init__(message)
        self.field_path = field_path


class ProjectResourceUnavailableError(ProjectConfigError):
    """A source is absent or inaccessible; do not disclose which."""


class ProjectSaveConflictError(ProjectConfigError):
    """A resource changed after preparation read it."""


@dataclass(frozen=True)
class ProjectView:
    id: UUID
    name: str
    project_type: str
    config: dict | None


@dataclass(frozen=True)
class FlowSelector:
    id: UUID | None = None
    name: str | None = None

    def __post_init__(self):
        if (self.id is None) == (self.name is None) or self.name == "":
            msg = "Choose a flow ID or an unambiguous legacy name."
            raise ProjectConfigError(msg)


@dataclass(frozen=True)
class FlowView:
    id: UUID
    project_id: UUID | None
    name: str
    description: str
    data: dict
    is_component: bool
    flow_type: str
    locked: bool
    revision: str
    token: str

    def definition(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "data": deepcopy(self.data),
            "is_component": self.is_component,
        }


@dataclass(frozen=True)
class SourceVersionReference:
    flow_id: UUID
    version_id: UUID
    revision: str


@dataclass(frozen=True)
class SourceSnapshot:
    reference: SourceVersionReference
    data: dict


@dataclass(frozen=True)
class SaveRequest:
    project: ProjectView
    operation: Literal["create", "replace", "clear"]
    config: dict | None
    previous_config: dict | None
    flows: tuple[FlowView, ...] = ()


@dataclass(frozen=True)
class PreparedSave:
    config: dict | None
    target_flow_ids: tuple[UUID, ...] = ()
    state: object = None


@dataclass(frozen=True)
class CompositionContext:
    project: ProjectView
    flows: tuple[FlowView, ...]
    applied_values: dict[str, dict] = field(default_factory=dict)


@dataclass(frozen=True)
class FlowChange:
    flow_id: UUID
    token: str
    data: dict
    applied_values: dict = field(default_factory=dict)
    fields_skipped: int = 0


class ProjectSaveContext(Protocol):
    async def read_project(self, project_id: UUID, *, expected_type: str) -> ProjectView: ...

    async def read_flow(self, selector: FlowSelector, *, access: Literal["read", "execute"]) -> FlowView: ...

    async def pin_sources(self, tokens: tuple[str, ...], *, label: str) -> tuple[SourceSnapshot, ...]: ...

    async def read_saved_source(self, reference: SourceVersionReference) -> SourceSnapshot: ...
