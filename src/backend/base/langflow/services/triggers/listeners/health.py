"""The only thing a listener process serves.

``/health`` is liveness: the process is up and its reconcile loop is a task that
has not died. ``/healthz`` is readiness: the database answers, the supervisor
reconciled recently, and no lease renewal has failed inside the last TTL - the
three ways a listener can be running and useless at the same time.

This is a hand-rolled asyncio HTTP server rather than a FastAPI app, and that is
the point. ``decisions/process-model.md`` says the boot path asserts that no
FastAPI app is created here, so the health endpoint cannot be the exception that
quietly reintroduces one; ``langflow.services.triggers.listeners.guard`` makes
building one an error. The surface is two GET paths and nothing else: no router,
no middleware, no authentication surface to get wrong.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from sqlalchemy import text

from langflow.services.deps import get_settings_service, session_scope

if TYPE_CHECKING:
    from langflow.services.triggers.listeners.supervisor import ListenerSupervisor

#: Cap on the request line plus headers we will read before giving up. A health
#: port is unauthenticated by design, so the reader is bounded.
_MAX_REQUEST_BYTES = 8192
_READ_TIMEOUT_S = 5.0
#: "GET /healthz HTTP/1.1" - method and path are all we parse.
_MIN_REQUEST_LINE_PARTS = 2


async def _database_ok() -> bool:
    try:
        async with session_scope() as session:
            await session.exec(text("SELECT 1"))  # type: ignore[call-overload]
    except Exception as exc:  # noqa: BLE001 - any failure is "not ready"
        await logger.adebug("Listener readiness probe failed: %s", type(exc).__name__)
        return False
    return True


async def readiness(supervisor: ListenerSupervisor) -> tuple[bool, dict[str, Any]]:
    """Is this listener doing its job? Returns ``(ready, body)``."""
    settings = get_settings_service().settings
    body = supervisor.snapshot()

    database_ok = await _database_ok()
    body["database"] = "ok" if database_ok else "unreachable"

    renew_ok = True
    if supervisor.last_renew_failure_at is not None:
        from langflow.services.triggers.listeners.supervisor import _now

        age = (_now() - supervisor.last_renew_failure_at).total_seconds()
        renew_ok = age > settings.listener_lease_ttl_s
    body["leases"] = "ok" if renew_ok else "renew_failed"

    # A reconcile loop that stopped reconciling is the failure a liveness probe
    # cannot see: the task is alive, the process answers, and nothing is being
    # claimed. Allow four intervals before calling it stale so an unlucky slow
    # pass does not flap the pod out of the service.
    stale_after = max(settings.listener_reconcile_interval_s * 4, settings.listener_lease_ttl_s)
    reconcile_ok = supervisor.last_reconcile_at is not None
    if reconcile_ok:
        from langflow.services.triggers.listeners.supervisor import _now

        reconcile_ok = (_now() - supervisor.last_reconcile_at).total_seconds() <= stale_after
    body["reconcile"] = "ok" if reconcile_ok else "stale"

    ready = bool(supervisor.running and database_ok and renew_ok and reconcile_ok)
    body["status"] = "ready" if ready else "not_ready"
    return ready, body


def _response(status: int, reason: str, body: dict[str, Any]) -> bytes:
    payload = json.dumps(body).encode()
    headers = (
        f"HTTP/1.1 {status} {reason}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    return headers + payload


class ListenerHealthServer:
    """Two GET paths on one port, started and stopped with the supervisor."""

    def __init__(self, supervisor: ListenerSupervisor, *, host: str | None = None, port: int | None = None) -> None:
        settings = get_settings_service().settings
        self.supervisor = supervisor
        self.host = host or settings.listeners_health_host
        self.port = port if port is not None else settings.listeners_health_port
        self._server: asyncio.AbstractServer | None = None

    @property
    def bound_port(self) -> int | None:
        """The port actually bound, which differs from ``port`` when it was 0."""
        if self._server is None or not self._server.sockets:
            return None
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, host=self.host, port=self.port)
        await logger.ainfo("Listener health endpoint on http://%s:%s/health", self.host, self.bound_port)

    async def stop(self) -> None:
        server, self._server = self._server, None
        if server is None:
            return
        server.close()
        await server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                request_line = await asyncio.wait_for(reader.readline(), timeout=_READ_TIMEOUT_S)
            except (TimeoutError, asyncio.TimeoutError):
                return
            if not request_line or len(request_line) > _MAX_REQUEST_BYTES:
                return
            parts = request_line.decode("latin-1").split()
            method, path = (parts[0], parts[1].split("?", 1)[0]) if len(parts) >= _MIN_REQUEST_LINE_PARTS else ("", "")

            if method != "GET":
                writer.write(_response(405, "Method Not Allowed", {"error": "method_not_allowed"}))
            elif path == "/health":
                # A reconcile task that died leaves a process that answers and
                # holds nothing. The liveness probe compares status codes, so
                # saying 200 here is how a useless listener stays scheduled
                # forever instead of being restarted.
                running = self.supervisor.running
                body = {"status": "alive" if running else "stopped", "running": running}
                writer.write(_response(200, "OK", body) if running else _response(503, "Service Unavailable", body))
            elif path == "/healthz":
                ready, body = await readiness(self.supervisor)
                writer.write(_response(200, "OK", body) if ready else _response(503, "Service Unavailable", body))
            else:
                writer.write(_response(404, "Not Found", {"error": "not_found"}))
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):  # pragma: no cover - probe hung up
            return
        except Exception as exc:  # noqa: BLE001 - one bad probe must not end the server
            await logger.adebug("Listener health request failed: %s", type(exc).__name__)
        finally:
            writer.close()
            with contextlib.suppress(ConnectionResetError, BrokenPipeError, TimeoutError, asyncio.TimeoutError):
                await writer.wait_closed()
