"""The two paths a listener serves, and the three ways it reports itself unready.

A liveness probe cannot see the failure that matters here: the process answers,
the task is alive, and nothing is being claimed. So readiness checks the
database, the freshness of the reconcile loop, and whether a lease renewal
failed inside the last TTL - and these tests check that each one can actually
turn the probe red.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.deps import get_settings_service
from langflow.services.triggers.listeners.health import ListenerHealthServer, readiness
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor

pytestmark = pytest.mark.no_blockbuster


class _AliveSupervisor(ListenerSupervisor):
    """A supervisor that reports a healthy reconcile without running a loop."""

    def __init__(self) -> None:
        super().__init__(holder="probe-test")
        self.last_reconcile_at = datetime.now(timezone.utc)

    @property
    def running(self) -> bool:
        return True


async def _get(port: int, path: str) -> tuple[int, dict]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=5)
    writer.close()
    head, _, body = raw.partition(b"\r\n\r\n")
    status = int(head.split(b"\r\n")[0].split()[1])
    return status, json.loads(body or b"{}")


@pytest.fixture
async def health_server(client):  # noqa: ARG001 - the client fixture stands up the database
    supervisor = _AliveSupervisor()
    server = ListenerHealthServer(supervisor, host="127.0.0.1", port=0)
    await server.start()
    try:
        yield server, supervisor
    finally:
        await server.stop()


async def test_health_is_alive_and_healthz_is_ready(health_server) -> None:
    server, _supervisor = health_server

    status, body = await _get(server.bound_port, "/health")
    assert status == 200
    assert body["status"] == "alive"

    status, body = await _get(server.bound_port, "/healthz")
    assert status == 200
    assert body["status"] == "ready"
    assert body["database"] == "ok"
    assert body["leases"] == "ok"
    assert body["reconcile"] == "ok"


async def test_the_listener_serves_nothing_else(health_server) -> None:
    """No router, no API surface: two GET paths and a 404."""
    server, _supervisor = health_server

    status, _body = await _get(server.bound_port, "/api/v1/flows")
    assert status == 404

    reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_port)
    writer.write(b"POST /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=5)
    writer.close()
    assert b"405" in raw.split(b"\r\n")[0]


async def test_a_stale_reconcile_loop_turns_readiness_red(health_server) -> None:
    server, supervisor = health_server
    settings = get_settings_service().settings
    stale_by = max(settings.listener_reconcile_interval_s * 4, settings.listener_lease_ttl_s) + 60
    supervisor.last_reconcile_at = datetime.now(timezone.utc) - timedelta(seconds=stale_by)

    status, body = await _get(server.bound_port, "/healthz")
    assert status == 503
    assert body["reconcile"] == "stale"
    assert body["status"] == "not_ready"


async def test_a_failed_lease_renewal_turns_readiness_red(health_server) -> None:
    server, supervisor = health_server
    supervisor.last_renew_failure_at = datetime.now(timezone.utc)

    status, body = await _get(server.bound_port, "/healthz")
    assert status == 503
    assert body["leases"] == "renew_failed"

    # It clears itself once the failure is older than one TTL.
    ttl = get_settings_service().settings.listener_lease_ttl_s
    supervisor.last_renew_failure_at = datetime.now(timezone.utc) - timedelta(seconds=ttl + 5)
    status, body = await _get(server.bound_port, "/healthz")
    assert status == 200
    assert body["leases"] == "ok"


async def test_an_unreachable_database_turns_readiness_red(client, monkeypatch) -> None:  # noqa: ARG001
    supervisor = _AliveSupervisor()

    async def _down() -> bool:
        return False

    monkeypatch.setattr("langflow.services.triggers.listeners.health._database_ok", _down)
    ready, body = await readiness(supervisor)
    assert ready is False
    assert body["database"] == "unreachable"


async def test_a_supervisor_that_is_not_running_is_never_ready(client) -> None:  # noqa: ARG001
    supervisor = ListenerSupervisor(holder="stopped")
    supervisor.last_reconcile_at = datetime.now(timezone.utc)
    ready, body = await readiness(supervisor)
    assert ready is False
    assert body["running"] is False
