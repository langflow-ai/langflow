import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from lfx.log.logger import logger


class RuntimeSettings(BaseModel):
    """Runtime behaviors: event delivery, worker timeouts, polling intervals, public flows, misc toggles.

    Note: ``event_delivery`` is validated here but reads ``workers`` from
    :class:`ServerSettings`. The composition order in :class:`Settings`
    guarantees ``workers`` is in ``info.data`` when this validator runs.
    """

    dev: bool = False
    """If True, Langflow will run in development mode."""

    # Job Queue
    job_queue_type: Literal["asyncio", "redis"] = "asyncio"
    """The job queue backend. Use 'redis' for multi-worker deployments to solve cross-worker JobQueueNotFoundError."""
    redis_queue_host: str | None = None
    """Redis host for the job queue. Falls back to redis_host if not set."""
    redis_queue_port: int | None = None
    """Redis port for the job queue. Falls back to redis_port if not set."""
    redis_queue_db: int = 1
    """Redis DB number for the job queue. Defaults to 1 to avoid conflict with the cache (DB 0)."""
    redis_queue_url: str | None = None
    """Full Redis URL for the job queue. Takes priority over host/port/db if set."""
    redis_queue_ttl: int = 3600
    """TTL in seconds for job stream keys in Redis."""
    redis_queue_startup_grace_s: float = Field(default=30.0, ge=0)
    """Seconds a cross-worker consumer waits for the producer's first XADD before
    treating a missing stream key as end-of-stream. Bump this if cold-start build
    latency on the producer worker can exceed the default (e.g. large graph
    instantiation, slow container image pulls). Negative values would make
    consumers treat a not-yet-created stream as EOF immediately, so values must
    be non-negative."""
    redis_queue_cancel_channel_enabled: bool = True
    """If True, RedisJobQueueService runs a single PSUBSCRIBE dispatcher per worker
    so POST /build/{job_id}/cancel works cross-worker. Any worker can publish a
    cancel signal; the owning worker cancels the local build task."""
    redis_queue_cancel_marker_ttl: int = Field(default=60, gt=0)
    """TTL in seconds for the persistent cancel-marker key used to close the race
    where a cancel signal is published before the owning worker's dispatcher
    subscribes or before the job is registered. Should comfortably exceed worker
    cold-start latency. Must be > 0: a non-positive TTL makes the marker
    ineffective and reopens the publish-before-subscribe race it closes."""
    redis_queue_polling_stale_threshold_s: float = Field(default=90.0, ge=0)
    """Maximum seconds a polling job may go without client activity before the
    watchdog publishes a cross-worker cancel. Polling clients have no persistent
    connection, so the server detects abandonment by tracking the most recent
    poll (or streaming-response heartbeat). Set to 0 to disable the watchdog."""
    redis_queue_polling_watchdog_interval_s: float = Field(default=15.0, gt=0)
    """How often the polling watchdog scans owned jobs. Smaller values give
    faster reclamation of abandoned builds at the cost of more Redis GETs.
    The watchdog only checks jobs this worker owns (entries in self._queues).
    Must be > 0 so the scan loop makes progress."""

    event_delivery: Literal["polling", "streaming", "direct"] = "streaming"
    """How to deliver build events to the frontend. Can be 'polling', 'streaming' or 'direct'."""

    worker_timeout: int = 300
    """Timeout for the API calls in seconds."""

    public_flow_cleanup_interval: int = Field(default=3600, gt=600)
    """The interval in seconds at which public temporary flows will be cleaned up.
    Default is 1 hour (3600 seconds). Minimum is 600 seconds (10 minutes)."""
    public_flow_expiration: int = Field(default=86400, gt=600)
    """The time in seconds after which a public temporary flow will be considered expired and eligible for cleanup.
    Default is 24 hours (86400 seconds). Minimum is 600 seconds (10 minutes)."""

    webhook_polling_interval: int = 0
    """The polling interval for the webhook in ms. Set to 0 to disable (SSE provides real-time updates)."""
    fs_flows_polling_interval: int = 10000
    """The polling interval in milliseconds for synchronizing flows from the file system."""

    collaboration_heartbeat_interval: float = 45.0
    """Seconds between heartbeat ping cycles for each collaboration WebSocket connection."""
    collaboration_heartbeat_stagger: float = 1.0
    """Seconds to wait between stagger buckets while scheduling heartbeat pings."""
    collaboration_heartbeat_timeout: float = 10.0
    """Seconds a client has to respond with heartbeat.pong after a ping."""
    collaboration_connection_ttl: float = 90.0
    """SQLite presence TTL for an active collaboration connection row."""
    collaboration_presence_snapshot_interval: float = 120.0
    """Seconds between full collaboration presence snapshots used as a fallback reconcile."""
    collaboration_max_connections: int = 100
    """Maximum local collaboration connections included in one heartbeat scheduling cycle."""

    health_check_max_retries: int = 5
    """The maximum number of retries for the health check."""

    max_file_size_upload: int = 1024
    """The maximum file size for the upload in MB."""

    max_ingestion_timeout_secs: int = 600

    celery_enabled: bool = False

    @field_validator("event_delivery", mode="before")
    @classmethod
    def set_event_delivery(cls, value, info):
        # Multi-worker deployments with the in-memory job queue cannot route
        # ``polling`` or ``streaming`` responses correctly: build events live in
        # the in-process queue of whichever worker started the job, and a later
        # poll/stream request may land on a different worker.  Switch to Redis
        # (LANGFLOW_JOB_QUEUE_TYPE=redis) to share state across workers, or
        # accept ``direct`` delivery which keeps the whole exchange on one
        # worker.  The override below preserves backwards compatibility for
        # deployments that haven't set this explicitly; new explicit values are
        # logged loudly so the cause is easy to diagnose if the UI loses events.
        if info.data.get("workers", 1) > 1 and info.data.get("job_queue_type", "asyncio") != "redis":
            requested = value or "polling"
            if requested != "direct":
                logger.warning(
                    "Multi-worker mode without a Redis-backed job queue cannot deliver "
                    "'%s' events across workers; forcing event_delivery='direct'. "
                    "Set LANGFLOW_JOB_QUEUE_TYPE=redis to keep '%s' delivery in multi-worker setups.",
                    requested,
                    requested,
                )
            return "direct"
        return value

    @field_validator(
        "collaboration_heartbeat_interval",
        "collaboration_heartbeat_stagger",
        "collaboration_heartbeat_timeout",
        "collaboration_connection_ttl",
        "collaboration_presence_snapshot_interval",
    )
    @classmethod
    def validate_collaboration_positive_float(cls, value: float) -> float:
        if value <= 0:
            msg = "collaboration timing values must be positive"
            raise ValueError(msg)
        return value

    @field_validator("collaboration_max_connections")
    @classmethod
    def validate_collaboration_max_connections(cls, value: int) -> int:
        if value <= 0:
            msg = "collaboration_max_connections must be a positive integer"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_collaboration_heartbeat_scheduler(self):
        stagger = self.collaboration_heartbeat_stagger
        interval = self.collaboration_heartbeat_interval
        if stagger >= interval:
            msg = "collaboration_heartbeat_stagger must be less than collaboration_heartbeat_interval"
            raise ValueError(msg)
        min_stagger_buckets = 2
        bucket_count = math.ceil(interval / stagger)
        if bucket_count < min_stagger_buckets:
            msg = (
                "collaboration heartbeat scheduler requires at least two stagger buckets "
                "within collaboration_heartbeat_interval"
            )
            raise ValueError(msg)
        return self
