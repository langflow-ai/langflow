from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from lfx.log.logger import logger


class RuntimeSettings(BaseModel):
    """Runtime behaviors: event delivery, worker timeouts, polling intervals, public flows, misc toggles.

    Note: ``event_delivery`` is validated here but reads ``workers`` from
    :class:`ServerSettings`. The composition order in :class:`Settings`
    guarantees ``workers`` is in ``info.data`` when this validator runs.
    """

    warm_registry_enabled: bool = False
    """Enable the process-local warm graph registry (LANGFLOW_WARM_REGISTRY_ENABLED)."""

    warm_registry_preload_limit: int = Field(default=0, ge=0)
    """Maximum flows each worker eagerly preloads (LANGFLOW_WARM_REGISTRY_PRELOAD_LIMIT).

    The safe default is zero: flows warm lazily after an authorized request, so
    enabling the cache on a shared cluster cannot make every worker materialize
    every tenant's saved graph. Dedicated trusted execution workers may opt into
    a bounded preload. Must be >= 0.
    """

    warm_registry_max_entries: int = Field(default=128, gt=0)
    """Maximum resident flow templates per worker (LANGFLOW_WARM_REGISTRY_MAX_ENTRIES)."""

    warm_registry_max_flow_bytes: int = Field(default=2_000_000, gt=0)
    """Maximum serialized retained execution snapshot eligible for warming, in bytes."""

    warm_registry_max_total_bytes: int = Field(default=32_000_000, gt=0)
    """Maximum total serialized execution-snapshot bytes retained or in flight per worker."""

    dev: bool = False
    """If True, Langflow will run in development mode."""

    warm_reconcile_interval: float = Field(default=20.0, gt=0)
    """Seconds between warm-registry reconcile passes (LANGFLOW_WARM_RECONCILE_INTERVAL).

    Each execution machine independently diffs its in-memory registry against the
    shared ``flow`` table every ``interval`` seconds, so a deploy or delete takes up
    to this long to propagate across the fleet. Lower for faster convergence at the
    cost of more manifest queries. Only used when ``warm_registry_enabled`` is true.
    Must be > 0."""

    # Job Queue
    job_queue_type: Literal["asyncio", "redis"] = "asyncio"
    """The job queue backend. Use 'redis' for multi-worker deployments to solve cross-worker JobQueueNotFoundError."""
    dangerously_allow_multi_worker_without_shared_queue: bool = False
    """Opt out of the startup guard that refuses ``workers > 1`` with the default
    in-memory job queue.

    Off by default. Enabling it lets headless deployments take multi-worker
    throughput without standing up Redis, at the cost of every behavior that
    needs process-shared state: the v1 ``/build`` editor and playground flows and
    MCP over SSE stop working, and rate limiting, webhook UI feedback, and the
    orphan sweep degrade to per-worker or per-node. ``LANGFLOW_JOB_QUEUE_TYPE=redis``
    remains the supported way to run multiple workers; see
    ``langflow.__main__.ensure_multi_worker_safe`` for the full list of caveats
    logged when the bypass is active."""
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

    # Background execution (v2 workflows background mode)
    background_max_concurrency: int = Field(default=5, gt=0)
    """Max number of background workflow jobs the in-process executor runs
    concurrently. Jobs beyond this queue and start as workers free up. Kept
    small by default so background runs cannot starve the request event loop;
    raise it for dedicated worker processes. The redis backend ignores this in
    favor of its own worker-process pool. Must be > 0."""
    background_job_timeout: float | None = None
    """Wall-clock seconds a single background job may run before it is marked
    TIMED_OUT. ``None`` (default) means no timeout. Applies per job, enforced by
    the runner via ``asyncio.wait_for`` around the build loop."""
    background_input_deadline_s: float | None = None
    """Optional wall-clock seconds a background run may stay SUSPENDED (awaiting human
    input) before it is given up on. Independent of ``background_job_timeout``: paused
    time never accrues against the compute timeout (resume re-enqueues a fresh pass).
    ``None`` (default) disables the deadline — nothing is stamped, nothing enforced.
    Enforced by ``sweep_input_deadlines`` (startup sweep + the periodic watchdog when
    the setting is set), which FAILs overdue runs with an ``input_timed_out`` error."""
    background_lease_ttl_s: float = Field(default=45.0, gt=0)
    """Liveness lease window for a running background job. The running owner
    refreshes a heartbeat on the job row; a reconciler (startup sweep / scaled
    watchdog) only fails or requeues an IN_PROGRESS job whose heartbeat is older
    than this TTL (or never recorded). Must comfortably exceed
    ``background_heartbeat_interval_s`` so a healthy owner never looks stale."""
    background_heartbeat_interval_s: float = Field(default=15.0, gt=0)
    """How often a running background job refreshes its liveness heartbeat. Kept
    well below ``background_lease_ttl_s`` so a brief stall does not trip the
    reconciler. Must be > 0."""
    background_watchdog_interval_s: float = Field(default=15.0, gt=0)
    """How often the scaled worker's periodic watchdog scans for orphaned leases
    (a dead worker's in-flight job) and reconciles them WITHOUT requiring a
    restart. Must be > 0."""
    background_claim_candidates: int = Field(default=5, gt=0)
    """How many oldest QUEUED jobs a scaled worker reads per claim attempt before
    lease-racing them in order. Size it roughly to the worker fleet: with more
    workers than candidates the extras lose every race and back off a full idle
    window. Must be > 0."""
    background_retention_days: int = Field(default=0, ge=0)
    """How many days to keep TERMINAL background job rows (and their events,
    signals and checkpoints) before deleting them. ``0``, the default, disables
    retention entirely and keeps every row forever.

    Enable this on any long-lived deployment, and especially with
    ``background_backend=scaled``, where the job table IS the work queue: every
    terminal row sits under the claim scan and ``job_events`` grows a row per
    durable milestone, so an install with no window set grows without bound.
    Live runs are never deleted at any age: QUEUED, IN_PROGRESS and SUSPENDED
    rows are excluded (a suspended run is waiting on a human who may answer
    weeks later)."""
    background_backend: Literal["default", "scaled"] = "default"
    """Which background-execution backend runs v2 background workflow jobs.

    ``default`` runs jobs in-process inside the API (bounded by
    ``background_max_concurrency``). ``scaled`` turns the durable job table into
    the work queue: the API only persists the QUEUED row, and separate
    ``langflow worker`` processes lease-claim and run jobs against the SAME
    database, so background load runs off the API workers and scales
    horizontally. No broker is needed — the database is the queue. Every worker
    must reach that one database: use Postgres for multi-host fleets (SQLite's
    WAL is host-local, so scaled + SQLite only works on a single machine)."""
    background_poll_interval_s: float = Field(default=0.5, gt=0)
    """How often a scaled-mode event tail polls ``job_events`` for new durable
    frames while a job is live. Bounds the added reattach latency per milestone.
    Must be > 0."""

    # Triggers (TRG-2): the leased dispatcher, the schedule tick producer, and
    # the ledger retention windows.
    trigger_dispatcher_enabled: bool = True
    """Run the leased trigger dispatcher and schedule tick producer inside this
    process. Every API replica may set this: the loops are singletons held by a
    ``trigger_lease`` row, so N replicas still produce one tick per schedule and
    one run per event. Turn it off on replicas that must never execute triggers
    (and when TRG-3's dedicated listener process hosts the loops instead)."""
    trigger_dispatcher_poll_interval_s: float = Field(default=5.0, gt=0)
    """How often the dispatcher scans the ledger for claimable events. The lower
    bound on scheduling latency for an event that arrives just after a scan."""
    trigger_lease_ttl_s: float = Field(default=30.0, gt=0)
    """Lifetime of a dispatcher/scheduler singleton lease and of a per-event
    claim. A holder that dies has its work re-dispatched this many seconds
    later, so this is the worst-case duplicate-suppression window as well as the
    worst-case stall. The loops renew on ``trigger_dispatcher_poll_interval_s``,
    which must stay comfortably below this TTL so a healthy holder never looks
    dead. TRG-3's listener process adds its own heartbeat knob when it has a
    loop whose cadence differs from the poll."""
    trigger_max_events_per_poll: int = Field(default=25, gt=0)
    """Upper bound on events one dispatcher pass claims, so a large backlog is
    drained in bounded batches instead of one unbounded transaction."""
    trigger_retry_backoff_base_s: float = Field(default=5.0, gt=0)
    """First retry delay for a failed dispatch. Subsequent attempts back off
    exponentially up to ``trigger_retry_backoff_cap_s``."""
    trigger_retry_backoff_cap_s: float = Field(default=300.0, gt=0)
    """Ceiling on the exponential retry backoff."""
    trigger_replay_window_days: int = Field(default=7, gt=0)
    """How far back an owner may replay a ledger row, and how far back the
    schedule catch-up may reach after downtime."""
    trigger_event_retention_days: int = Field(default=30, gt=0)
    """How long terminal ledger rows are kept before the purge job deletes them.
    Must be at least ``trigger_replay_window_days`` for replay to be meaningful."""
    trigger_purge_interval_s: float = Field(default=3600.0, gt=0)
    """How often the purge pass runs inside the dispatcher loop."""

    # Triggers (TRG-3): the supervised listener process that holds Track B
    # provider connections (Slack Socket Mode, Graph delta polling, Gmail
    # Pub/Sub pull). The listeners never run the dispatcher loops and the API
    # never holds a provider connection; the two processes meet only at the
    # ledger.
    listeners_mode: Literal["off", "subprocess"] = "off"
    """Whether the API lifespan spawns ``langflow listeners`` as a child process.

    ``off`` (default) means the API hosts no listeners: either nothing needs
    Track B, or an operator runs ``langflow listeners`` as its own service (the
    supported shape for multi-replica deployments). ``subprocess`` is the
    single-container and Desktop shape - exactly one API worker spawns the child
    and stops it on shutdown, so a multi-worker API does not start N copies."""
    listeners_health_host: str = "127.0.0.1"
    """Interface the listener health server binds. Loopback by default so a
    listener container exposes nothing by accident; set ``0.0.0.0`` when a
    Kubernetes probe or a Compose healthcheck must reach it from outside the
    process namespace."""
    listeners_health_port: int = Field(default=7861, gt=0, le=65535)
    """Port serving ``/health`` (liveness) and ``/healthz`` (readiness) in the
    listener process. The listener serves nothing else: it has no HTTP app."""
    listener_lease_ttl_s: float = Field(default=30.0, gt=0)
    """How long a ``trigger_listener_lease`` row stays valid without a
    heartbeat. A replica that dies has its connections taken over within two
    TTLs, which is the failover target ``decisions/process-model.md`` records.
    Expiry is a Langflow recovery bound, not proof that the dead process closed
    its socket, so adapters must tolerate bounded overlap."""
    listener_heartbeat_interval_s: float = Field(default=10.0, gt=0)
    """How often a held connection lease is renewed. Must stay well below
    ``listener_lease_ttl_s`` so a healthy holder never looks dead."""
    listener_reconcile_interval_s: float = Field(default=5.0, gt=0)
    """How often the supervisor compares the triggers in the database with the
    connections it is holding, and claims or drops leases accordingly. There is
    no broker: this poll is how a listener learns about a new trigger."""
    listener_poll_interval_s: float = Field(default=30.0, gt=0)
    """Default interval for the generic poll loop that drives pull adapters.
    An adapter may ask for a different cadence; this is the fallback."""
    listener_backoff_base_s: float = Field(default=2.0, gt=0)
    """First delay after a connection task fails. Subsequent consecutive
    failures back off exponentially, with jitter, up to the cap."""
    listener_backoff_cap_s: float = Field(default=300.0, gt=0)
    """Ceiling on the listener reconnect backoff."""
    listener_failure_threshold: int = Field(default=5, gt=0)
    """Consecutive failures on one connection before the error is surfaced on
    every trigger that connection feeds. A success resets the counter."""

    # Triggers (TRG-4): the provider-signed ingress route on the API process and
    # the leased job that keeps provider subscriptions alive.
    trigger_ingress_enabled: bool = True
    """Serve the provider ingress route. Turn it off on an instance that accepts
    no inbound provider deliveries at all (a firewalled install using Track B
    listeners only); every ingress request then answers 404 exactly as an
    unknown trigger id does, so disabling it leaks nothing either."""
    trigger_ingress_max_body_bytes: int = Field(default=1_048_576, gt=0)
    """Per-route body cap for an ingress delivery, independent of the global
    request limit. Provider notifications are small - Graph basic notifications
    carry ids only - and this route is unauthenticated, so it reads a bounded
    body and rejects anything larger before parsing it."""
    trigger_ingress_rate_limit_per_minute: int = Field(default=600, gt=0)
    """Per-trigger ingress ceiling. Ten deliveries a second is far above any
    wave-1 provider's own cap (Slack allows 30,000 per workspace per app per
    hour) and far below what an abusive caller would need to hurt the API."""
    trigger_ingress_unknown_rate_limit_per_minute: int = Field(default=60, gt=0)
    """Per-client ceiling for deliveries that name no known trigger. Separate
    from the per-trigger counter so probing for valid ids is bounded without a
    real provider's retries ever consuming the same budget."""
    trigger_ingress_signature_tolerance_s: int = Field(default=300, gt=0)
    """How stale a signed request's timestamp may be. Slack's own guidance is
    five minutes; a shorter window rejects legitimate retries, a longer one
    widens the replay window."""
    trigger_subscription_renew_fraction: float = Field(default=0.5, gt=0, le=1)
    """Fraction of a subscription's lifetime after which renewal is attempted."""
    trigger_subscription_renew_lead_cap_s: float = Field(default=86_400.0, gt=0)
    """Upper bound on how far ahead of expiry a subscription is renewed. With
    the fraction above, a seven-day Graph mail subscription renews a day early
    and a one-day rich-notification subscription renews twelve hours early."""
    trigger_subscription_renew_interval_s: float = Field(default=300.0, gt=0)
    """How often the leased renewal job scans for subscriptions coming due."""
    trigger_subscription_max_per_poll: int = Field(default=25, gt=0)
    """Upper bound on how many subscriptions one renewal pass claims. Separate
    from the dispatcher's ``trigger_max_events_per_poll`` on purpose: one is an
    event budget measured against flow execution, the other a provider-call
    budget measured against an HTTP round trip per row, and an operator tuning
    one should not silently change the other."""
    trigger_subscription_retry_backoff_base_s: float = Field(default=60.0, gt=0)
    """First delay before a failed renewal is retried. Subsequent consecutive
    failures back off exponentially up to the cap. A renewal failure is never
    terminal while the subscription still has time on it - only expiry is."""
    trigger_subscription_retry_backoff_cap_s: float = Field(default=3600.0, gt=0)
    """Ceiling on the renewal retry backoff. Well under every wave-1 provider's
    shortest subscription lifetime (one day), so a subscription that is failing
    still gets many attempts before it expires."""
    trigger_subscription_failure_threshold: int = Field(default=3, gt=0)
    """Consecutive renewal failures before the problem is surfaced on the
    trigger the subscription feeds. A success clears it."""

    event_delivery: Literal["polling", "streaming", "direct"] = "streaming"
    """How to deliver build events to the frontend. Can be 'polling', 'streaming' or 'direct'."""

    worker_timeout: int = 300
    """Timeout for the API calls in seconds."""

    workflow_execution_timeout: int = 300
    """Wall-clock ceiling in seconds for a client-attached v2 workflow run.
    Sync runs raise a 408; stream and public runs emit the protocol's terminal-error
    event. Background runs use ``background_job_timeout`` instead."""

    model_provider_policy_refresh_interval_s: float = Field(default=10.0, gt=0)
    """How often each backend worker refreshes the install-wide model-provider policy.

    A several-second default limits steady-state database traffic while still
    converging policy updates promptly across workers. Must be positive so the
    refresh loop cannot spin continuously.
    """

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

    @model_validator(mode="after")
    def validate_trigger_event_retention(self) -> "RuntimeSettings":
        """Retain terminal events for the entire advertised replay window."""
        if self.trigger_event_retention_days < self.trigger_replay_window_days:
            msg = "trigger_event_retention_days must be at least trigger_replay_window_days"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_listener_lease_cadence(self) -> "RuntimeSettings":
        """A lease must not be able to expire before its holder gets to renew it.

        Renewal happens inside the reconcile pass, so the worst case between two
        renewals is a heartbeat that came due just after a pass plus a whole
        reconcile interval. Individually valid settings can combine to exceed
        the TTL - 30s TTL, 25s heartbeat, 20s reconcile renews at 45s - and then
        another replica takes over a connection whose adapter is still running.
        """
        renewal_ceiling = self.listener_heartbeat_interval_s + self.listener_reconcile_interval_s
        if renewal_ceiling >= self.listener_lease_ttl_s:
            msg = (
                "listener_heartbeat_interval_s + listener_reconcile_interval_s "
                f"({renewal_ceiling:g}s) must be below listener_lease_ttl_s "
                f"({self.listener_lease_ttl_s:g}s): renewal happens on a reconcile pass, so a "
                "healthy holder would otherwise look dead and lose its connections to another replica."
            )
            raise ValueError(msg)
        return self

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

    @property
    def background_backend_is_scaled(self) -> bool:
        """True when separate ``langflow worker`` processes run background jobs.

        Selection is the explicit ``background_backend`` setting: ``scaled``
        means the API only persists QUEUED job rows and workers lease-claim them
        off the shared database. Independent of ``job_queue_type`` — the
        database is the queue, no redis is involved.
        """
        return self.background_backend == "scaled"
