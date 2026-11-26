"""Project declarations with lazy discovery through the shared adapter registry.

Built-ins and explicit registrations precede entry points. Operator configuration has final
precedence. Slots remain explicit registrations; importing declarations never runs discovery.
"""

from __future__ import annotations

import inspect
import threading
from typing import TypeVar

from lfx.projects.schema import ProjectTypeDefinition, ProjectTypeField, SlotDefinition
from lfx.services.adapters.registry import AdapterRegistry
from lfx.services.adapters.schema import AdapterType

_SLOT_DEFINITIONS: dict[str, SlotDefinition] = {}
_discovery_lock = threading.RLock()
_discovering = False
DefinitionT = TypeVar("DefinitionT", bound=ProjectTypeDefinition)


def _validate_project_type(key: str, project_type: type[ProjectTypeDefinition]) -> None:
    if not isinstance(project_type, type) or not issubclass(project_type, ProjectTypeDefinition):
        msg = "Register a ProjectTypeDefinition subclass."
        raise TypeError(msg)
    for attribute in ("name", "display_name", "icon"):
        value = getattr(project_type, attribute, None)
        if not isinstance(value, str) or not value.strip():
            msg = f"Project type {key!r} must declare a non-empty {attribute}."
            raise ValueError(msg)
    if project_type.name != key:
        msg = f"Project type key {key!r} does not match declared name {project_type.name!r}."
        raise ValueError(msg)
    if not inspect.iscoroutinefunction(project_type.save_config):
        msg = f"Project type {key!r} must implement an asynchronous save_config hook."
        raise TypeError(msg)
    if not callable(project_type.compose) or inspect.iscoroutinefunction(project_type.compose):
        msg = f"Project type {key!r} must implement a synchronous compose hook."
        raise TypeError(msg)
    if not isinstance(project_type.description, str) or not isinstance(project_type.fields, tuple):
        msg = f"Project type {key!r} must declare a string description and a tuple of fields."
        raise TypeError(msg)
    for attribute in ("allows_empty_project", "exportable"):
        if not isinstance(getattr(project_type, attribute), bool):
            msg = f"Project type {key!r} must declare a boolean {attribute}."
            raise TypeError(msg)
    if (
        not isinstance(project_type.panels, tuple)
        or any(not isinstance(panel, str) or not panel.strip() for panel in project_type.panels)
        or len(set(project_type.panels)) != len(project_type.panels)
    ):
        msg = f"Project type {key!r} must declare a tuple of unique, non-empty panel names."
        raise ValueError(msg)
    names: set[str] = set()
    for field in project_type.fields:
        if not isinstance(field, ProjectTypeField):
            msg = f"Project type {key!r} must use ProjectTypeField declarations."
            raise TypeError(msg)
        if field.name in names:
            msg = f"Project type {project_type.name!r} declares field {field.name!r} more than once."
            raise ValueError(msg)
        names.add(field.name)
        if not isinstance(field.references, str) or (field.references and not field.references.strip()):
            msg = f"Project field {project_type.name}.{field.name} must name its referenced project type."
            raise ValueError(msg)
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


class _ProjectTypeRegistry(AdapterRegistry[ProjectTypeDefinition]):
    """Validate all discovery sources with the same declaration contract."""

    def register_class(self, key: str, adapter_class: type[ProjectTypeDefinition], *, override: bool = True) -> None:
        _validate_project_type(key, adapter_class)
        super().register_class(key, adapter_class, override=override)


# Declarations are stateless. This module owns their registry and lazy instance cache.
_PROJECT_TYPES = _ProjectTypeRegistry(
    adapter_type=AdapterType.PROJECT_TYPE,
    entry_point_group=AdapterType.PROJECT_TYPE.entry_point_group,
    config_section_path=AdapterType.PROJECT_TYPE.config_section_path,
)


def _ensure_discovered() -> None:
    global _discovering  # noqa: PLW0603
    if _PROJECT_TYPES.is_discovered:
        return
    with _discovery_lock:
        if _PROJECT_TYPES.is_discovered:
            return
        if _discovering:
            msg = "Project type plugins must declare types without looking up other project types during import."
            raise RuntimeError(msg)
        from lfx.services.config_discovery import resolve_config_dir
        from lfx.services.deps import get_settings_service

        _discovering = True
        try:
            config_dir = resolve_config_dir(None, settings_service=get_settings_service())
            _PROJECT_TYPES.discover(config_dir=config_dir)
        finally:
            _discovering = False


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


def register_project_type(project_type: type[DefinitionT], *, override: bool = False) -> type[DefinitionT]:
    """Register a class, also usable as a decorator. Import-time registration does no I/O.

    The same class may register again. A different class needs explicit ``override=True``;
    hosts must register their overrides before the first lookup so operator config wins.
    Entry points should export undecorated classes: discovery registers their keys itself.
    """
    _validate_project_type(getattr(project_type, "name", ""), project_type)
    with _discovery_lock:
        existing = _PROJECT_TYPES.get_class(project_type.name)
        if existing is not None and existing is not project_type and not override:
            msg = f"Project type {project_type.name!r} is already registered; refusing to overwrite it."
            raise ValueError(msg)
        if existing is not None and existing is not project_type and _PROJECT_TYPES.is_discovered:
            msg = "Register project type overrides before the first lookup so operator configuration keeps precedence."
            raise ValueError(msg)
        _PROJECT_TYPES.register_class(project_type.name, project_type, override=override)
    return project_type


def get_project_type(name: str) -> ProjectTypeDefinition:
    """Resolve a declaration. Unknown or unavailable plugins never fall back to another type."""
    _ensure_discovered()
    project_type = _PROJECT_TYPES.get_instance(name, factory=lambda cls: cls())
    if project_type is None:
        available = ", ".join(_PROJECT_TYPES.list_keys()) or "<none>"
        msg = f"Project type {name!r} is not registered. Registered types: {available}."
        raise ValueError(msg)
    return project_type


def registered_project_types() -> tuple[str, ...]:
    """Every discovered project type name, in a stable order."""
    _ensure_discovered()
    return tuple(_PROJECT_TYPES.list_keys())


def all_project_types() -> tuple[ProjectTypeDefinition, ...]:
    """Every discovered declaration, in the same stable order."""
    return tuple(get_project_type(name) for name in registered_project_types())
