"""Trusted identity for connection metadata requested from component configuration hooks."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from lfx.services.authorization.base import ExecutionPrincipal

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID

_principal: ContextVar[ExecutionPrincipal | None] = ContextVar("connection_configuration_principal", default=None)


@contextmanager
def connection_configuration_context(*, user_id: UUID | str) -> Iterator[None]:
    """Resolve metadata as the authenticated caller for this hook only."""
    token = _principal.set(
        ExecutionPrincipal(
            kind="actor",
            user_id=str(user_id),
            actor_id=str(user_id),
            family="component_configuration",
            interactive=True,
        )
    )
    try:
        yield
    finally:
        _principal.reset(token)


def current_connection_configuration_principal() -> ExecutionPrincipal | None:
    return _principal.get()
