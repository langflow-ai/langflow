"""Stable catalog-policy contract shared by LFX and Langflow."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.services.base import Service
from lfx.services.policy_bundle import PolicyBundleSnapshot
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class CatalogPolicySnapshot:
    """Immutable process-local catalog-policy decision snapshot.

    An empty snapshot is intentionally fail-open: until a durable policy has
    been hydrated, every component and template is available.
    """

    blocked_component_keys: frozenset[str] = frozenset()
    blocked_template_keys: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocked_component_keys", frozenset(self.blocked_component_keys))
        object.__setattr__(self, "blocked_template_keys", frozenset(self.blocked_template_keys))

    @property
    def enabled(self) -> bool:
        """Return whether this snapshot blocks at least one catalog resource."""
        return bool(self.blocked_component_keys or self.blocked_template_keys)

    def is_component_blocked(self, key: str) -> bool:
        """Return whether a component key is blocked."""
        return key in self.blocked_component_keys

    def is_template_blocked(self, key: str) -> bool:
        """Return whether a template key is blocked."""
        return key in self.blocked_template_keys

    def blocked_components(self, keys: Iterable[str]) -> frozenset[str]:
        """Return the blocked subset of component keys."""
        return frozenset(key for key in keys if self.is_component_blocked(key))

    def blocked_templates(self, keys: Iterable[str]) -> frozenset[str]:
        """Return the blocked subset of template keys."""
        return frozenset(key for key in keys if self.is_template_blocked(key))


@dataclass(frozen=True, slots=True)
class CatalogPolicyUpdate:
    """One committed whole-set replacement and its exact delta."""

    snapshot: CatalogPolicySnapshot
    added: frozenset[str]
    removed: frozenset[str]


class BaseCatalogPolicyService(Service, abc.ABC):
    """Synchronous catalog-policy decision surface.

    Implementations publish a complete immutable snapshot after loading
    durable policy. The initial empty snapshot is deliberately fail-open so
    LFX remains usable when no Langflow database-backed policy is present.
    """

    name = ServiceType.CATALOG_POLICY_SERVICE.value

    @property
    def external_policy_snapshot(self) -> CatalogPolicySnapshot | None:
        """Return the externally owned active snapshot, if one is configured.

        ``None`` means Langflow owns the durable catalog policy. An empty
        snapshot still represents externally managed policy. A non-``None``
        value must be value-equivalent to ``snapshot`` because administration
        reads use this property while runtime enforcement uses ``snapshot``.
        """
        return None

    @property
    @abc.abstractmethod
    def snapshot(self) -> CatalogPolicySnapshot:
        """Return the current immutable process-local snapshot."""

    @property
    def policy_bundle_snapshot(self) -> PolicyBundleSnapshot:
        """Return a compatibility bundle view for catalog-only implementations."""
        snapshot = self.snapshot
        return PolicyBundleSnapshot(
            blocked_component_keys=snapshot.blocked_component_keys,
            blocked_template_keys=snapshot.blocked_template_keys,
        )

    @property
    def supports_policy_bundle_updates(self) -> bool:
        """Return whether committed shared bundles can be applied atomically.

        Legacy plugins default to ``False`` so Langflow never reports a
        successful database write that the active enforcement plugin ignored.
        """
        return False

    def apply_policy_bundle(self, snapshot: PolicyBundleSnapshot) -> bool:
        """Publish a durable bundle when the implementation supports live updates."""
        _ = snapshot
        return False

    @property
    def enabled(self) -> bool:
        """Return whether the current snapshot blocks any catalog resource."""
        return self.snapshot.enabled

    def is_component_blocked(self, key: str) -> bool:
        """Return whether a component key is blocked."""
        return self.snapshot.is_component_blocked(key)

    def is_template_blocked(self, key: str) -> bool:
        """Return whether a template key is blocked."""
        return self.snapshot.is_template_blocked(key)

    def blocked_component_keys(self, keys: Iterable[str]) -> frozenset[str]:
        """Return the blocked subset of component keys in one lookup."""
        return self.snapshot.blocked_components(keys)

    def blocked_template_keys(self, keys: Iterable[str]) -> frozenset[str]:
        """Return the blocked subset of template keys in one lookup."""
        return self.snapshot.blocked_templates(keys)

    def is_component_allowed(self, key: str) -> bool:
        """Return whether a component key is allowed."""
        return not self.is_component_blocked(key)

    def is_template_allowed(self, key: str) -> bool:
        """Return whether a template key is allowed."""
        return not self.is_template_blocked(key)

    async def hydrate(self) -> CatalogPolicySnapshot:
        """Return the current snapshot when no durable loader is required."""
        return self.snapshot

    async def replace_blocked_component_keys(
        self,
        keys: Collection[str],
        *,
        actor_user_id: UUID | None,
    ) -> CatalogPolicyUpdate:
        """Replace component policy when the implementation is writable."""
        raise NotImplementedError

    async def replace_blocked_template_keys(
        self,
        keys: Collection[str],
        *,
        actor_user_id: UUID | None,
    ) -> CatalogPolicyUpdate:
        """Replace template policy when the implementation is writable."""
        raise NotImplementedError

    async def teardown(self) -> None:
        """No resources are owned by the base policy service."""
