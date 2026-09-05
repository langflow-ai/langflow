"""Stable process-local contract for shared deployment policy bundles."""

from __future__ import annotations

import abc
import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection
    from datetime import datetime
    from uuid import UUID


def policy_bundle_content_hash(
    *,
    approved_provider_ids: Collection[str],
    blocked_component_keys: Collection[str],
    blocked_template_keys: Collection[str],
    blocked_model_keys: Collection[str] = (),
    approved_integration_provider_ids: Collection[str] = (),
    blocked_integration_action_keys: Collection[str] = (),
) -> str:
    """Return the SHA-256 of the canonical complete decision payload.

    ``blocked_model_keys``, ``approved_integration_provider_ids`` and
    ``blocked_integration_action_keys`` join the canonical payload only when
    non-empty so every revision hashed before those fields existed keeps its
    stored hash, and a bundle without model blocks or integration governance
    hashes identically across releases.
    """
    payload = {
        "approved_provider_ids": sorted(set(approved_provider_ids)),
        "blocked_component_keys": sorted(set(blocked_component_keys)),
        "blocked_template_keys": sorted(set(blocked_template_keys)),
    }
    if blocked_model_keys:
        payload["blocked_model_keys"] = sorted(set(blocked_model_keys))
    if approved_integration_provider_ids:
        payload["approved_integration_provider_ids"] = sorted(set(approved_integration_provider_ids))
    if blocked_integration_action_keys:
        payload["blocked_integration_action_keys"] = sorted(set(blocked_integration_action_keys))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class PolicyBundleSnapshot:
    """One immutable provider, catalog, and integration policy revision."""

    revision: int = 0
    initialized: bool = False
    source: str = "default"
    approved_provider_ids: frozenset[str] = frozenset()
    blocked_component_keys: frozenset[str] = frozenset()
    blocked_template_keys: frozenset[str] = frozenset()
    blocked_model_keys: frozenset[str] = frozenset()
    # Integration governance (INT-7). Both default to empty so every caller
    # written before integrations existed keeps producing an identical bundle.
    # An empty ceiling means "unrestricted" in OSS; Enterprise policy plugins
    # may read the same empty set as deny-all.
    approved_integration_provider_ids: frozenset[str] = frozenset()
    blocked_integration_action_keys: frozenset[str] = frozenset()
    content_hash: str = ""
    created_at: datetime | None = None
    created_by: UUID | None = None
    reason: str | None = None
    rollback_of_revision: int | None = None

    def __post_init__(self) -> None:
        if self.revision < 0:
            msg = "Policy bundle revision must not be negative"
            raise ValueError(msg)
        object.__setattr__(self, "approved_provider_ids", frozenset(self.approved_provider_ids))
        object.__setattr__(self, "blocked_component_keys", frozenset(self.blocked_component_keys))
        object.__setattr__(self, "blocked_template_keys", frozenset(self.blocked_template_keys))
        object.__setattr__(self, "blocked_model_keys", frozenset(self.blocked_model_keys))
        object.__setattr__(
            self,
            "approved_integration_provider_ids",
            frozenset(self.approved_integration_provider_ids),
        )
        object.__setattr__(
            self,
            "blocked_integration_action_keys",
            frozenset(self.blocked_integration_action_keys),
        )


class BasePolicyBundleService(Service, abc.ABC):
    """Publish one immutable policy reference shared by all decision planes."""

    name = ServiceType.POLICY_BUNDLE_SERVICE.value

    @property
    @abc.abstractmethod
    def snapshot(self) -> PolicyBundleSnapshot:
        """Return the currently published complete policy revision."""

    @property
    @abc.abstractmethod
    def hydrated(self) -> bool:
        """Return whether a durable revision has been published."""

    @property
    @abc.abstractmethod
    def source_available(self) -> bool:
        """Return whether the last durable refresh succeeded."""

    @abc.abstractmethod
    def publish(self, snapshot: PolicyBundleSnapshot) -> bool:
        """Atomically publish a non-stale complete revision."""

    @abc.abstractmethod
    def mark_source_unavailable(self) -> bool:
        """Record a failed refresh without discarding last-known-good content."""
