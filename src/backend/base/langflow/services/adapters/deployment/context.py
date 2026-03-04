from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

_current_deployment_provider_id: ContextVar[UUID | None] = ContextVar(
    "langflow_current_deployment_provider_id",
    default=None,
)


@contextmanager
def deployment_provider_scope(provider_id: UUID):
    token = _current_deployment_provider_id.set(provider_id)
    try:
        yield
    finally:
        _current_deployment_provider_id.reset(token)


def get_current_deployment_provider_id() -> UUID | None:
    return _current_deployment_provider_id.get()
