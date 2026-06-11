from typing import Literal

from pydantic import BaseModel


class TelemetrySettings(BaseModel):
    """Telemetry, error tracking, and tracing settings."""

    # Sentry
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float | None = 1.0
    sentry_profiles_sample_rate: float | None = 1.0

    # Telemetry
    do_not_track: bool = False
    """If set to True, Langflow will not track telemetry."""
    telemetry_base_url: str = "https://langflow.gateway.scarf.sh"

    transactions_storage_enabled: bool = True
    """If set to True, Langflow will track transactions between flows."""
    vertex_builds_storage_enabled: bool = True
    """If set to True, Langflow will keep track of each vertex builds (outputs) in the UI for any flow."""

    telemetry_writer_enabled: bool = True
    """Route transaction and vertex_build writes through an async batched writer backed by a
    disk-persisted outbox and a dedicated database connection. Eliminates SQLite
    'database is locked' errors and Postgres pool-timeouts under heavy load by keeping
    telemetry traffic off the request-handling connection pool.
    Set to False to fall back to the legacy direct-write path."""
    telemetry_writer_batch_size: int = 200
    """Maximum rows per batched INSERT executed by the telemetry writer."""
    telemetry_writer_flush_interval_s: float = 0.5
    """Maximum seconds the writer waits before flushing a partial batch."""
    telemetry_writer_cleanup_interval_s: int = 60
    """Cadence (seconds) of the retention sweeper that enforces max_transactions_to_keep
    and max_vertex_builds_to_keep. Retention is amortized rather than per-row to avoid
    inflating per-write cost."""
    telemetry_writer_max_queue: int = 100_000
    """Per-outbox cap. When exceeded, oldest entries are dropped and a counter is
    incremented. Bounds disk usage in pathological backlog scenarios."""
    telemetry_writer_outbox_dir: str | None = None
    """Directory for the disk-backed outbox. Defaults to
    <tempdir>/langflow_telemetry_outbox. Each worker process uses an isolated
    subdirectory keyed by PID; sibling subdirectories from crashed workers are
    automatically adopted on startup."""
    telemetry_writer_shutdown_drain_s: float = 5.0
    """Maximum seconds the writer waits to drain in-flight batches on shutdown
    before disposing the dedicated engine."""
    telemetry_writer_orphan_max_age_s: float = 3600.0
    """Cross-host orphan outboxes (e.g. dead pods on a shared volume) are pruned
    when their owner file hasn't been heartbeated within this many seconds.
    Same-host orphans are adopted regardless of age via owner-file identity."""
    telemetry_writer_size_strategy: Literal["count", "bytes", "either"] = "count"
    """How the writer bounds memory and flushes.

    - 'count' (default): preserve legacy row-count semantics. ``batch_size`` and
      ``max_queue`` are the only thresholds.
    - 'bytes': bound by the byte thresholds below; row caps are ignored.
    - 'either': whichever (rows or bytes) trips first wins. Recommended for
      deployments with variable payload sizes (large vertex_build artifacts,
      doc-loader outputs)."""
    telemetry_writer_batch_size_bytes: int = 262_144
    """Cap on per-flush batch size in *encoded JSON bytes*. Consulted when
    ``telemetry_writer_size_strategy`` is 'bytes' or 'either'. Sized around a
    single TCP frame so individual INSERTs stay below DB packet limits.

    Note: this measures the payload's serialized size, not Python's in-memory
    footprint (dicts carry significant overhead beyond their JSON form)."""
    telemetry_writer_max_queue_bytes: int = 209_715_200
    """Per-outbox cap in *encoded JSON bytes*. When exceeded under 'bytes' or
    'either' strategy, oldest entries are dropped until the buffer fits.
    Defaults to ~200MB so a single worker's telemetry buffer can't dominate
    container memory. As with ``batch_size_bytes`` this is serialized size, not
    Python in-memory size — actual RSS will be 2-5x higher."""

    deactivate_tracing: bool = False
    """If set to True, tracing will be deactivated."""
