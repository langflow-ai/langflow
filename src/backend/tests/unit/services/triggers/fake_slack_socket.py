"""A local Slack Socket Mode endpoint for adapter tests.

``apps.connections.open`` is served through an ``httpx.MockTransport`` handed to
the adapter, and the socket it returns is a *real* WebSocket server on
127.0.0.1. So the adapter under test speaks the actual protocol over an actual
socket - hello, envelopes, acknowledgements, disconnect warnings, abrupt closes -
and every assertion is about frames that really crossed the wire.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from tests.unit.services.triggers import slack_fixtures as fx

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from typing_extensions import Self
    from websockets.asyncio.server import ServerConnection

API_BASE_URL = "https://slack.test/api"


def local_socket_url(url) -> bool:
    """Tests dial the fake on loopback; production only ever dials ``wss://*.slack.com``."""
    return url.scheme == "ws" and url.hostname == "127.0.0.1"


@dataclass(eq=False)
class FakeSocket:
    """One socket the adapter opened, as the server sees it."""

    ws: ServerConnection
    received: list[dict[str, Any]] = field(default_factory=list)
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    _arrived: asyncio.Event = field(default_factory=asyncio.Event)

    async def send(self, frame: dict[str, Any]) -> None:
        await self.ws.send(json.dumps(frame))

    async def deliver(self, body: dict[str, Any], *, envelope_id: str, retry_attempt: int = 0) -> None:
        await self.send(fx.socket_envelope(body, envelope_id=envelope_id, retry_attempt=retry_attempt))

    def acked(self, envelope_id: str) -> bool:
        return any(frame.get("envelope_id") == envelope_id for frame in self.received)

    async def wait_for_ack(self, envelope_id: str, *, timeout: float = 5.0) -> bool:
        """True once the adapter acknowledged ``envelope_id``; False on timeout."""
        deadline = asyncio.get_running_loop().time() + timeout
        while not self.acked(envelope_id):
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return False
            self._arrived.clear()
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(self._arrived.wait(), timeout=remaining)
        return True

    async def drop(self) -> None:
        """Close the socket abruptly, as a network failure would."""
        await self.ws.close(code=1011, reason="gone")


class FakeSlackSocketMode:
    """``apps.connections.open`` plus a real WebSocket server speaking Socket Mode."""

    def __init__(self, *, app_id: str = fx.APP_ID) -> None:
        self.app_id = app_id
        #: Overrides ``hello.num_connections``; ``None`` reports the real count.
        self.num_connections: int | None = None
        #: ``(status, json)`` answers for ``apps.connections.open``, used in order
        #: before the fake starts handing out socket URLs.
        self.open_errors: list[tuple[int, dict[str, Any]]] = []
        self.open_calls = 0
        self.authorizations: list[str] = []
        self.sockets: list[FakeSocket] = []
        #: Called with each acknowledged ``envelope_id`` as it arrives, before
        #: the ack is recorded - where a test checks what was committed by then.
        self.on_ack: Callable[[str], Awaitable[None]] | None = None
        self._opened = asyncio.Event()
        self._server = None
        self._port = 0

    async def __aenter__(self) -> Self:
        self._server = await serve(self._handle, "127.0.0.1", 0)
        self._port = next(iter(self._server.sockets)).getsockname()[1]
        return self

    async def __aexit__(self, *_exc) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._open)

    def live(self) -> list[FakeSocket]:
        return [socket for socket in self.sockets if not socket.closed.is_set()]

    async def wait_for_sockets(self, count: int, *, timeout: float = 5.0) -> list[FakeSocket]:
        """Wait until at least ``count`` sockets have been opened in total."""
        deadline = asyncio.get_running_loop().time() + timeout
        while len(self.sockets) < count:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                msg = f"expected {count} socket(s), the adapter opened {len(self.sockets)}"
                raise AssertionError(msg)
            self._opened.clear()
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(self._opened.wait(), timeout=remaining)
        return self.sockets

    def _open(self, request: httpx.Request) -> httpx.Response:
        self.open_calls += 1
        self.authorizations.append(request.headers.get("Authorization", ""))
        if request.url.path != "/api/apps.connections.open":
            return httpx.Response(404, json={"ok": False, "error": "unknown_method"})
        if self.open_errors:
            status, body = self.open_errors.pop(0)
            return httpx.Response(status, json=body)
        return httpx.Response(
            200, json={"ok": True, "url": f"ws://127.0.0.1:{self._port}/link/?ticket={self.open_calls}"}
        )

    async def _handle(self, ws: ServerConnection) -> None:
        socket = FakeSocket(ws=ws)
        self.sockets.append(socket)
        self._opened.set()
        live = len(self.live())
        await ws.send(
            json.dumps(
                {
                    "type": "hello",
                    "num_connections": self.num_connections if self.num_connections is not None else live,
                    "connection_info": {"app_id": self.app_id},
                    "debug_info": {"host": "applink-test", "approximate_connection_time": 18060},
                }
            )
        )
        try:
            async for raw in ws:
                frame = json.loads(raw)
                if self.on_ack is not None and isinstance(frame.get("envelope_id"), str):
                    await self.on_ack(frame["envelope_id"])
                socket.received.append(frame)
                socket._arrived.set()
        except ConnectionClosed:
            pass
        finally:
            socket.closed.set()
