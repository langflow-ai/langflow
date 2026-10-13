"""Metadata and lazy composition factories declared by installed project types."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.projects.archives import ProjectComposition
    from lfx.projects.schema import ProjectTypeDefinition


@dataclass(frozen=True)
class ProjectStarter:
    name: str
    display_name: str
    description: str
    build: Callable[[], ProjectComposition]

    def __post_init__(self):
        if not isinstance(self.name, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", self.name):
            msg = "Project starters need a lowercase slug."
            raise ValueError(msg)
        if any(not isinstance(value, str) or not value.strip() for value in (self.display_name, self.description)):
            msg = "Project starters need a display name and description."
            raise ValueError(msg)
        if not callable(self.build) or inspect.iscoroutinefunction(self.build):
            msg = "Project starters need a synchronous composition factory."
            raise TypeError(msg)

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "display_name": self.display_name, "description": self.description}


def project_starters() -> tuple[tuple[ProjectTypeDefinition, ProjectStarter], ...]:
    """List factories without executing them; reject ambiguous global route names."""
    from lfx.projects.registry import all_project_types

    result = []
    names = set()
    for definition in all_project_types():
        starters = definition.starters()
        if not isinstance(starters, tuple) or any(not isinstance(item, ProjectStarter) for item in starters):
            msg = f"Project type {definition.name!r} must return a tuple of ProjectStarter declarations."
            raise TypeError(msg)
        for starter in starters:
            if starter.name in names:
                msg = f"Project starter {starter.name!r} is declared more than once."
                raise ValueError(msg)
            names.add(starter.name)
            result.append((definition, starter))
    return tuple(result)


def get_project_starter(name: str) -> tuple[ProjectTypeDefinition, ProjectStarter]:
    for definition, starter in project_starters():
        if starter.name == name:
            return definition, starter
    msg = "Project starter not found."
    raise LookupError(msg)


def build_project_starter(definition: ProjectTypeDefinition, starter: ProjectStarter) -> ProjectComposition:
    """Validate the factory result before the host creates any resources."""
    from lfx.projects.archives import CompositionGraph, ProjectComposition

    result = starter.build()
    if not isinstance(result, ProjectComposition):
        msg = "A project starter must build a ProjectComposition."
        raise TypeError(msg)
    graph = CompositionGraph(result)
    if graph.projects[str(result.root_project_id)].project_type != definition.name:
        msg = "A project starter's root must have its declaring project type."
        raise ValueError(msg)
    graph.validate(allow_missing_secrets=True)
    return result
