"""Connection-pool saturation is only observable while the pool is live.

These drive a real SQLAlchemy pool with real connections rather than a stand-in, because the
whole value of the gauges is that they read the pool's own counters at collection time. A
mocked pool would assert that the plumbing calls a method, which is not the thing that breaks.
"""

import sqlite3
from types import SimpleNamespace

from langflow.services.telemetry.opentelemetry import DB_POOL_GAUGES, instrument_db_pool
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from sqlalchemy.pool import QueuePool, StaticPool


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


def test_queue_pool_checkout_moves_the_in_use_gauge():
    """The signal an operator needs during a pool-exhaustion incident."""
    provider, reader = _provider_with_reader()
    pool = QueuePool(lambda: sqlite3.connect(":memory:"), pool_size=5, max_overflow=2)

    instrument_db_pool(provider, SimpleNamespace(pool=pool))

    assert _collect(reader).get("langflow_db_pool_connections_in_use") == 0

    connection = pool.connect()
    try:
        assert _collect(reader)["langflow_db_pool_connections_in_use"] == 1
    finally:
        connection.close()

    # Returned to the pool, not destroyed: in use falls back, idle now holds it.
    collected = _collect(reader)
    assert collected["langflow_db_pool_connections_in_use"] == 0
    assert collected["langflow_db_pool_connections_idle"] == 1
    assert collected["langflow_db_pool_size"] == 5
    provider.shutdown()


def test_pools_that_count_nothing_register_nothing():
    """SQLite is the default and uses StaticPool, which has none of these counters.

    Registering a gauge whose callback cannot work would emit a permanently-zero series and,
    worse, make a pool look healthy on a deployment where it is simply not measured.
    """
    provider, reader = _provider_with_reader()

    instrument_db_pool(provider, SimpleNamespace(pool=StaticPool(lambda: sqlite3.connect(":memory:"))))

    assert not [name for name, *_ in DB_POOL_GAUGES if name in _collect(reader)]
    provider.shutdown()


def test_instrumenting_without_a_provider_is_a_noop():
    """Nothing exported means nothing to register on; must not raise."""
    instrument_db_pool(None, SimpleNamespace(pool=QueuePool(lambda: sqlite3.connect(":memory:"))))
