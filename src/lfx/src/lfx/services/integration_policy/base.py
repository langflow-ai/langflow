"""Stable integration governance contract shared by OSS and Enterprise.

Two decisions travel together on the shared policy bundle:

* ``approved_integration_provider_ids`` -- an operator ceiling over providers.
  Empty means unrestricted in OSS; an Enterprise plugin may read the same empty
  set as deny-all.
* ``blocked_integration_action_keys`` -- a deny-list of capability policy keys
  sourced verbatim from bundle capability manifests
  (:class:`lfx.integrations.capabilities.IntegrationCapability.policy_keys`).

Both are evaluated for two purposes: ``DISCOVER`` hides an unavailable
capability from the palette and templates, and ``USE`` fails an execution
closed before any provider adapter runs.
"""

from __future__ import annotations

import abc
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service
from lfx.services.model_provider_policy.base import (
    ModelProviderPolicyContext,
    policy_context_cache_value,
)
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from lfx.integrations.capabilities import IntegrationCapability

_MAX_SNAPSHOT_CACHE_SIZE = 512

#: Every action policy key is namespaced under this prefix so operator
#: deny-lists can never collide with catalog or model policy keys.
INTEGRATION_POLICY_KEY_PREFIX = "integrations."
INTEGRATION_POLICY_KEY_MIN_SEGMENTS = 3
_ALLOWED_KEY_CHARACTERS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")

# The integration policy context is the model-provider policy context: the same
# request-local principal attributes (user id, project/workspace scope,
# ``provider_scope_required``) decide both, and reusing it means
# ``scoped_model_provider_policy_for_flow`` binds integration scope unchanged.
IntegrationPolicyContext = ModelProviderPolicyContext


class IntegrationPolicyPurpose(str, Enum):
    """Why the caller needs a provider or capability."""

    DISCOVER = "discover"
    USE = "use"


def normalize_integration_policy_key(key: str) -> str:
    """Canonicalize one action policy key, rejecting keys outside the grammar.

    A key is ``integrations.<provider_id>.<segment>[.<segment>...]`` in
    lowercase identifier syntax. The grammar is validated rather than coerced:
    an operator who blocks ``integrations.Google.Drive.Search`` means the same
    action as the manifest's ``integrations.google.drive.search``, so the key is
    case-folded, but a key that names no provider is a typo the API must reject
    before it silently blocks nothing.
    """
    normalized = key.strip().casefold()
    if not normalized:
        msg = "Integration action policy keys must not be empty"
        raise ValueError(msg)
    if not normalized.startswith(INTEGRATION_POLICY_KEY_PREFIX):
        msg = f"Integration action policy keys must start with {INTEGRATION_POLICY_KEY_PREFIX!r}: {key!r}"
        raise ValueError(msg)
    segments = normalized.split(".")
    if len(segments) < INTEGRATION_POLICY_KEY_MIN_SEGMENTS or any(not segment for segment in segments):
        msg = (
            "Integration action policy keys must use the form "
            f"'integrations.<provider_id>.<action>' with non-empty segments: {key!r}"
        )
        raise ValueError(msg)
    if not set(normalized) <= _ALLOWED_KEY_CHARACTERS:
        msg = f"Integration action policy keys must use lowercase identifier syntax: {key!r}"
        raise ValueError(msg)
    return normalized


def integration_policy_key_provider(key: str) -> str:
    """Return the provider id segment of a normalized action policy key."""
    return normalize_integration_policy_key(key).split(".")[1]


def integration_policy_key_prefix(provider_id: str) -> str:
    """Return the required key prefix for one provider's capabilities."""
    return f"{INTEGRATION_POLICY_KEY_PREFIX}{provider_id}."


class IntegrationPolicyError(PermissionError):
    """A provider or capability is not usable under the resolved snapshot."""

    code = "policy-blocked"

    def __init__(
        self,
        provider_id: str,
        purpose: IntegrationPolicyPurpose,
        *,
        policy_key: str | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.purpose = purpose
        self.policy_key = policy_key
        if policy_key is not None:
            message = (
                f"This integration action is not available: {policy_key!r} is blocked by the "
                "current integration policy. Ask an administrator to enable it."
            )
        else:
            message = (
                f"The {provider_id!r} integration is not available: it is outside the approved "
                "integration set. Ask an administrator to approve it."
            )
        super().__init__(message)


@dataclass(frozen=True)
class IntegrationPolicySnapshot:
    """Immutable decision set for one context, purpose, and candidate set."""

    context: IntegrationPolicyContext
    purpose: IntegrationPolicyPurpose
    candidate_provider_ids: frozenset[str]
    allowed_provider_ids: frozenset[str]
    blocked_action_keys: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        candidates = frozenset(self.candidate_provider_ids)
        allowed = frozenset(self.allowed_provider_ids)
        if not allowed.issubset(candidates):
            msg = "allowed_provider_ids must be a subset of candidate_provider_ids"
            raise ValueError(msg)
        object.__setattr__(self, "candidate_provider_ids", candidates)
        object.__setattr__(self, "allowed_provider_ids", allowed)
        object.__setattr__(self, "blocked_action_keys", frozenset(self.blocked_action_keys))

    def allows_provider(self, provider_id: str) -> bool:
        """Return whether one provider is inside the effective ceiling."""
        return provider_id in self.allowed_provider_ids

    def allows_action(self, policy_key: str) -> bool:
        """Return whether one action policy key is usable.

        A key is unusable when its provider is outside the ceiling or the key
        itself is denied. Malformed keys are treated as denied so a capability
        that ships an unparseable key never executes silently.
        """
        try:
            normalized = normalize_integration_policy_key(policy_key)
        except ValueError:
            return False
        if not self.allows_provider(normalized.split(".")[1]):
            return False
        return normalized not in self.blocked_action_keys

    def blocked_action_key(self, policy_keys: Iterable[str]) -> str | None:
        """Return the first denied key of an action, or ``None`` when usable.

        A capability declares every policy key that governs it, so blocking any
        one of them blocks the capability.
        """
        for policy_key in policy_keys:
            if not self.allows_action(policy_key):
                return policy_key
        return None

    def allows_capability(self, capability: IntegrationCapability) -> bool:
        """Return whether every policy key of one manifest capability is usable."""
        return self.blocked_action_key(capability.policy_keys) is None

    def require_provider(self, provider_id: str) -> None:
        """Raise a reason-coded error when a provider is outside the ceiling."""
        if not self.allows_provider(provider_id):
            raise IntegrationPolicyError(provider_id, self.purpose)

    def require_action(self, policy_key: str) -> None:
        """Raise a reason-coded error when one action key is denied."""
        if self.allows_action(policy_key):
            return
        try:
            provider_id = integration_policy_key_provider(policy_key)
        except ValueError:
            provider_id = ""
        if provider_id and not self.allows_provider(provider_id):
            raise IntegrationPolicyError(provider_id, self.purpose)
        raise IntegrationPolicyError(provider_id, self.purpose, policy_key=policy_key)

    def require_actions(self, policy_keys: Iterable[str]) -> None:
        """Raise on the first denied key of an action or capability."""
        for policy_key in policy_keys:
            self.require_action(policy_key)


class BaseIntegrationPolicyService(Service, abc.ABC):
    """Policy plugin point; implementations evaluate stable provider ids."""

    name = ServiceType.INTEGRATION_POLICY_SERVICE.value
    SNAPSHOT_CACHE_MAX_SIZE = _MAX_SNAPSHOT_CACHE_SIZE
    SNAPSHOT_CACHE_TTL_SECONDS = 300.0
    _snapshot_cache_initialization_lock = threading.Lock()

    def __init__(self) -> None:
        super().__init__()
        self._ensure_snapshot_cache_state()

    @property
    def external_approved_integration_provider_ids(self) -> frozenset[str] | None:
        """Return the externally owned integration ceiling, if one is active.

        ``None`` means Langflow owns the persisted policy, so ``/policy-bundle``
        may write the integration fields. Any frozenset -- including an empty
        one -- marks the policy as externally managed and locks those writes,
        mirroring ``external_approved_provider_ids`` for model providers.
        """
        return None

    def _ensure_snapshot_cache_state(self) -> None:
        """Initialize cache state, including for subclasses that skipped ``super()``."""
        if "_snapshot_cache_lock" in self.__dict__:
            return
        with self._snapshot_cache_initialization_lock:
            if "_snapshot_cache_lock" not in self.__dict__:
                self._snapshot_cache: OrderedDict[tuple[Any, ...], tuple[float, IntegrationPolicySnapshot]] = (
                    OrderedDict()
                )
                self._snapshot_cache_generation = 0
                # Publish the lock last so the fast path above only ever
                # observes a fully initialized cache.
                self._snapshot_cache_lock = threading.RLock()

    @abc.abstractmethod
    def get_allowed_provider_ids(
        self,
        *,
        context: IntegrationPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: IntegrationPolicyPurpose,
    ) -> Collection[str]:
        """Return the candidate provider ids allowed for this context and purpose."""

    async def aget_allowed_provider_ids(
        self,
        *,
        context: IntegrationPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: IntegrationPolicyPurpose,
    ) -> Collection[str]:
        """Evaluate asynchronously, defaulting to the synchronous policy hook."""
        return self.get_allowed_provider_ids(
            context=context,
            candidate_provider_ids=candidate_provider_ids,
            purpose=purpose,
        )

    def get_blocked_action_keys(
        self,
        *,
        context: IntegrationPolicyContext,
        purpose: IntegrationPolicyPurpose,
    ) -> Collection[str]:
        """Return normalized denied action keys for this context and purpose.

        The default denies nothing. This is an in-memory read on the snapshot
        resolution path -- implementations must not perform I/O.
        """
        _ = context, purpose
        return ()

    @staticmethod
    def _cache_key(
        *,
        context: IntegrationPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: IntegrationPolicyPurpose,
    ) -> tuple[Any, ...] | None:
        try:
            attributes = policy_context_cache_value(context.attributes)
        except TypeError:
            # A request attribute without a safe structural identity must
            # bypass the cache rather than collide with another principal.
            return None
        return (
            str(context.user_id) if context.user_id is not None else None,
            attributes,
            purpose,
            candidate_provider_ids,
        )

    def _cache_lookup(self, cache_key: tuple[Any, ...] | None) -> tuple[IntegrationPolicySnapshot | None, int]:
        self._ensure_snapshot_cache_state()
        with self._snapshot_cache_lock:
            generation = self._snapshot_cache_generation
            if cache_key is None:
                return None, generation
            entry = self._snapshot_cache.get(cache_key)
            if entry is None:
                return None, generation
            cached_at, snapshot = entry
            if time.monotonic() - cached_at >= self.SNAPSHOT_CACHE_TTL_SECONDS:
                del self._snapshot_cache[cache_key]
                return None, generation
            self._snapshot_cache.move_to_end(cache_key)
            return snapshot, generation

    def _cache_store(
        self,
        cache_key: tuple[Any, ...] | None,
        *,
        generation: int,
        snapshot: IntegrationPolicySnapshot,
    ) -> None:
        if cache_key is None:
            return
        self._ensure_snapshot_cache_state()
        with self._snapshot_cache_lock:
            # Never repopulate a cache generation a writer has dropped.
            if generation != self._snapshot_cache_generation:
                return
            self._snapshot_cache[cache_key] = (time.monotonic(), snapshot)
            self._snapshot_cache.move_to_end(cache_key)
            if len(self._snapshot_cache) > self.SNAPSHOT_CACHE_MAX_SIZE:
                self._snapshot_cache.popitem(last=False)

    def _snapshot(
        self,
        *,
        context: IntegrationPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: IntegrationPolicyPurpose,
        allowed_provider_ids: Collection[str],
    ) -> IntegrationPolicySnapshot:
        return IntegrationPolicySnapshot(
            context=context,
            purpose=purpose,
            candidate_provider_ids=candidate_provider_ids,
            allowed_provider_ids=frozenset(allowed_provider_ids),
            blocked_action_keys=frozenset(self.get_blocked_action_keys(context=context, purpose=purpose)),
        )

    def resolve(
        self,
        *,
        context: IntegrationPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: IntegrationPolicyPurpose,
    ) -> IntegrationPolicySnapshot:
        """Resolve one immutable, cached decision snapshot."""
        candidates = frozenset(candidate_provider_ids)
        cache_key = self._cache_key(context=context, candidate_provider_ids=candidates, purpose=purpose)
        cached, generation = self._cache_lookup(cache_key)
        if cached is not None:
            return cached
        snapshot = self._snapshot(
            context=context,
            candidate_provider_ids=candidates,
            purpose=purpose,
            allowed_provider_ids=self.get_allowed_provider_ids(
                context=context,
                candidate_provider_ids=candidates,
                purpose=purpose,
            ),
        )
        self._cache_store(cache_key, generation=generation, snapshot=snapshot)
        return snapshot

    async def aresolve(
        self,
        *,
        context: IntegrationPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: IntegrationPolicyPurpose,
    ) -> IntegrationPolicySnapshot:
        """Resolve one cached snapshot through the asynchronous evaluation hook."""
        candidates = frozenset(candidate_provider_ids)
        cache_key = self._cache_key(context=context, candidate_provider_ids=candidates, purpose=purpose)
        cached, generation = self._cache_lookup(cache_key)
        if cached is not None:
            return cached
        snapshot = self._snapshot(
            context=context,
            candidate_provider_ids=candidates,
            purpose=purpose,
            allowed_provider_ids=await self.aget_allowed_provider_ids(
                context=context,
                candidate_provider_ids=candidates,
                purpose=purpose,
            ),
        )
        self._cache_store(cache_key, generation=generation, snapshot=snapshot)
        return snapshot

    def invalidate(self) -> None:
        """Drop all cached snapshots after a policy-source change."""
        self._ensure_snapshot_cache_state()
        with self._snapshot_cache_lock:
            self._snapshot_cache.clear()
            self._snapshot_cache_generation += 1

    async def teardown(self) -> None:
        """Invalidate cached decisions; the base service owns nothing else."""
        self.invalidate()
