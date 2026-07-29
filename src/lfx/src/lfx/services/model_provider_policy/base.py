"""Stable model-provider policy contract shared by OSS and Enterprise."""

from __future__ import annotations

import abc
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection
    from uuid import UUID

_MAX_SNAPSHOT_CACHE_SIZE = 512


def _freeze_context_value(value: Any) -> Any:
    """Recursively freeze request attributes captured by a policy snapshot."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_context_value(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_context_value(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze_context_value(item) for item in value)
    return value


def _context_cache_value(value: Any) -> Any:
    """Convert frozen context attributes to a type-preserving cache key.

    Python considers values such as ``True`` and ``1`` equal dictionary keys.
    Policy attributes may legitimately distinguish them, so every scalar and
    container carries an explicit type tag. Unsupported unhashable objects are
    rejected instead of falling back to ``repr()``, which is not a safe policy
    identity.
    """
    if isinstance(value, Mapping):
        items = [(_context_cache_value(key), _context_cache_value(item)) for key, item in value.items()]
        return ("mapping", tuple(sorted(items, key=repr)))
    if isinstance(value, tuple):
        return ("tuple", tuple(_context_cache_value(item) for item in value))
    if isinstance(value, list):
        return ("list", tuple(_context_cache_value(item) for item in value))
    if isinstance(value, set):
        return ("set", frozenset(_context_cache_value(item) for item in value))
    if isinstance(value, frozenset):
        return ("frozenset", frozenset(_context_cache_value(item) for item in value))
    try:
        hash(value)
    except TypeError as exc:
        msg = f"Unsupported unhashable model-provider policy attribute: {type(value).__qualname__}"
        raise TypeError(msg) from exc
    value_type = type(value)
    return ("scalar", value_type.__module__, value_type.__qualname__, value)


class ModelProviderPolicyPurpose(str, Enum):
    """Why the caller needs access to a provider."""

    DISCOVER = "discover"
    CONFIGURE = "configure"
    USE = "use"


@dataclass(frozen=True)
class ModelProviderPolicyContext:
    """Principal and request attributes available to future RBAC policies."""

    user_id: UUID | str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_context_value(self.attributes))


class ModelProviderPolicyError(PermissionError):
    """A provider is not usable under the resolved policy snapshot."""

    code = "policy_blocked"

    def __init__(self, provider_id: str, purpose: ModelProviderPolicyPurpose) -> None:
        self.provider_id = provider_id
        self.purpose = purpose
        super().__init__("The requested model provider is not available")


@dataclass(frozen=True)
class ModelProviderPolicySnapshot:
    """Immutable decision set for one context, purpose, and candidate catalog."""

    context: ModelProviderPolicyContext
    purpose: ModelProviderPolicyPurpose
    candidate_provider_ids: frozenset[str]
    allowed_provider_ids: frozenset[str]

    def __post_init__(self) -> None:
        candidates = frozenset(self.candidate_provider_ids)
        allowed = frozenset(self.allowed_provider_ids)
        if not allowed.issubset(candidates):
            msg = "allowed_provider_ids must be a subset of candidate_provider_ids"
            raise ValueError(msg)
        object.__setattr__(self, "candidate_provider_ids", candidates)
        object.__setattr__(self, "allowed_provider_ids", allowed)

    @staticmethod
    def _stable_id(provider: str) -> str:
        from lfx.base.models.provider_registry import resolve_provider_id

        return resolve_provider_id(provider)

    def allows(self, provider: str) -> bool:
        """Return whether a legacy name, alias, or stable ID is allowed."""
        return self._stable_id(provider) in self.allowed_provider_ids

    def filter(self, providers: Collection[str]) -> list[str]:
        """Filter provider names without changing their order or representation."""
        return [provider for provider in providers if self.allows(provider)]

    def require(self, provider: str) -> None:
        """Raise a reason-coded error when a provider is not allowed."""
        if not self.allows(provider):
            raise ModelProviderPolicyError(self._stable_id(provider), self.purpose)


class BaseModelProviderPolicyService(Service, abc.ABC):
    """Policy plugin point; implementations evaluate stable provider IDs."""

    name = ServiceType.MODEL_PROVIDER_POLICY_SERVICE.value

    def __init__(self) -> None:
        super().__init__()
        self._snapshot_cache: OrderedDict[tuple[Any, ...], ModelProviderPolicySnapshot] = OrderedDict()
        self._snapshot_cache_generation = 0
        self._snapshot_cache_lock = threading.RLock()

    @abc.abstractmethod
    def get_allowed_provider_ids(
        self,
        *,
        context: ModelProviderPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,
    ) -> Collection[str]:
        """Return the candidate IDs allowed for this context and purpose."""

    def resolve(
        self,
        *,
        context: ModelProviderPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,
    ) -> ModelProviderPolicySnapshot:
        """Resolve one immutable decision snapshot.

        Enterprise implementations can intersect a deployment ceiling with a
        single batch RBAC evaluation in ``get_allowed_provider_ids``. The base
        method validates that a plugin can never widen the candidate set and
        caches the immutable snapshot until :meth:`invalidate` is called.
        """
        candidates = frozenset(candidate_provider_ids)
        cache_key = (
            str(context.user_id) if context.user_id is not None else None,
            _context_cache_value(context.attributes),
            purpose,
            candidates,
        )
        with self._snapshot_cache_lock:
            cached = self._snapshot_cache.get(cache_key)
            if cached is not None:
                self._snapshot_cache.move_to_end(cache_key)
                return cached
            generation = self._snapshot_cache_generation

        allowed = frozenset(
            self.get_allowed_provider_ids(
                context=context,
                candidate_provider_ids=candidates,
                purpose=purpose,
            )
        )
        snapshot = ModelProviderPolicySnapshot(
            context=context,
            purpose=purpose,
            candidate_provider_ids=candidates,
            allowed_provider_ids=allowed,
        )
        with self._snapshot_cache_lock:
            # An invalidation may race with policy evaluation. Never repopulate
            # a cache generation that a writer has explicitly dropped.
            if generation == self._snapshot_cache_generation:
                self._snapshot_cache[cache_key] = snapshot
                self._snapshot_cache.move_to_end(cache_key)
                if len(self._snapshot_cache) > _MAX_SNAPSHOT_CACHE_SIZE:
                    self._snapshot_cache.popitem(last=False)
        return snapshot

    async def aresolve(
        self,
        *,
        context: ModelProviderPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,
    ) -> ModelProviderPolicySnapshot:
        """Resolve policy asynchronously and return a synchronous snapshot.

        The OSS implementation delegates to the cached synchronous resolver.
        Enterprise policy sources may override this method when their policy
        load is I/O-bound while preserving the immutable snapshot contract for
        downstream catalog and runtime code.
        """
        return self.resolve(
            context=context,
            candidate_provider_ids=candidate_provider_ids,
            purpose=purpose,
        )

    def is_allowed(
        self,
        provider_id: str,
        purpose: ModelProviderPolicyPurpose,
        *,
        context: ModelProviderPolicyContext | None = None,
    ) -> bool:
        """Return one provider decision using the stable provider identity."""
        snapshot = self.resolve(
            context=context or ModelProviderPolicyContext(),
            candidate_provider_ids=frozenset({provider_id}),
            purpose=purpose,
        )
        return snapshot.allows(provider_id)

    def invalidate(self) -> None:
        """Drop all cached snapshots after policy-source changes."""
        with self._snapshot_cache_lock:
            self._snapshot_cache.clear()
            self._snapshot_cache_generation += 1

    async def teardown(self) -> None:
        """No resources are owned by the base policy service."""
        self.invalidate()
