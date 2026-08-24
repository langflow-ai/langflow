"""Stable model-provider policy contract shared by OSS and Enterprise."""

from __future__ import annotations

import abc
import threading
import time
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
        return (
            "mapping",
            frozenset((_context_cache_value(key), _context_cache_value(item)) for key, item in value.items()),
        )
    if isinstance(value, tuple):
        return ("tuple", tuple(_context_cache_value(item) for item in value))
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


# Blocked-model keys reuse the persisted model-status identity grammar
# (``model``, ``provider::model``, ``provider::<type>::model``) so admins block
# exactly the identities users see in the model picker. The grammar constants
# are mirrored here instead of imported: ``unified_models.credentials`` (their
# original home) pulls service dependencies this stable contract module must
# not load. A drift guard in the unified-model tests keeps the mirrors equal.
MODEL_POLICY_KEY_SEPARATOR = "::"
MODEL_POLICY_KEY_TYPES = ("llm", "embeddings")


def normalize_blocked_model_key(key: str) -> str:
    """Canonicalize one blocked-model key's provider segment to its stable ID.

    Accepts the three model-status identity forms. The split is bounded so
    model names containing ``::`` survive when provider-qualified; a bare name
    can therefore never itself contain the separator. Raises ``ValueError``
    for empty keys or empty segments.
    """
    from lfx.base.models.provider_registry import resolve_provider_id

    normalized = key.strip()
    if not normalized:
        msg = "Blocked-model keys must not be empty"
        raise ValueError(msg)
    parts = normalized.split(MODEL_POLICY_KEY_SEPARATOR, 2)
    if len(parts) == 1:
        return normalized
    if any(not part.strip() for part in parts):
        msg = "Blocked-model key segments must not be empty"
        raise ValueError(msg)
    provider_id = resolve_provider_id(parts[0].strip())
    if len(parts) == 2:  # noqa: PLR2004
        return f"{provider_id}{MODEL_POLICY_KEY_SEPARATOR}{parts[1].strip()}"
    possible_type = parts[1].strip()
    if possible_type in MODEL_POLICY_KEY_TYPES:
        return MODEL_POLICY_KEY_SEPARATOR.join((provider_id, possible_type, parts[2].strip()))
    # Not a typed key: the remainder after the provider is one model name that
    # happens to contain the separator, mirroring parse_model_status_key.
    return f"{provider_id}{MODEL_POLICY_KEY_SEPARATOR}{MODEL_POLICY_KEY_SEPARATOR.join((parts[1], parts[2])).strip()}"


@dataclass(frozen=True)
class ModelProviderPolicyContext:
    """Principal and request attributes available to future RBAC policies."""

    user_id: UUID | str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_context_value(self.attributes))


class ModelProviderPolicyError(PermissionError):
    """A provider or model is not usable under the resolved policy snapshot."""

    code = "policy_blocked"

    def __init__(
        self,
        provider_id: str,
        purpose: ModelProviderPolicyPurpose,
        *,
        model_name: str | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.purpose = purpose
        self.model_name = model_name
        # The message is what builders read in the Playground error panel
        # (rendered by ``ErrorMessage``), so name the blocked model and point
        # at the governance owner instead of exposing only a reason code.
        if model_name is not None:
            message = (
                f"The requested model is not available: {model_name!r} ({provider_id}) "
                "is blocked by the current model provider policy. "
                "Ask an administrator to enable it."
            )
        else:
            message = "The requested model provider is not available"
        super().__init__(message)


@dataclass(frozen=True)
class ModelProviderPolicySnapshot:
    """Immutable decision set for one context, purpose, and candidate catalog."""

    context: ModelProviderPolicyContext
    purpose: ModelProviderPolicyPurpose
    candidate_provider_ids: frozenset[str]
    allowed_provider_ids: frozenset[str]
    blocked_model_keys: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        candidates = frozenset(self.candidate_provider_ids)
        allowed = frozenset(self.allowed_provider_ids)
        if not allowed.issubset(candidates):
            msg = "allowed_provider_ids must be a subset of candidate_provider_ids"
            raise ValueError(msg)
        object.__setattr__(self, "candidate_provider_ids", candidates)
        object.__setattr__(self, "allowed_provider_ids", allowed)
        object.__setattr__(self, "blocked_model_keys", frozenset(self.blocked_model_keys))

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

    def _model_is_blocked(self, provider: str, model_name: str, model_type: str | None) -> bool:
        if not self.blocked_model_keys:
            return False
        if model_name in self.blocked_model_keys:
            return True
        provider_id = self._stable_id(provider)
        qualified = f"{provider_id}{MODEL_POLICY_KEY_SEPARATOR}{model_name}"
        if qualified in self.blocked_model_keys:
            return True
        types = (model_type,) if model_type in MODEL_POLICY_KEY_TYPES else MODEL_POLICY_KEY_TYPES
        return any(
            MODEL_POLICY_KEY_SEPARATOR.join((provider_id, type_segment, model_name)) in self.blocked_model_keys
            for type_segment in types
        )

    def allows_model(self, provider: str, model_name: str, *, model_type: str | None = None) -> bool:
        """Return whether a specific model of an allowed provider is usable.

        A model is matched against the blocked-key grammar by its bare name,
        its provider-qualified name, and its typed identity. An unknown
        ``model_type`` matches every typed key so a block cannot be dodged by
        an untyped catalog row.
        """
        if not self.allows(provider):
            return False
        return not self._model_is_blocked(provider, model_name, model_type)

    def require_model(self, provider: str, model_name: str, *, model_type: str | None = None) -> None:
        """Raise a reason-coded error when a provider or one of its models is blocked."""
        self.require(provider)
        if self._model_is_blocked(provider, model_name, model_type):
            raise ModelProviderPolicyError(self._stable_id(provider), self.purpose, model_name=model_name)


class BaseModelProviderPolicyService(Service, abc.ABC):
    """Policy plugin point; implementations evaluate stable provider IDs."""

    name = ServiceType.MODEL_PROVIDER_POLICY_SERVICE.value
    SNAPSHOT_CACHE_MAX_SIZE = _MAX_SNAPSHOT_CACHE_SIZE
    SNAPSHOT_CACHE_TTL_SECONDS = 300.0
    _snapshot_cache_initialization_lock = threading.Lock()

    def __init__(self) -> None:
        super().__init__()
        self._ensure_snapshot_cache_state()

    @property
    def external_approved_provider_ids(self) -> frozenset[str] | None:
        """Return the externally owned deployment ceiling, if one is active.

        ``None`` means Langflow owns the persisted policy. An empty frozenset
        still marks the policy as externally managed, so administration must not
        fall back to the OSS database. For decisions, an empty external set is
        unrestricted; a non-empty set is a deployment ceiling. Every synchronous
        and asynchronous allowed-provider result must remain within that ceiling,
        though contextual policy may narrow it further.
        """
        return None

    def _ensure_snapshot_cache_state(self) -> None:
        """Initialize cache state, including for legacy subclasses that skipped ``super()``."""
        if "_snapshot_cache_lock" in self.__dict__:
            return
        with self._snapshot_cache_initialization_lock:
            if "_snapshot_cache_lock" not in self.__dict__:
                self._snapshot_cache: OrderedDict[tuple[Any, ...], tuple[float, ModelProviderPolicySnapshot]] = (
                    OrderedDict()
                )
                self._snapshot_cache_generation = 0
                # Publish the lock last so the fast-path above only observes a
                # fully initialized cache state.
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

    async def aget_allowed_provider_ids(
        self,
        *,
        context: ModelProviderPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,
    ) -> Collection[str]:
        """Evaluate asynchronously, defaulting to the synchronous policy hook."""
        return self.get_allowed_provider_ids(
            context=context,
            candidate_provider_ids=candidate_provider_ids,
            purpose=purpose,
        )

    def get_blocked_model_keys(
        self,
        *,
        context: ModelProviderPolicyContext,
        purpose: ModelProviderPolicyPurpose,
    ) -> Collection[str]:
        """Return normalized blocked-model keys for this context and purpose.

        Keys use the model-status identity grammar (bare ``model``,
        ``provider::model``, ``provider::<llm|embeddings>::model``) with the
        provider segment already canonicalized to its stable ID. The default
        blocks nothing; implementations typically surface a deployment-wide
        deny-list from the shared policy bundle. This is an in-memory read on
        the snapshot resolution path — implementations must not perform I/O.
        """
        _ = context, purpose
        return ()

    @staticmethod
    def _cache_key(
        *,
        context: ModelProviderPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,
    ) -> tuple[Any, ...] | None:
        try:
            attributes = _context_cache_value(context.attributes)
        except TypeError:
            # Arbitrary request attributes may contain mutable application
            # objects. They remain available to the policy evaluator, but a
            # value without a safe structural identity must bypass the cache.
            return None
        return (
            str(context.user_id) if context.user_id is not None else None,
            attributes,
            purpose,
            candidate_provider_ids,
        )

    def _cache_lookup(
        self,
        cache_key: tuple[Any, ...] | None,
    ) -> tuple[ModelProviderPolicySnapshot | None, int]:
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
        snapshot: ModelProviderPolicySnapshot,
    ) -> None:
        if cache_key is None:
            return
        self._ensure_snapshot_cache_state()
        with self._snapshot_cache_lock:
            # An invalidation may race with policy evaluation. Never repopulate
            # a cache generation that a writer has explicitly dropped.
            if generation != self._snapshot_cache_generation:
                return
            self._snapshot_cache[cache_key] = (time.monotonic(), snapshot)
            self._snapshot_cache.move_to_end(cache_key)
            if len(self._snapshot_cache) > self.SNAPSHOT_CACHE_MAX_SIZE:
                self._snapshot_cache.popitem(last=False)

    def _snapshot(
        self,
        *,
        context: ModelProviderPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,
        allowed_provider_ids: Collection[str],
    ) -> ModelProviderPolicySnapshot:
        return ModelProviderPolicySnapshot(
            context=context,
            purpose=purpose,
            candidate_provider_ids=candidate_provider_ids,
            allowed_provider_ids=frozenset(allowed_provider_ids),
            blocked_model_keys=frozenset(self.get_blocked_model_keys(context=context, purpose=purpose)),
        )

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
        cache_key = self._cache_key(
            context=context,
            candidate_provider_ids=candidates,
            purpose=purpose,
        )
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
        context: ModelProviderPolicyContext,
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,
    ) -> ModelProviderPolicySnapshot:
        """Resolve one cached snapshot through the asynchronous evaluation hook."""
        candidates = frozenset(candidate_provider_ids)
        cache_key = self._cache_key(
            context=context,
            candidate_provider_ids=candidates,
            purpose=purpose,
        )
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

    def is_allowed(
        self,
        provider_id: str,
        purpose: ModelProviderPolicyPurpose,
        *,
        context: ModelProviderPolicyContext | None = None,
    ) -> bool:
        """Return one provider decision using the stable provider identity."""
        from lfx.base.models.provider_registry import resolve_provider_id
        from lfx.services.model_provider_policy.context import current_model_provider_policy_context

        canonical_provider_id = resolve_provider_id(provider_id)
        effective_context = context
        if effective_context is None:
            effective_context = current_model_provider_policy_context() or ModelProviderPolicyContext()
        snapshot = self.resolve(
            context=effective_context,
            candidate_provider_ids=frozenset({canonical_provider_id}),
            purpose=purpose,
        )
        return canonical_provider_id in snapshot.allowed_provider_ids

    def invalidate(self) -> None:
        """Drop all cached snapshots after policy-source changes."""
        self._ensure_snapshot_cache_state()
        with self._snapshot_cache_lock:
            self._snapshot_cache.clear()
            self._snapshot_cache_generation += 1

    async def teardown(self) -> None:
        """Invalidate cached decisions; no other resources are owned by the base service."""
        self.invalidate()
