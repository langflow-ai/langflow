"""Keep shared graph text only while an ASGI response still uses its lease."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from starlette.responses import Response

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

    from langflow.services.flow_multiplayer.cache import SerializedGraph


class _Consumers:
    def __init__(self) -> None:
        self.leases: list[SerializedGraph] = []
        self.closed = False

    def add(self, lease: SerializedGraph) -> bool:
        if self.closed:
            return False
        self.leases.append(lease)
        return True

    def close(self) -> None:
        self.closed = True
        for lease in self.leases:
            lease.close()
        self.leases.clear()


_consumers: ContextVar[_Consumers | None] = ContextVar("graph_serialization_consumers", default=None)


def hold_for_response(lease: SerializedGraph) -> bool:
    """Register a read lease in the live outer response scope, when present."""
    consumers = _consumers.get()
    if consumers is None:
        return False
    if not consumers.add(lease):
        lease.close()
        message = "The graph read's HTTP response scope has already ended."
        raise RuntimeError(message)
    return True


class SerializationResponseMiddleware:
    """Release read leases after outer sending, errors, disconnects or cancellation.

    Register this last so it wraps BaseHTTPMiddleware and compression. Their
    inner responses can finish before the actual outer body has been sent.
    The mutable registry is shared by the child tasks those middleware create.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        consumers = _Consumers()
        token = _consumers.set(consumers)
        try:
            await self.app(scope, receive, send)
        finally:
            consumers.close()
            _consumers.reset(token)


class SerializedGraphResponse(Response):
    """Response-bound fallback for a router mounted without the outer middleware."""

    def __init__(self, content: bytes, *, lease: SerializedGraph, **kwargs: Any) -> None:
        super().__init__(content, **kwargs)
        self._lease = lease

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._lease.close()
