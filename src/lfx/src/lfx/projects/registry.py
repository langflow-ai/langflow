"""Registries of project types and reusable flow contracts.

Same shape as the vector-store backend registry: a module-level dict, free functions, no
lock and no reload path. A project type is registered once on import and then read.
"""

from __future__ import annotations

from lfx.projects.schema import ProjectType, SlotDefinition

_PROJECT_TYPES: dict[str, ProjectType] = {}
_SLOT_DEFINITIONS: dict[str, SlotDefinition] = {}


def register_slot(slot_definition: SlotDefinition) -> SlotDefinition:
    """Register a contract before a project type uses it. Refuse conflicting definitions."""
    if not isinstance(slot_definition, SlotDefinition):
        msg = "Register a SlotDefinition instance, not a name reference."
        raise TypeError(msg)
    existing = _SLOT_DEFINITIONS.get(slot_definition.name)
    if existing is not None and existing is not slot_definition:
        msg = f"Slot {slot_definition.name!r} is already registered; refusing to overwrite it."
        raise ValueError(msg)
    _SLOT_DEFINITIONS[slot_definition.name] = slot_definition
    return slot_definition


def get_slot(name: str) -> SlotDefinition:
    """Look up a registered contract without loading any components."""
    try:
        return _SLOT_DEFINITIONS[name]
    except KeyError as exc:
        available = ", ".join(registered_slots()) or "<none>"
        msg = f"Slot {name!r} is not registered. Registered slots: {available}."
        raise ValueError(msg) from exc


def registered_slots() -> tuple[str, ...]:
    return tuple(sorted(_SLOT_DEFINITIONS))


def all_slots() -> tuple[SlotDefinition, ...]:
    return tuple(_SLOT_DEFINITIONS[name] for name in registered_slots())


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

    names: set[str] = set()
    for field in project_type.fields:
        if field.name in names:
            msg = f"Project type {project_type.name!r} declares field {field.name!r} more than once."
            raise ValueError(msg)
        names.add(field.name)
        definition = field.slot_definition
        if definition is None:
            continue
        if not isinstance(definition, SlotDefinition):
            msg = f"Project field {project_type.name}.{field.name} must use a registered SlotDefinition instance."
            raise TypeError(msg)
        if _SLOT_DEFINITIONS.get(definition.name) is not definition:
            msg = (
                f"Project field {project_type.name}.{field.name} uses slot {definition.name!r}, "
                "but not its registered definition. Register the slot first, then pass that same instance."
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
