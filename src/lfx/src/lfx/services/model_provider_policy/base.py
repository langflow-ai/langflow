"""Stable model-provider policy contract shared by OSS and Enterprise."""

from __future__ import annotations

import abc
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


def _freeze_context_value(value: Any) -> Any:
    """Recursively freeze request attributes captured by a policy snapshot."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_context_value(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_context_value(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze_context_value(item) for item in value)
    return value


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
        from lfx.base.models.provider_registry import provider_id_for

        return provider_id_for(provider) or provider

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
        method validates that a plugin can never widen the candidate set.
        """
        candidates = frozenset(candidate_provider_ids)
        allowed = frozenset(
            self.get_allowed_provider_ids(
                context=context,
                candidate_provider_ids=candidates,
                purpose=purpose,
            )
        )
        return ModelProviderPolicySnapshot(
            context=context,
            purpose=purpose,
            candidate_provider_ids=candidates,
            allowed_provider_ids=allowed,
        )

    async def teardown(self) -> None:
        """No resources are owned by the base policy service."""
