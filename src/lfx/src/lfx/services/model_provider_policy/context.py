"""Request-local principal attributes for synchronous provider-policy checks."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any

from lfx.services.model_provider_policy.base import ModelProviderPolicyContext

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

_current_context: ContextVar[ModelProviderPolicyContext | None] = ContextVar(
    "model_provider_policy_context",
    default=None,
)


def set_current_model_provider_policy_context(
    *,
    user_id: UUID | str | None,
    attributes: Mapping[str, Any] | None = None,
) -> Token[ModelProviderPolicyContext | None]:
    """Bind trusted principal attributes to the current request/task context."""
    return _current_context.set(ModelProviderPolicyContext(user_id=user_id, attributes=attributes or {}))


def reset_current_model_provider_policy_context(token: Token[ModelProviderPolicyContext | None]) -> None:
    """Restore the context that preceded ``set_current_model_provider_policy_context``."""
    _current_context.reset(token)


def current_model_provider_policy_context() -> ModelProviderPolicyContext | None:
    """Return the principal bound to the current request/task, if any."""
    return _current_context.get()
