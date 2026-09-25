"""Registry of project types.

Same shape as the vector-store backend registry: a module-level dict, free functions, no
lock and no reload path. A project type is registered once on import and then read.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.projects.schema import ProjectType

_PROJECT_TYPES: dict[str, ProjectType] = {}


def register_project_type(project_type: ProjectType) -> ProjectType:
    """Register ``project_type`` under its name, and return it.

    Idempotent for the identical object; re-registering a different type under a name that is
    taken raises ``ValueError`` rather than silently shadowing it. The return value lets a
    caller bind the registered object in one statement.
    """
    existing = _PROJECT_TYPES.get(project_type.name)
    if existing is not None and existing is not project_type:
        msg = (
            f"Project type {project_type.name!r} is already registered as "
            f"{existing.display_name!r}; refusing to overwrite it."
        )
        raise ValueError(msg)
    _PROJECT_TYPES[project_type.name] = project_type
    return project_type


def get_project_type(name: str) -> ProjectType:
    """Look up a registered project type by name."""
    try:
        return _PROJECT_TYPES[name]
    except KeyError as exc:
        available = ", ".join(registered_project_types()) or "<none>"
        msg = f"Project type {name!r} is not registered. Registered types: {available}."
        raise ValueError(msg) from exc


def registered_project_types() -> tuple[str, ...]:
    """Every registered project type name, in a stable order."""
    return tuple(sorted(_PROJECT_TYPES))


def all_project_types() -> tuple[ProjectType, ...]:
    """Every registered project type, in the same stable order."""
    return tuple(_PROJECT_TYPES[name] for name in registered_project_types())
