"""Stable process-local contract for shared deployment policy bundles."""

from __future__ import annotations

import abc
import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.integrations.policy_constants import INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID
from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection
    from datetime import datetime
    from uuid import UUID

_MAX_TRIGGER_KIND_LENGTH = 64


def normalize_trigger_kind(kind: str) -> str:
    """Validate a stable trigger kind, including the core schedule/webhook kinds."""
    value = kind.strip().casefold()
    if (
        not value
        or len(value) > _MAX_TRIGGER_KIND_LENGTH
        or re.fullmatch(r"[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)*", value) is None
    ):
        msg = "Trigger kinds must use stable lowercase identifier syntax and at most 64 characters"
        raise ValueError(msg)
    return value


def encode_integration_provider_ids(provider_ids: Collection[str] | None) -> list[str]:
    """Encode a semantic ceiling for storage and the legacy API.

    Preserve the old meaning of an empty list across rolling upgrades. A
    reserved, nonempty allowlist makes deny-all enforceable by old replicas.
    """
    if provider_ids is None:
        return []
    if INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID in provider_ids:
        msg = "The integration deny-all identity is reserved for policy storage"
        raise ValueError(msg)
    return sorted(set(provider_ids)) if provider_ids else [INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID]


def decode_integration_provider_ids(provider_ids: Collection[str] | None) -> frozenset[str] | None:
    """Read legacy empty ceilings and the rolling-upgrade-safe deny-all marker."""
    if not provider_ids:
        return None
    providers = frozenset(provider_ids)
    if INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID in providers:
        if len(providers) != 1:
            msg = "The integration deny-all identity cannot be combined with provider IDs"
            raise ValueError(msg)
        return frozenset()
    return providers


def policy_bundle_content_hash(
    *,
    approved_provider_ids: Collection[str],
    blocked_component_keys: Collection[str],
    blocked_template_keys: Collection[str],
    blocked_model_keys: Collection[str] = (),
    approved_integration_provider_ids: Collection[str] | None = None,
    blocked_integration_action_keys: Collection[str] = (),
    approved_trigger_kinds: Collection[str] | None = None,
) -> str:
    """Return the SHA-256 of the canonical complete decision payload.

    Optional facets join the canonical payload only when their legacy storage
    representation is nonempty. Thus unrestricted policies retain their old
    hashes, and deny-all hashes agree with old replicas carrying its marker.
    """
    payload = {
        "approved_provider_ids": sorted(set(approved_provider_ids)),
        "blocked_component_keys": sorted(set(blocked_component_keys)),
        "blocked_template_keys": sorted(set(blocked_template_keys)),
    }
    if blocked_model_keys:
        payload["blocked_model_keys"] = sorted(set(blocked_model_keys))
    integration_providers = encode_integration_provider_ids(approved_integration_provider_ids)
    if integration_providers:
        payload["approved_integration_provider_ids"] = integration_providers
    if blocked_integration_action_keys:
        payload["blocked_integration_action_keys"] = sorted(set(blocked_integration_action_keys))
    if approved_trigger_kinds is not None:
        payload["approved_trigger_kinds"] = sorted({normalize_trigger_kind(kind) for kind in approved_trigger_kinds})
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
    # ``None`` means unrestricted, while an explicit empty set means deny all.
    # This keeps the operator intent distinct without a second policy-mode flag.
    approved_integration_provider_ids: frozenset[str] | None = None
    blocked_integration_action_keys: frozenset[str] = frozenset()
    # Kinds are provider-qualified (for example google.gmail). None preserves
    # unrestricted OSS behavior; an explicit empty set denies every trigger.
    approved_trigger_kinds: frozenset[str] | None = None
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
        if self.approved_integration_provider_ids is not None:
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
        if self.approved_trigger_kinds is not None:
            object.__setattr__(
                self,
                "approved_trigger_kinds",
                frozenset(normalize_trigger_kind(kind) for kind in self.approved_trigger_kinds),
            )

    def allows_trigger_kind(self, kind: str) -> bool:
        """Return the provider/kind ceiling decision without widening unknown kinds."""
        if self.approved_trigger_kinds is None:
            return True
        try:
            normalized = normalize_trigger_kind(kind)
        except ValueError:
            return False
        return normalized in self.approved_trigger_kinds


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
    def read_state(self) -> tuple[PolicyBundleSnapshot, bool]:
        """Atomically capture the complete revision and source availability."""

    @abc.abstractmethod
    def publish(self, snapshot: PolicyBundleSnapshot) -> bool:
        """Atomically publish a non-stale complete revision."""

    @abc.abstractmethod
    def mark_source_unavailable(self) -> bool:
        """Record a failed refresh without discarding last-known-good content."""
