"""Connection-pool saturation is only observable while the pool is live.

These drive a real ``AsyncEngine`` -- the same type ``get_db_service().engine`` returns -- with
real connections, rather than a stand-in exposing a ``.pool`` attribute. That matters: the
instrumentation reads ``engine.pool`` and silently returns when it is absent, so a stand-in
would keep every assertion green even if ``AsyncEngine`` did not proxy the attribute at all and
the feature were a no-op in production.
"""

import tempfile
from pathlib import Path

from langflow.services.telemetry.opentelemetry import DB_POOL_GAUGES, instrument_db_pool
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool


def _collect(reader) -> dict[str, float]:
    # None rather than an empty payload is what the reader returns when nothing was ever
    # registered, which is itself the assertion in the StaticPool case below.
    data = reader.get_metrics_data()
    if data is None:
        return {}
    return {
        metric.name: point.value
        for rm in (data.resource_metrics or [])
        for sm in rm.scope_metrics
        for metric in sm.metrics
        for point in metric.data.data_points
    }


def _provider_with_reader() -> tuple[MeterProvider, InMemoryMetricReader]:
    reader = InMemoryMetricReader()
    return MeterProvider(metric_readers=[reader], shutdown_on_exit=False), reader


async def test_checkout_from_a_real_async_engine_moves_the_in_use_gauge():
    """The signal an operator needs during a pool-exhaustion incident.

    Uses a counting pool explicitly, because the counters only exist on the queue pools that
    real Postgres deployments get.
    """
    provider, reader = _provider_with_reader()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=AsyncAdaptedQueuePool, pool_size=5, max_overflow=2
    )
    try:
        instrument_db_pool(provider, engine)
        assert _collect(reader)["langflow_db_pool_connections_in_use"] == 0

        async with engine.connect():
            assert _collect(reader)["langflow_db_pool_connections_in_use"] == 1

        # Returned to the pool, not destroyed: in use falls back, idle now holds it.
        collected = _collect(reader)
        assert collected["langflow_db_pool_connections_in_use"] == 0
        assert collected["langflow_db_pool_connections_idle"] == 1
        assert collected["langflow_db_pool_size"] == 5
        # A pool well within its size reports a negative overflow internally; the gauge must
        # not surface that, or a dashboard shows -5 as the healthy baseline.
        assert collected["langflow_db_pool_overflow"] == 0
    finally:
        await engine.dispose()
        provider.shutdown()


async def test_pools_that_count_nothing_register_nothing():
    """SQLite is the default and uses StaticPool, which has none of these counters.

    Registering a gauge whose callback cannot work would emit a permanently-zero series and,
    worse, make a pool look healthy on a deployment where it is simply not measured.
    """
    provider, reader = _provider_with_reader()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        instrument_db_pool(provider, engine)
        assert not [name for name, *_ in DB_POOL_GAUGES if name in _collect(reader)]
    finally:
        await engine.dispose()
        provider.shutdown()


async def test_instrumenting_without_a_provider_is_a_noop():
    """Nothing exported means nothing to register on; must not raise."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=AsyncAdaptedQueuePool)
    try:
        instrument_db_pool(None, engine)
    finally:
        await engine.dispose()


async def test_gauges_follow_the_pool_across_a_dispose():
    """dispose() swaps in a fresh pool rather than resetting one in place.

    A gauge holding the original pool would answer for the dead one forever, reporting a
    permanently healthy zero after any reconnect -- the exact false-healthy reading these
    exist to prevent.
    """
    provider, reader = _provider_with_reader()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=AsyncAdaptedQueuePool, pool_size=5)
    try:
        instrument_db_pool(provider, engine)
        original_pool = engine.pool

        await engine.dispose()
        assert engine.pool is not original_pool, "sqlalchemy no longer swaps the pool; test premise is stale"

        async with engine.connect():
            assert _collect(reader)["langflow_db_pool_connections_in_use"] == 1
    finally:
        await engine.dispose()
        provider.shutdown()


async def test_file_backed_sqlite_is_instrumented():
    """The default deployment is file-backed SQLite, which does get a counting pool.

    Only ``:memory:`` uses StaticPool, so this is the branch that actually runs for most
    installs and it must not be left to the memory-only tests above.
    """
    provider, reader = _provider_with_reader()
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_async_engine(f"sqlite+aiosqlite:///{Path(tmp) / 'langflow.db'}", pool_size=20, max_overflow=30)
        try:
            instrument_db_pool(provider, engine)
            collected = _collect(reader)
            assert collected["langflow_db_pool_size"] == 20
            # overflow() starts at -pool_size on a queue pool; the clamp must hide that.
            assert collected["langflow_db_pool_overflow"] == 0
        finally:
            await engine.dispose()
            provider.shutdown()


async def test_gauges_retarget_when_the_whole_engine_is_replaced():
    """Re-instrumenting with a replacement engine must move the gauges to it.

    OpenTelemetry de-duplicates observable gauges by name, so the second registration returns
    the existing instrument and drops the new callbacks. If the engine were captured per
    callback, the gauges would keep reporting on the first, disposed engine -- a permanently
    healthy pool for one that no longer exists. Swapping only ``engine.pool`` does not catch
    this; the whole engine has to be replaced.
    """
    provider, reader = _provider_with_reader()
    first = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=AsyncAdaptedQueuePool, pool_size=5)
    second = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=AsyncAdaptedQueuePool, pool_size=5)
    try:
        instrument_db_pool(provider, first)
        instrument_db_pool(provider, second)

        # Hold a connection on the replacement only. A gauge still bound to `first` reports 0.
        async with second.connect():
            assert _collect(reader)["langflow_db_pool_connections_in_use"] == 1
    finally:
        await first.dispose()
        await second.dispose()
        provider.shutdown()
