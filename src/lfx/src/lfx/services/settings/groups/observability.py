from pydantic import BaseModel, Field


class ObservabilitySettings(BaseModel):
    """Metrics exposure and historical record retention."""

    prometheus_enabled: bool = False
    """If set to True, Langflow will expose Prometheus metrics."""
    prometheus_port: int = 9090
    """The port on which Langflow will expose Prometheus metrics. 9090 is the default port."""

    # Background execution observability
    background_metrics_interval: int = 15
    """Seconds between background-execution DB-derived metric collector ticks."""
    background_worker_registry_interval_s: float = Field(default=10.0, gt=0)
    """How often a ``langflow worker`` refreshes its row in ``worker_registry``
    (idle or busy). This first-class idle heartbeat keeps ``last_heartbeat`` fresh
    during a long job and while idle; the online window is a multiple of this. The
    API-side collector derives the online/busy/idle gauges from these rows. Must
    be > 0."""
    background_worker_registry_retention_s: float = Field(default=3600.0, gt=0)
    """How long a stale ``worker_registry`` row (a crashed worker that never
    deregistered) is kept before the collector prunes it. Surfaces a crashed
    worker as offline for this window, then removes it so the roster does not
    accumulate dead owners across restarts. Must be > 0."""

    max_transactions_to_keep: int = 3000
    """The maximum number of transactions to keep in the database."""
    max_vertex_builds_to_keep: int = 3000
    """The maximum number of vertex builds to keep in the database."""
    max_vertex_builds_per_vertex: int = 50
    """The maximum number of builds to keep per vertex. Older builds will be deleted."""
    max_flow_version_entries_per_flow: int = 50
    """Max version history entries per flow. Oldest entries pruned on next snapshot.

    If retroactively lowered below the current count for a flow,
    the oldest entries are deleted only when the next entry is created.
    """
