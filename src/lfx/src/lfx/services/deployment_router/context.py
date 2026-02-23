"""Request-scoped deployment provider context for adapter calls."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

_current_deployment_provider_id: ContextVar[UUID | None] = ContextVar(
    "current_deployment_provider_id",
    default=None,
)


def set_current_deployment_provider_id(provider_id: UUID) -> None:
    _current_deployment_provider_id.set(provider_id)


def get_current_deployment_provider_id() -> UUID | None:
    return _current_deployment_provider_id.get()



