from typing import Literal

from pydantic import BaseModel, Field, field_validator

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

    workflow_execution_timeout: int = 300
    """Wall-clock ceiling in seconds for a single v2 workflow run, applied to every
    execution mode. Sync runs raise a 408; stream, background, and public runs emit
    the protocol's terminal-error event and (for background) mark the job failed."""

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

    health_check_max_retries: int = 5
    """The maximum number of retries for the health check."""

    max_file_size_upload: int = 1024
    """The maximum file size for the upload in MB."""

    max_ingestion_timeout_secs: int = 600

    celery_enabled: bool = False

    executor_kind: str = "in-process"
    """The default executor kind used by the execution coordinator.

    Must match the `kind` of an Executor registered with the executor service. The built-in
    `in-process` executor runs graphs in the current process; third-party executors registered
    via the `lfx.executors` entry-point group can be selected by setting this to their kind.
    """

    deployment_list_sync_batch_size: int = Field(default=500, ge=1)
    """Max local deployment rows checked against the provider in one list request.

    The deployment list endpoint in Langflow, GET /api/v1/deployments,
    prunes any local DB rows representing deployments that have been deleted
    in the provider. This can involve multiple provider API calls before
    filling the page size requested to Langflow, because deployments might
    have been pruned. If each provider API call only uses the
    page-size-requested-to-langflow many deployments, then the number of
    provider requests (bounded by deployment_list_sync_max_rounds) can be high
    and result in a slow API response from Langflow to the requestor. Thus, it
    is recommended to make the batch size larger than the requested page size
    to Langflow to reduce the number of provider API calls.
    """

    deployment_list_sync_max_rounds: int = Field(default=2, ge=1)
    """Max provider validation rounds used to fill one deployment-list response.

    When GET /api/v1/deployments checks local deployment rows against a provider,
    some rows might be pruned before they can be returned to the requestor.
    If enough rows are pruned, Langflow can make another provider API call
    using the next local DB rows after the last checked deployment.
    This setting limits how many of those provider API calls Langflow can make
    while trying to fill a single requested page.
    """

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
