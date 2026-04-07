from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Explicit fallback aliases for rare cases that cannot be derived from
# component metadata. Most legacy names are inferred from `_type`,
# `name`, and `display_name`.
LEGACY_TYPE_ALIASES: dict[str, str] = {
    "Prompt": "Prompt Template",
    "parser": "ParserComponent",
}


def get_component_type_aliases(
    component_name: str,
    component_data: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Return the known aliases for a component type."""
    aliases: list[str] = [component_name]
    aliases.extend(old_name for old_name, new_name in LEGACY_TYPE_ALIASES.items() if new_name == component_name)

    if component_data:
        for field_name in ("name", "display_name"):
            value = component_data.get(field_name)
            if isinstance(value, str) and value:
                aliases.append(value)

        template = component_data.get("template")
        if isinstance(template, Mapping):
            component_class_name = template.get("_type")
            if (
                isinstance(component_class_name, str)
                and component_class_name
                and component_class_name.endswith("Component")
            ):
                aliases.append(component_class_name.removesuffix("Component"))

    deduped_aliases = dict.fromkeys(alias for alias in aliases if alias)
    return tuple(deduped_aliases)


def flatten_components_with_aliases(
    all_types_dict: Mapping[str, Any],
) -> dict[str, Any]:
    """Flatten a categorized component dict and append derived aliases."""
    flattened: dict[str, Any] = {}
    aliased_entries: list[tuple[str, Mapping[str, Any], Any]] = []

    for category_components in all_types_dict.values():
        if not isinstance(category_components, Mapping):
            continue
        for component_name, component_data in category_components.items():
            flattened[component_name] = component_data
            if isinstance(component_data, Mapping):
                aliased_entries.append((component_name, component_data, component_data))

    for component_name, component_data, component_value in aliased_entries:
        for alias in get_component_type_aliases(component_name, component_data):
            flattened.setdefault(alias, component_value)

    return flattened
