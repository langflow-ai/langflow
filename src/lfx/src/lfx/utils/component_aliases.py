from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Explicit fallback aliases for rare cases that cannot be derived from
# component metadata. Most legacy names are inferred from `_type`,
# `name`, and `display_name`.
LEGACY_TYPE_ALIASES: dict[str, str] = {
    "Prompt": "Prompt Template",
    "parser": "ParserComponent",
}

# Extension components are keyed ``ext:<bundle>:<ClassName>@<slot>``.  Their
# decorated templates carry ``name=None`` and ``_type="Component"``, so none
# of the metadata-derived aliases below yield the legacy class name; the key
# itself is the only source.  Flows saved before a provider moved out of the
# built-in palette reference the legacy keys (``TavilySearchComponent`` /
# ``TavilySearch``) -- without these aliases such nodes stop resolving a
# current template, so e.g. the starter-project updater leaves their embedded
# code stale and the UI reports them as permanently outdated.  Mirrors
# ``getTemplateAliases`` in the frontend's reactflowUtils.ts.
_EXT_KEY_RE = re.compile(r"^ext:[^:]+:(?P<class_name>[^@]+)@.+$")


def _component_alias_tiers(
    component_name: str,
    component_data: Mapping[str, Any] | None,
) -> tuple[list[str], list[str]]:
    """Split a component's aliases into identity and display tiers.

    Identity aliases derive from the component's own canonical name -- the
    registry key, explicit legacy mappings, the ext-key class name, and the
    ``name`` field.  Display aliases derive from human-facing labels
    (``display_name``, the template ``_type``) that can legitimately collide
    with another component's identity (e.g. the Composio ``AgentQL`` wrapper's
    ``display_name`` vs. the standalone ``AgentQL`` component's class name).

    Keeping the two tiers separate lets ``flatten_components_with_aliases``
    register every identity alias before any display alias, so a component's
    true name always wins its own key regardless of registry iteration order.
    """
    identity: list[str] = [component_name]
    identity.extend(old_name for old_name, new_name in LEGACY_TYPE_ALIASES.items() if new_name == component_name)

    ext_match = _EXT_KEY_RE.match(component_name)
    if ext_match:
        bare_class_name = ext_match.group("class_name")
        identity.append(bare_class_name)
        if bare_class_name.endswith("Component"):
            identity.append(bare_class_name.removesuffix("Component"))

    display: list[str] = []
    if component_data:
        name_value = component_data.get("name")
        if isinstance(name_value, str) and name_value:
            identity.append(name_value)

        display_name_value = component_data.get("display_name")
        if isinstance(display_name_value, str) and display_name_value:
            display.append(display_name_value)

        template = component_data.get("template")
        if isinstance(template, Mapping):
            component_class_name = template.get("_type")
            if (
                isinstance(component_class_name, str)
                and component_class_name
                and component_class_name.endswith("Component")
            ):
                display.append(component_class_name.removesuffix("Component"))

    return identity, display


def get_component_type_aliases(
    component_name: str,
    component_data: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Return the known aliases for a component type."""
    identity, display = _component_alias_tiers(component_name, component_data)
    deduped_aliases = dict.fromkeys(alias for alias in (*identity, *display) if alias)
    return tuple(deduped_aliases)


def flatten_components_with_aliases(
    all_types_dict: Mapping[str, Any],
) -> dict[str, Any]:
    """Flatten a categorized component dict and append derived aliases.

    Aliases are registered in two passes: identity aliases (a component's own
    canonical name) for every component first, then display aliases.  This makes
    resolution deterministic when two components share a label -- a component's
    own class name beats another component's ``display_name`` no matter the
    registry iteration order.
    """
    flattened: dict[str, Any] = {}
    aliased_entries: list[tuple[list[str], list[str], Any]] = []

    for category_components in all_types_dict.values():
        if not isinstance(category_components, Mapping):
            continue
        for component_name, component_data in category_components.items():
            flattened[component_name] = component_data
            if isinstance(component_data, Mapping):
                identity, display = _component_alias_tiers(component_name, component_data)
                aliased_entries.append((identity, display, component_data))

    for identity, _display, component_value in aliased_entries:
        for alias in identity:
            if alias:
                flattened.setdefault(alias, component_value)

    for _identity, display, component_value in aliased_entries:
        for alias in display:
            if alias:
                flattened.setdefault(alias, component_value)

    return flattened
