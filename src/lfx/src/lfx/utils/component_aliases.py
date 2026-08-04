from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

# Explicit fallback aliases for rare cases that cannot be derived from
# component metadata. Most legacy names are inferred from `_type`,
# `name`, and `display_name`.
LEGACY_TYPE_ALIASES: dict[str, str] = {
    "Prompt": "Prompt Template",
    "TavilyAISearch": "ext:tavily:TavilySearchComponent@official",
    "TavilySearchToolComponent": "ext:tavily:TavilySearchComponent@official",
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


@dataclass(frozen=True, slots=True)
class ComponentIdentityIndex:
    """Resolve component aliases against the current registry without guessing.

    Registry keys are the canonical component identities for the running
    release. Aliases may point at one or more canonical keys; keeping every
    candidate prevents registry iteration order from silently choosing a
    component when an alias is ambiguous.
    """

    canonical_keys: frozenset[str]
    aliases: Mapping[str, frozenset[str]]

    def resolve(self, identity: str) -> frozenset[str]:
        """Return canonical candidates for ``identity``.

        Exact canonical keys always win over aliases contributed by another
        component. Unknown strings resolve to themselves so existing exact,
        case-sensitive policy behavior is preserved for synthetic/custom
        component identities that are not in the registry.
        """
        if identity in self.canonical_keys:
            return frozenset({identity})
        return self.aliases.get(identity, frozenset({identity}))

    def resolve_many(self, identities: Iterable[str]) -> frozenset[str]:
        """Return the union of canonical candidates for ``identities``."""
        return frozenset(candidate for identity in identities for candidate in self.resolve(identity))


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
    own identity always beats another component's ``display_name`` for a shared
    key, regardless of registry iteration order.  (This does not disambiguate
    two components that contribute the *same identity* alias -- e.g. an
    ``XComponent`` and a bare ``X`` across two bundles -- which remain
    first-wins by iteration order; a real registry key, set directly, still
    beats any alias.)
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


def _component_identity_index_alias_tiers(
    component_name: str,
    component_data: Mapping[str, Any] | None,
) -> tuple[list[str], list[str]]:
    """Return aliases used only by the canonical policy identity index.

    Runtime component materialization exposes the Python class name while the
    registry may use a component's explicit ``name`` (for example,
    ``PromptComponent`` versus ``Prompt Template``). These class identities
    are intentionally index-only so the legacy starter-project flattening
    behavior remains unchanged.
    """
    identity, display = _component_alias_tiers(component_name, component_data)
    if component_data:
        metadata = component_data.get("metadata")
        if isinstance(metadata, Mapping):
            module_value = metadata.get("module")
            if isinstance(module_value, str) and module_value:
                module_class_name = module_value.rsplit(".", maxsplit=1)[-1]
                if module_class_name:
                    identity.append(module_class_name)
                    if module_class_name.endswith("Component"):
                        identity.append(module_class_name.removesuffix("Component"))

        template = component_data.get("template")
        if isinstance(template, Mapping):
            template_class_name = template.get("_type")
            if isinstance(template_class_name, str) and template_class_name and template_class_name != "Component":
                identity.append(template_class_name)
                if template_class_name.endswith("Component"):
                    display.append(template_class_name.removesuffix("Component"))

    return (
        list(dict.fromkeys(alias for alias in identity if alias)),
        list(dict.fromkeys(alias for alias in display if alias)),
    )


def build_component_identity_index(all_types_dict: Mapping[str, Any]) -> ComponentIdentityIndex:
    """Build a collision-aware identity index from a categorized registry.

    Canonical registry keys are collected before aliases so an alias can never
    shadow an exact key. Unlike :func:`flatten_components_with_aliases`, this
    index retains all canonical candidates for an ambiguous alias instead of
    selecting the first component encountered. The legacy flattening helper is
    intentionally unchanged because starter-project upgrades still depend on
    its value lookup behavior.
    """
    entries: list[tuple[str, Mapping[str, Any] | None]] = []
    canonical_keys: set[str] = set()

    for category_components in all_types_dict.values():
        if not isinstance(category_components, Mapping):
            continue
        for component_name, component_data in category_components.items():
            if not isinstance(component_name, str) or not component_name:
                continue
            canonical_keys.add(component_name)
            entries.append(
                (
                    component_name,
                    component_data if isinstance(component_data, Mapping) else None,
                )
            )

    identity_candidates: defaultdict[str, set[str]] = defaultdict(set)
    display_candidates: defaultdict[str, set[str]] = defaultdict(set)
    for component_name, component_data in entries:
        identity, display = _component_identity_index_alias_tiers(component_name, component_data)
        for alias in identity:
            if alias and alias not in canonical_keys:
                identity_candidates[alias].add(component_name)
        for alias in display:
            if alias and alias not in canonical_keys:
                display_candidates[alias].add(component_name)

    # Identity aliases outrank display labels, matching the legacy two-pass
    # precedence without its first-wins behavior. Collisions within the
    # winning tier retain every candidate.
    alias_candidates = {
        alias: identity_candidates.get(alias) or display_candidates[alias]
        for alias in identity_candidates.keys() | display_candidates.keys()
    }

    frozen_aliases = MappingProxyType({alias: frozenset(candidates) for alias, candidates in alias_candidates.items()})
    return ComponentIdentityIndex(
        canonical_keys=frozenset(canonical_keys),
        aliases=frozen_aliases,
    )


def flatten_components_with_aliases(
    all_types_dict: Mapping[str, Any],
) -> dict[str, Any]:
    """Flatten a categorized component dict and append derived aliases.

    Aliases are registered in two passes: identity aliases (a component's own
    canonical name) for every component first, then display aliases.  A
    component's own class name therefore beats another component's
    ``display_name`` for a shared key, no matter the registry iteration order
    (and a real registry key, set directly below, beats any alias).  This does
    NOT disambiguate two components that contribute the *same identity* alias --
    that collision remains first-wins by iteration order.
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
