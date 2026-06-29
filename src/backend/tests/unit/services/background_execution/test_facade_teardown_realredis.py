"""Real-redis: the scaled facade closes its background-execution redis client.

In scaled mode the facade builds a StrictRedis client for the redis backend
(``self._backend._client``). The worker process closes its own client on
teardown, but the API replica used to leak its background-execution connection
pool on shutdown because ``teardown()``/``stop()`` only stopped the executor and
never touched the backend. This drives the facade's ``teardown()`` against a real
redis backend and asserts the backend's real client-close ran.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_facade_teardown_closes_scaled_backend_client(real_redis, real_redis_url):  # noqa: ARG001
    from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service
    from redis.asyncio import StrictRedis

    client = StrictRedis.from_url(real_redis_url)
    await client.ping()
    # Capture the live pooled connection so we can prove it was disconnected.
    pooled = client.connection_pool._available_connections[0]
    assert pooled._writer is not None

    # Thin instrumented subclass: records that the REAL teardown ran (still calls
    # the production close), mirroring the _CountingJobService probe pattern. Not
    # a mock of our logic — the real client.aclose() executes.
    class _ProbedBackend(RedisBackgroundQueue):
        teardown_calls = 0

        async def teardown(self) -> None:
            type(self).teardown_calls += 1
            await super().teardown()

    backend = _ProbedBackend(client=client, job_service=None, stream_ttl=60, startup_grace_s=10.0)
    svc = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend)
    assert svc._scaled is True

    await svc.teardown()

    # The facade reached the backend's teardown, which closed the real client.
    assert _ProbedBackend.teardown_calls == 1, "facade teardown did not close the scaled backend client"
    # The real aclose() disconnected the live pooled connection (writer dropped).
    assert pooled._writer is None, "scaled backend client connection was not disconnected on teardown"
