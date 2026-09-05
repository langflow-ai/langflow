"""Map palette components to the integration actions that govern them (INT-7).

Discovery hides a component when its provider is outside the operator ceiling,
or when every capability the component can perform is blocked. Two independent
declarations identify a component's actions:

* ``ConnectionRefInput`` template fields carry ``provider`` and the INT-2/INT-3
  ``capabilities`` list, which is the authoritative per-node action set for a
  connection-backed component and survives class renames.
* ``metadata.integration_provider_id`` / ``metadata.integration_capability_ids``
  are stamped from the loaded class when the bundle registry maps a capability's
  ``component_ref`` to it. This covers API-key-mode components with no
  connection-reference input.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from lfx.extension.bundle_registry import BundleRegistry, get_default_registry
from lfx.services.integration_policy import (
    IntegrationPolicyError,
    IntegrationPolicyPurpose,
    aresolve_integration_policy,
    resolve_integration_policy_for_current_context,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from lfx.integrations.capabilities import IntegrationCapability
    from lfx.services.integration_policy import IntegrationPolicySnapshot

CONNECTION_REF_FIELD_TYPE = "connection_ref"
INTEGRATION_PROVIDER_METADATA_KEY = "integration_provider_id"
INTEGRATION_CAPABILITIES_METADATA_KEY = "integration_capability_ids"


class IntegrationCapabilityIndex:
    """Immutable lookup from manifest capability id to capability and policy keys.

    Component-class lookup deliberately lives in lfx
    (``integration_policy_identity_for_component_class``): the API-key-mode
    execution gate is the only caller that has a bare class name, and it runs
    inside lfx where this module is not importable.
    """

    __slots__ = ("_capabilities", "_provider_ids")

    def __init__(self, integrations: Iterable[Any]) -> None:
        capabilities: dict[str, IntegrationCapability] = {}
        provider_ids: set[str] = set()
        for integration in integrations:
            manifest = getattr(integration, "capability_manifest", None)
            if manifest is None:
                continue
            provider_ids.add(manifest.provider_id)
            for capability in manifest.capabilities:
                capabilities[capability.id] = capability
        self._capabilities = capabilities
        self._provider_ids = frozenset(provider_ids)

    @property
    def provider_ids(self) -> frozenset[str]:
        """Every provider id declared by a loaded capability manifest."""
        return self._provider_ids

    def capability(self, capability_id: str) -> IntegrationCapability | None:
        """Return one loaded capability by its manifest id."""
        return self._capabilities.get(capability_id)

    def policy_keys(self, capability_ids: Iterable[str]) -> tuple[str, ...]:
        """Return the declared policy keys of known capability ids, in order."""
        keys: list[str] = []
        for capability_id in capability_ids:
            capability = self._capabilities.get(capability_id)
            if capability is None:
                continue
            keys.extend(capability.policy_keys)
        return tuple(dict.fromkeys(keys))


_index_lock = threading.Lock()
_cached_index: tuple[dict[str, Any], IntegrationCapabilityIndex] | None = None


def _is_same_bundle_set(cached: dict[str, Any], current: dict[str, Any]) -> bool:
    """True when both snapshots hold the very same ``BundleRecord`` objects.

    The cache keeps the snapshot it was built from alive, so a record it names
    can never be garbage-collected and a later install can never be handed the
    freed address of one -- which is why this compares objects rather than a
    hash of their ``id()``. ``BundleRecord`` is frozen and the reload pipeline
    swaps in a brand-new record, so object identity is exactly "the installed
    set has not changed".
    """
    if len(cached) != len(current):
        return False
    return all(name in cached and cached[name] is record for name, record in current.items())


def build_integration_capability_index(registry: BundleRegistry | None = None) -> IntegrationCapabilityIndex:
    """Build (and cache per registry snapshot) the loaded capability index.

    ``GET /all`` is a hot path, so the index is cached against the registry's
    current bundle snapshot rather than rebuilt per request. A bundle install or
    reload produces a new snapshot and therefore a new index.
    """
    global _cached_index  # noqa: PLW0603

    active_registry = registry if registry is not None else get_default_registry()
    snapshot = active_registry.snapshot()
    if registry is None:
        with _index_lock:
            cached = _cached_index
            if cached is not None and _is_same_bundle_set(cached[0], snapshot):
                return cached[1]
    index = IntegrationCapabilityIndex(
        capability for record in snapshot.values() for capability in getattr(record, "integrations", ())
    )
    if registry is None:
        with _index_lock:
            _cached_index = (snapshot, index)
    return index


def reset_integration_capability_index() -> None:
    """Drop the cached index (test-only, and after a bundle reload)."""
    global _cached_index  # noqa: PLW0603

    with _index_lock:
        _cached_index = None


def _template_connection_requirements(component: dict) -> list[tuple[str, tuple[str, ...]]]:
    """Return ``(provider, capability_ids)`` for each connection-reference field."""
    template = component.get("template")
    if not isinstance(template, dict):
        return []
    requirements: list[tuple[str, tuple[str, ...]]] = []
    for field in template.values():
        if not isinstance(field, dict) or field.get("type") != CONNECTION_REF_FIELD_TYPE:
            continue
        provider = field.get("provider")
        if not isinstance(provider, str) or not provider:
            continue
        capabilities = field.get("capabilities")
        capability_ids = tuple(item for item in capabilities if isinstance(item, str)) if capabilities else ()
        requirements.append((provider, capability_ids))
    return requirements


def _metadata_requirement(component: dict) -> tuple[str, tuple[str, ...]] | None:
    """Return the stamped ``(provider, capability_ids)`` of an API-key component."""
    metadata = component.get("metadata")
    if not isinstance(metadata, dict):
        return None
    provider = metadata.get(INTEGRATION_PROVIDER_METADATA_KEY)
    if not isinstance(provider, str) or not provider:
        return None
    capabilities = metadata.get(INTEGRATION_CAPABILITIES_METADATA_KEY)
    capability_ids = tuple(item for item in capabilities if isinstance(item, str)) if capabilities else ()
    return provider, capability_ids


def integration_requirements(component: Any) -> list[tuple[str, tuple[str, ...]]]:
    """Return every ``(provider, capability_ids)`` pair one palette node declares.

    An unrelated component in a mixed bundle declares nothing and is never
    filtered.
    """
    if not isinstance(component, dict):
        return []
    requirements = _template_connection_requirements(component)
    stamped = _metadata_requirement(component)
    if stamped is not None and stamped not in requirements:
        requirements.append(stamped)
    return requirements


def component_is_allowed(
    component: Any,
    *,
    policy: IntegrationPolicySnapshot,
    index: IntegrationCapabilityIndex,
) -> bool:
    """Return whether one palette component survives the integration policy.

    A component is hidden when any provider it declares is outside the ceiling,
    or when it declares capabilities and *every* one of them is blocked. A
    component that keeps at least one usable action stays visible: option-level
    filtering inside an action picker is the bundle's own responsibility, using
    ``resolve_integration_policy``.
    """
    requirements = integration_requirements(component)
    if not requirements:
        return True
    for provider_id, capability_ids in requirements:
        if not policy.allows_provider(provider_id):
            return False
        declared = [
            capability
            for capability_id in capability_ids
            if (capability := index.capability(capability_id)) is not None
        ]
        if not declared:
            # The node names no known capability (or the bundle is not loaded in
            # this process); the provider ceiling is the only available decision.
            continue
        if not any(policy.allows_capability(capability) for capability in declared):
            return False
    return True


def candidate_provider_ids(all_types: dict[str, dict[str, dict]]) -> frozenset[str]:
    """Return every integration provider the palette references."""
    return frozenset(
        provider_id
        for components in all_types.values()
        for component in components.values()
        for provider_id, _capability_ids in integration_requirements(component)
    )


async def filter_component_palette_by_integration_policy(
    all_types: dict[str, dict[str, dict]],
    *,
    user_id,
    attributes: dict[str, Any] | None = None,
    purpose: IntegrationPolicyPurpose = IntegrationPolicyPurpose.DISCOVER,
) -> dict[str, dict[str, dict]]:
    """Return a request-local palette without policy-blocked integration nodes.

    The component registry is a process-wide cache, so category mappings are
    copied and component payloads are shared, never mutated. A palette with no
    integration components short-circuits without resolving any policy.
    """
    provider_ids = candidate_provider_ids(all_types)
    if not provider_ids:
        return all_types
    policy = await aresolve_integration_policy(
        user_id=user_id,
        provider_ids=provider_ids,
        purpose=purpose,
        attributes=attributes,
    )
    index = build_integration_capability_index()
    return {
        category: {
            name: component
            for name, component in components.items()
            if component_is_allowed(component, policy=policy, index=index)
        }
        for category, components in all_types.items()
    }


def _graph_node_components(nodes: Iterable[Any]) -> list[dict]:
    """Return the frontend-node payload of every node in a saved graph."""
    components: list[dict] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        component = data.get("node")
        if isinstance(component, dict):
            components.append(component)
    return components


def graph_nodes_are_allowed(
    nodes: Iterable[Any],
    *,
    policy: IntegrationPolicySnapshot,
    index: IntegrationCapabilityIndex,
) -> bool:
    """Return whether every integration node of a saved graph survives the policy."""
    return all(
        component_is_allowed(component, policy=policy, index=index) for component in _graph_node_components(nodes)
    )


def graph_provider_ids(nodes: Iterable[Any]) -> frozenset[str]:
    """Return every integration provider one saved graph references."""
    return frozenset(
        provider_id
        for component in _graph_node_components(nodes)
        for provider_id, _capability_ids in integration_requirements(component)
    )


def template_integration_filter(
    templates: Iterable[tuple[Any, Iterable[Any]]],
) -> set[int]:
    """Return the indices of templates hiding at least one blocked integration node.

    Template listing is synchronous and runs inside a request that already bound
    the policy context, so the decision is resolved from that context. Templates
    referencing no integration never resolve a policy at all.
    """
    entries = list(templates)
    provider_ids = frozenset(provider_id for _key, nodes in entries for provider_id in graph_provider_ids(nodes))
    if not provider_ids:
        return set()
    policy = resolve_integration_policy_for_current_context(
        provider_ids=provider_ids,
        purpose=IntegrationPolicyPurpose.DISCOVER,
    )
    index = build_integration_capability_index()
    return {
        position
        for position, (_key, nodes) in enumerate(entries)
        if not graph_nodes_are_allowed(nodes, policy=policy, index=index)
    }


async def ablocked_template_positions(
    templates: Iterable[Iterable[Any]],
    *,
    user_id,
    attributes: dict[str, Any] | None = None,
) -> set[int]:
    """Return the positions of templates containing a policy-blocked integration node.

    A template is hidden when one of its nodes could never run, mirroring the
    catalog-policy rule that hides a template whose component is blocked.
    """
    entries = [list(nodes) for nodes in templates]
    provider_ids = frozenset(provider_id for nodes in entries for provider_id in graph_provider_ids(nodes))
    if not provider_ids:
        return set()
    policy = await aresolve_integration_policy(
        user_id=user_id,
        provider_ids=provider_ids,
        purpose=IntegrationPolicyPurpose.DISCOVER,
        attributes=attributes,
    )
    index = build_integration_capability_index()
    return {
        position
        for position, nodes in enumerate(entries)
        if not graph_nodes_are_allowed(nodes, policy=policy, index=index)
    }


async def aenforce_integration_policy_for_component(
    component: Any,
    *,
    user_id,
    attributes: dict[str, Any] | None = None,
    purpose: IntegrationPolicyPurpose = IntegrationPolicyPurpose.DISCOVER,
) -> None:
    """Raise ``IntegrationPolicyError`` when one built component is blocked.

    Used by the custom-component build/update routes so posting the source of a
    blocked integration component cannot reconstruct what discovery hides.
    """
    requirements = integration_requirements(component)
    if not requirements:
        return
    policy = await aresolve_integration_policy(
        user_id=user_id,
        provider_ids={provider_id for provider_id, _capability_ids in requirements},
        purpose=purpose,
        attributes=attributes,
    )
    index = build_integration_capability_index()
    if component_is_allowed(component, policy=policy, index=index):
        return
    provider_id, capability_ids = requirements[0]
    policy.require_provider(provider_id)
    policy.require_actions(index.policy_keys(capability_ids))
    # Every declared key resolved as allowed but the component is still blocked:
    # deny on the provider rather than returning a component discovery hides.
    raise IntegrationPolicyError(provider_id, purpose)


__all__ = [
    "CONNECTION_REF_FIELD_TYPE",
    "INTEGRATION_CAPABILITIES_METADATA_KEY",
    "INTEGRATION_PROVIDER_METADATA_KEY",
    "IntegrationCapabilityIndex",
    "ablocked_template_positions",
    "aenforce_integration_policy_for_component",
    "build_integration_capability_index",
    "candidate_provider_ids",
    "component_is_allowed",
    "filter_component_palette_by_integration_policy",
    "graph_nodes_are_allowed",
    "graph_provider_ids",
    "integration_requirements",
    "reset_integration_capability_index",
    "template_integration_filter",
]
