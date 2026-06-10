import asyncio
import contextlib
import json
import os
from pathlib import Path
from shutil import copy2
from typing import Any, Literal

import aiofiles
import orjson
import yaml
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict
from typing_extensions import override

from lfx.constants import BASE_COMPONENTS_PATH
from lfx.log.logger import logger
from lfx.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH
from lfx.services.settings.constants import AGENTIC_VARIABLES, VARIABLES_TO_GET_FROM_ENVIRONMENT
from lfx.utils.util_strings import is_valid_database_url, sanitize_database_url


def is_list_of_any(field: FieldInfo) -> bool:
    """Check if the given field is a list or an optional list of any type.

    Args:
        field (FieldInfo): The field to be checked.

    Returns:
        bool: True if the field is a list or a list of any type, False otherwise.
    """
    if field.annotation is None:
        return False
    try:
        union_args = field.annotation.__args__ if hasattr(field.annotation, "__args__") else []

        return field.annotation.__origin__ is list or any(
            arg.__origin__ is list for arg in union_args if hasattr(arg, "__origin__")
        )
    except AttributeError:
        return False


class CustomSource(EnvSettingsSource):
    @override
    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:  # type: ignore[misc]
        # allow comma-separated list parsing

        # fieldInfo contains the annotation of the field
        if is_list_of_any(field):
            if isinstance(value, str):
                value = value.split(",")
            if isinstance(value, list):
                return value

        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    # Define the default LANGFLOW_DIR
    config_dir: str | None = None
    # Define if langflow db should be saved in config dir or
    # in the langflow directory
    save_db_in_config_dir: bool = False
    """Define if langflow database should be saved in LANGFLOW_CONFIG_DIR or in the langflow directory
    (i.e. in the package directory)."""

    knowledge_bases_dir: str | None = "~/.langflow/knowledge_bases"
    """The directory to store knowledge bases."""

    kb_allowed_folder_roots: list[str] = []
    """Allow-list of directories the folder-ingestion endpoint may read from.

    Comma-separated when set via env (``LANGFLOW_KB_ALLOWED_FOLDER_ROOTS``),
    e.g. ``/srv/docs,/data/shared``. Empty by default — operators must opt in.
    ``POST /api/v1/knowledge_bases/{kb_name}/ingest/folder`` refuses to walk any
    directory that is not equal to or inside one of these roots; symlink escapes
    are blocked because the path is resolved before the containment check. Leave
    empty in multi-tenant cloud deployments to refuse arbitrary-path access."""

    dev: bool = False
    """If True, Langflow will run in development mode."""
    database_url: str | None = None
    """Database URL for Langflow. If not provided, Langflow will use a SQLite database.
    The driver shall be an async one like `sqlite+aiosqlite` (`sqlite` and `postgresql`
    will be automatically converted to the async drivers `sqlite+aiosqlite` and
    `postgresql+psycopg` respectively)."""
    database_connection_retry: bool = False
    """If True, Langflow will retry to connect to the database if it fails."""
    pool_size: int = 20
    """The number of connections to keep open in the connection pool.
    For high load scenarios, this should be increased based on expected concurrent users."""
    max_overflow: int = 30
    """The number of connections to allow that can be opened beyond the pool size.
    Should be 2x the pool_size for optimal performance under load."""
    db_connect_timeout: int = 30
    """The number of seconds to wait before giving up on a lock to released or establishing a connection to the
    database."""
    migration_lock_namespace: str | None = None
    """Optional namespace identifier for PostgreSQL advisory lock during migrations.
    If not provided, a hash of the database URL will be used. Useful when multiple Langflow
    instances share the same database and need coordinated migration locking."""

    root_path: str = ""
    """ASGI root_path for deployments behind a reverse proxy that strips a URL
    prefix (e.g. '/langflow').  When set, the MCP SSE transport includes this
    prefix in the POST-back URL so clients can reach the correct endpoint.
    Can also be set via the LANGFLOW_ROOT_PATH environment variable."""

    @field_validator("root_path", mode="before")
    @classmethod
    def validate_root_path(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            msg = "root_path must be a string"
            raise TypeError(msg)

        value = value.strip()
        if not value or value == "/":
            return ""

        if "://" in value or "?" in value or "#" in value:
            msg = "root_path must be an ASGI path prefix only, without scheme, query string, or fragment"
            raise ValueError(msg)

        if not value.startswith("/"):
            value = f"/{value}"

        return value.rstrip("/")

    mcp_base_url: str = ""
    """External base URL used to build MCP server URLs in the UI configuration JSON
    (e.g. 'https://langflow.example.com'). When empty, the frontend falls back to
    the browser's window.location.origin."""

    mcp_server_timeout: int = 20
    """The number of seconds to wait before giving up on establishing a connection to the MCP server."""

    mcp_tool_execution_timeout: float = 180.0
    """Maximum seconds to wait for MCP tool execution before timing out.
    Default is 180 seconds (3 minutes) to support long-running operations.
    Supports decimal values for sub-second timeouts (e.g., 0.5 for 500ms).
    Individual components can override this with their own timeout setting.
    Must be a positive number greater than 0."""

    @field_validator("mcp_tool_execution_timeout")
    @classmethod
    def validate_mcp_tool_execution_timeout(cls, v: float) -> float:
        """Validate that mcp_tool_execution_timeout is positive."""
        if v <= 0:
            msg = "mcp_tool_execution_timeout must be greater than 0"
            raise ValueError(msg)
        return v

    # ---------------------------------------------------------------------
    # MCP Session-manager tuning
    # ---------------------------------------------------------------------
    mcp_max_sessions_per_server: int = 10
    """Maximum number of MCP sessions to keep per unique server (command/url).
    Mirrors the default constant MAX_SESSIONS_PER_SERVER in util.py. Adjust to
    control resource usage or concurrency per server."""

    mcp_session_idle_timeout: int = 400  # seconds
    """How long (in seconds) an MCP session can stay idle before the background
    cleanup task disposes of it. Defaults to 5 minutes."""

    mcp_session_cleanup_interval: int = 120  # seconds
    """Frequency (in seconds) at which the background cleanup task wakes up to
    reap idle sessions."""

    # sqlite configuration
    sqlite_pragmas: dict | None = {
        "synchronous": "NORMAL",
        "journal_mode": "WAL",
        "busy_timeout": 30000,
        "foreign_keys": "ON",
    }
    """SQLite pragmas to use when connecting to the database."""

    db_driver_connection_settings: dict | None = None
    """Database driver connection settings."""

    db_connection_settings: dict | None = {
        "pool_size": 20,  # Match the pool_size above
        "max_overflow": 30,  # Match the max_overflow above
        "pool_timeout": 30,  # Seconds to wait for a connection from pool
        "pool_pre_ping": True,  # Check connection validity before using
        "pool_recycle": 1800,  # Recycle connections after 30 minutes
        "echo": False,  # Set to True for debugging only
    }
    """Database connection settings optimized for high load scenarios.
    Note: These settings are most effective with PostgreSQL. For SQLite:
    - Reduce pool_size and max_overflow if experiencing lock contention
    - SQLite has limited concurrent write capability even with WAL mode
    - Best for read-heavy or moderate write workloads

    Settings:
    - pool_size: Number of connections to maintain (increase for higher concurrency)
    - max_overflow: Additional connections allowed beyond pool_size
    - pool_timeout: Seconds to wait for an available connection
    - pool_pre_ping: Validates connections before use to prevent stale connections
    - pool_recycle: Seconds before connections are recycled (prevents timeouts)
    - echo: Enable SQL query logging (development only)
    """

    use_noop_database: bool = False
    """If True, disables all database operations and uses a no-op session.
    Controlled by LANGFLOW_USE_NOOP_DATABASE env variable."""

    # cache configuration
    cache_type: Literal["async", "redis", "memory"] = "async"
    """The cache backend: 'async' (default in-memory), 'memory' (sync in-memory), or 'redis'."""
    cache_expire: int = 3600
    """The cache expire in seconds."""
    cache_dir: str | None = None
    """Directory used by FlowEventsService for cross-worker event storage. Defaults to a temp dir if not set."""
    variable_store: str = "db"
    """The store can be 'db' or 'kubernetes'."""

    prometheus_enabled: bool = False
    """If set to True, Langflow will expose Prometheus metrics."""
    prometheus_port: int = 9090
    """The port on which Langflow will expose Prometheus metrics. 9090 is the default port."""

    disable_track_apikey_usage: bool = False
    remove_api_keys: bool = False
    components_path: list[str] = []
    """List of paths to custom components.

    Security: This setting defines an allow-list of custom components
    permitted to execute, even when LANGFLOW_ALLOW_CUSTOM_COMPONENTS is False.
    """
    components_index_path: str | None = None
    """Path or URL to a prebuilt component index JSON file.

    If None, uses the built-in index at lfx/_assets/component_index.json.
    Set to a file path (e.g., '/path/to/index.json') or URL (e.g., 'https://example.com/index.json')
    to use a custom index.
    """
    langchain_cache: str = "InMemoryCache"
    load_flows_path: str | None = None
    load_flows_overwrite_on_name_match: bool = False
    """When a flow loaded from ``load_flows_path`` shares a name with an existing DB row but has
    a different id, overwrite the existing row's content from the file.

    Default ``False`` preserves user edits made in the UI on restart: name-matched rows are
    skipped with a warning instead of being silently overwritten when file UUIDs regenerate.
    (Pre-1.10.0 this case raised ``IntegrityError`` and crashed startup; the loader now boots
    successfully either way.) Set ``True`` to opt into "prepackaged flows are the source of
    truth on restart" semantics, typically for CI/CD pipelines.
    """
    bundle_urls: list[str] = []

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str | None = None
    redis_cache_expire: int = 3600

    # Rate Limiting
    rate_limit_enabled: bool = True
    """Enable rate limiting for login endpoint. Set to False to disable (useful for testing)."""
    rate_limit_per_minute: int = 5
    """Number of login attempts allowed per minute per IP."""
    rate_limit_storage_uri: str = "memory://"
    """Storage backend for rate limiting. Use 'memory://' for single-server or 'redis://host:port' for multi-server."""
    rate_limit_trust_proxy: bool = False
    """Trust X-Forwarded-For header when behind a reverse proxy. Only enable when behind a trusted proxy."""

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

    # Sentry
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float | None = 1.0
    sentry_profiles_sample_rate: float | None = 1.0

    store: bool | None = True
    store_url: str | None = "https://api.langflow.store"
    download_webhook_url: str | None = "https://api.langflow.store/flows/trigger/ec611a61-8460-4438-b187-a4f65e5559d4"
    like_webhook_url: str | None = "https://api.langflow.store/flows/trigger/64275852-ec00-45c1-984e-3bff814732da"

    storage_type: str = "local"
    """Storage type for file storage. Defaults to 'local'. Supports 'local' and 's3'."""
    object_storage_bucket_name: str | None = "langflow-bucket"
    """Object storage bucket name for file storage. Defaults to 'langflow-bucket'."""
    object_storage_prefix: str | None = "files"
    """Object storage prefix for file storage. Defaults to 'files'."""
    object_storage_tags: dict[str, str] | None = None
    """Object storage tags for file storage."""

    celery_enabled: bool = False

    fallback_to_env_var: bool = True
    """If set to True, Global Variables set in the UI will fallback to a environment variable
    with the same name in case Langflow fails to retrieve the variable value."""

    store_environment_variables: bool = True
    """Whether to store environment variables as Global Variables in the database."""
    variables_to_get_from_environment: list[str] = VARIABLES_TO_GET_FROM_ENVIRONMENT
    """List of environment variables to get from the environment and store in the database."""
    worker_timeout: int = 300
    """Timeout for the API calls in seconds."""
    frontend_timeout: int = 0
    """Timeout for the frontend API calls in seconds."""
    user_agent: str = "langflow"
    """User agent for the API calls."""
    backend_only: bool = False
    """If set to True, Langflow will not serve the frontend."""

    # CORS Settings
    cors_origins: list[str] | str = "*"
    """Allowed origins for CORS. Can be a list of origins or '*' for all origins.
    Default is '*' for backward compatibility. In production, specify exact origins."""
    cors_allow_credentials: bool = True
    """Whether to allow credentials in CORS requests.
    Default is True for backward compatibility. In v2.0, this will be changed to False when using wildcard origins."""
    cors_allow_methods: list[str] | str = "*"
    """Allowed HTTP methods for CORS requests."""
    cors_allow_headers: list[str] | str = "*"
    """Allowed headers for CORS requests."""

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

    # Config
    host: str = "localhost"
    """The host on which Langflow will run."""
    port: int = 7860
    """The port on which Langflow will run."""
    runtime_port: int | None = Field(default=None, exclude=True)
    """TEMPORARY: The port detected at runtime after checking for conflicts.
    This field is system-managed only and will be removed in future versions
    when strict port enforcement is implemented (errors will be raised if port unavailable)."""
    workers: int = 1
    """The number of workers to run."""
    log_level: str = "critical"
    """The log level for Langflow."""
    log_file: str | None = "logs/langflow.log"
    """The path to log file for Langflow."""
    alembic_log_file: str = "alembic/alembic.log"
    """The path to log file for Alembic for SQLAlchemy."""
    alembic_log_to_stdout: bool = False
    """If set to True, the log file will be ignored and Alembic will log to stdout."""
    frontend_path: str | None = None
    """The path to the frontend directory containing build files. This is for development purposes only.."""
    open_browser: bool = False
    """If set to True, Langflow will open the browser on startup."""
    auto_saving: bool = True
    """If set to True, Langflow will auto save flows."""
    auto_saving_interval: int = 1000
    """The interval in ms at which Langflow will auto save flows."""
    health_check_max_retries: int = 5
    """The maximum number of retries for the health check."""
    max_file_size_upload: int = 1024
    """The maximum file size for the upload in MB."""
    deactivate_tracing: bool = False
    """If set to True, tracing will be deactivated."""
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
    webhook_polling_interval: int = 0
    """The polling interval for the webhook in ms. Set to 0 to disable (SSE provides real-time updates)."""
    fs_flows_polling_interval: int = 10000
    """The polling interval in milliseconds for synchronizing flows from the file system."""
    ssl_cert_file: str | None = None
    """Path to the SSL certificate file on the local system."""
    ssl_key_file: str | None = None
    """Path to the SSL key file on the local system."""
    max_text_length: int = MAX_TEXT_LENGTH
    """Maximum number of characters to store and display in the UI. Responses longer than this
    will be truncated when displayed in the UI. Does not truncate responses between components nor outputs."""
    max_items_length: int = MAX_ITEMS_LENGTH
    """Maximum number of items to store and display in the UI. Lists longer than this
    will be truncated when displayed in the UI. Does not affect data passed between components nor outputs."""
    max_ingestion_timeout_secs: int = 600

    # MCP Server
    mcp_server_enabled: bool = True
    """If set to False, Langflow will not enable the MCP server."""
    mcp_server_enable_progress_notifications: bool = False
    """If set to False, Langflow will not send progress notifications in the MCP server."""

    # Add projects to MCP servers automatically on creation
    add_projects_to_mcp_servers: bool = True
    """If set to True, newly created projects will be added to the user's MCP servers config automatically."""
    # MCP Composer
    mcp_composer_enabled: bool = True
    """If set to False, Langflow will not start the MCP Composer service."""
    mcp_composer_version: str = "==0.1.0.8.10"
    """Version constraint for mcp-composer when using uvx. Uses PEP 440 syntax."""

    # Agentic Experience
    agentic_experience: bool = False
    """If set to True, Langflow will start the agentic MCP server that provides tools for
    flow/component operations, template search, and graph visualization."""

    # Developer API
    developer_api_enabled: bool = False
    """If set to True, Langflow will enable developer API endpoints for advanced debugging and introspection."""

    # Public Flow Settings
    public_flow_cleanup_interval: int = Field(default=3600, gt=600)
    """The interval in seconds at which public temporary flows will be cleaned up.
    Default is 1 hour (3600 seconds). Minimum is 600 seconds (10 minutes)."""
    public_flow_expiration: int = Field(default=86400, gt=600)
    """The time in seconds after which a public temporary flow will be considered expired and eligible for cleanup.
    Default is 24 hours (86400 seconds). Minimum is 600 seconds (10 minutes)."""
    event_delivery: Literal["polling", "streaming", "direct"] = "streaming"
    """How to deliver build events to the frontend. Can be 'polling', 'streaming' or 'direct'."""
    lazy_load_components: bool = False
    """If set to True, Langflow will only partially load components at startup and fully load them on demand.
    This significantly reduces startup time but may cause a slight delay when a component is first used."""

    # Starter Projects
    create_starter_projects: bool = True
    """If set to True, Langflow will create starter projects. If False, skips all starter project setup.
    Note that this doesn't check if the starter projects are already loaded in the db;
    this is intended to be used to skip all startup project logic."""
    update_starter_projects: bool = True
    """If set to True, Langflow will update starter projects."""

    # Extension reload (Mode A only)
    enable_extension_reload: bool = False
    """If True, registers ``POST /api/v1/extensions/{id}/bundles/{name}/reload``
    so authenticated users can hot-swap a Bundle's components in-process.

    This is a Mode A (local-dev / pip-installed) facility only.  In Mode B/C
    (Docker image with baked-in bundles) Bundle changes require an image
    rebuild and the in-process reload route would mask the real deploy
    pipeline.  Defaults to ``False`` so self-hosted / production deployments
    do not expose runtime imports through an HTTP endpoint without an
    explicit opt-in.  Set ``LANGFLOW_ENABLE_EXTENSION_RELOAD=true`` in your
    local dev environment to turn it on."""

    # Custom Component Security
    allow_custom_components: bool = True
    """If set to False, blocks execution of components whose code does not match a known
    server template.

    The server validates node code against its component template cache;
    when the cache is not yet loaded (e.g., during startup), all flow execution is blocked
    as a safety measure.

    Note: LANGFLOW_COMPONENTS_PATH and LANGFLOW_COMPONENTS_INDEX_PATH can be used to define
    an allow-list of custom components that will be allowed to execute, even when
    allow_custom_components is False. That bypass can be disabled with
    allow_components_paths_override.

    Note: this is a beta feature. For security in a multi-tenant environment,
    use hardware-level isolation to restrict access."""
    custom_component_admin_only: bool = False
    """If set to True, only admin users can edit custom component code. Regular editors
    are blocked from modifying custom component templates."""

    allow_components_paths_override: bool = True
    """If set to False, LANGFLOW_COMPONENTS_PATH and LANGFLOW_COMPONENTS_INDEX_PATH will
    not bypass the allow_custom_components=False restriction — only components matching
    built-in server templates will be executable.

    Default is True, which preserves the existing behavior: components loaded from those
    env-var paths act as an admin-curated allow-list that remains executable even when
    allow_custom_components is False.

    Has no effect when allow_custom_components is True (the flag is not blocking anything
    to override)."""

    # SSRF Protection
    ssrf_protection_enabled: bool = True
    """If set to True, Langflow will enable SSRF (Server-Side Request Forgery) protection.
    When enabled, blocks requests to private IP ranges, localhost, and cloud metadata endpoints.
    When False, no URL validation is performed, allowing requests to any destination
    including internal services, private networks, and cloud metadata endpoints.
    Default is True to protect against SSRF attacks including DNS rebinding.

    Note: When ssrf_protection_enabled is disabled, the ssrf_allowed_hosts setting is ignored and has no effect."""
    ssrf_allowed_hosts: list[str] = []
    """Comma-separated list of hosts/IPs/CIDR ranges to allow despite SSRF protection.
    Examples: 'internal-api.company.local,192.168.1.0/24,10.0.0.5,*.dev.internal'
    Supports exact hostnames, wildcard domains (*.example.com), exact IPs, and CIDR ranges.

    Note: This setting only takes effect when ssrf_protection_enabled is True.
    When protection is disabled, all hosts are allowed regardless of this setting."""

    # Embedded mode flags
    embedded_mode: bool = False
    """Umbrella flag for iframe/embedded mode. When True, hides UI elements specific to
    standalone installations (logout button, new project/flow buttons, starter projects, etc.).

    This flag does not implicitly enable security controls such as
    ``mcp_servers_locked`` or ``custom_component_admin_only``. Configure those
    explicitly based on your deployment hardening requirements.
    """
    hide_getting_started_progress: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "LANGFLOW_HIDE_GETTING_STARTED_PROGRESS",
            "HIDE_GETTING_STARTED_PROGRESS",
        ),
    )
    """If set to True, hides the getting-started onboarding progress UI."""
    hide_logout_button: bool = False
    """If set to True, hides the Logout button in the account menu."""
    hide_new_project_button: bool = False
    """If set to True, hides the ability to create new projects/folders."""
    hide_new_flow_button: bool = False
    """If set to True, hides the ability to create new flows."""
    hide_starter_projects: bool = False
    """If set to True, hides starter projects from the UI (does not affect database seeding)."""

    # MCP Server management
    mcp_servers_locked: bool = False
    """If set to True, users cannot add or modify MCP servers via the UI/API.

    This control is independent from ``embedded_mode`` and must be enabled
    explicitly when you want to lock MCP server management.
    """

    @field_validator("runtime_port", mode="before")
    @classmethod
    def validate_runtime_port(cls, value):
        """Parse port from Kubernetes service discovery env vars.

        Kubernetes auto-creates env vars like LANGFLOW_RUNTIME_PORT=tcp://<ip>:<port>
        for services, which collides with the LANGFLOW_ env prefix. Extract the port
        number from URL-like values instead of failing.
        """
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            if value.isdigit():
                return int(value)
            if "://" in value:
                from urllib.parse import urlparse

                try:
                    parsed_port = urlparse(value).port
                except ValueError:
                    return None
                if parsed_port is not None:
                    return parsed_port
        return None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def validate_cors_origins(cls, value):
        """Convert comma-separated string to list if needed."""
        if isinstance(value, str) and value != "*":
            if "," in value:
                # Convert comma-separated string to list
                return [origin.strip() for origin in value.split(",")]
            # Convert single origin to list for consistency
            return [value]
        return value

    @field_validator("use_noop_database", mode="before")
    @classmethod
    def set_use_noop_database(cls, value):
        if value:
            logger.info("Running with NOOP database session. All DB operations are disabled.")
        return value

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

    @field_validator("user_agent", mode="after")
    @classmethod
    def set_user_agent(cls, value):
        if not value:
            value = "Langflow"
        import os

        os.environ["USER_AGENT"] = value
        logger.debug(f"Setting user agent to {value}")
        return value

    @field_validator("mcp_composer_version", mode="before")
    @classmethod
    def validate_mcp_composer_version(cls, value):
        """Ensure the version string has a version specifier prefix.

        If a bare version like '0.1.0.7' is provided, prepend '~=' to allow patch updates.
        Supports PEP 440 specifiers: ==, !=, <=, >=, <, >, ~=, ===
        """
        if not value:
            return "==0.1.0.8.10"  # Default

        # Check if it already has a version specifier
        # Order matters: check longer specifiers first to avoid false matches
        specifiers = ["===", "==", "!=", "<=", ">=", "~=", "<", ">"]
        if any(value.startswith(spec) for spec in specifiers):
            return value

        # If it's a bare version number, add ~= prefix
        # This regex matches version numbers like 0.1.0.7, 1.2.3, etc.
        import re

        if re.match(r"^\d+(\.\d+)*", value):
            logger.debug(f"Adding ~= prefix to bare version '{value}' -> '~={value}'")
            return f"~={value}"

        # If we can't determine, return as-is and let uvx handle it
        return value

    @field_validator("variables_to_get_from_environment", mode="before")
    @classmethod
    def set_variables_to_get_from_environment(cls, value):
        import os

        if isinstance(value, str):
            value = value.split(",")

        result = list(set(VARIABLES_TO_GET_FROM_ENVIRONMENT + value))

        # Add agentic variables if agentic_experience is enabled
        # Check env var directly since we can't access instance attributes in validator
        if os.getenv("LANGFLOW_AGENTIC_EXPERIENCE", "true").lower() == "true":
            result.extend(AGENTIC_VARIABLES)

        return list(set(result))

    @field_validator("log_file", mode="before")
    @classmethod
    def set_log_file(cls, value):
        if isinstance(value, Path):
            value = str(value)
        return value

    @field_validator("config_dir", mode="before")
    @classmethod
    def set_langflow_dir(cls, value):
        if not value:
            from platformdirs import user_cache_dir

            # Define the app name and author
            app_name = "langflow"
            app_author = "langflow"

            # Get the cache directory for the application
            cache_dir = user_cache_dir(app_name, app_author)

            # Create a .langflow directory inside the cache directory
            value = Path(cache_dir)
            value.mkdir(parents=True, exist_ok=True)

        if isinstance(value, str):
            value = Path(value)
        # Resolve to absolute path to handle relative paths correctly
        value = value.resolve()
        if not value.exists():
            value.mkdir(parents=True, exist_ok=True)

        return str(value)

    @field_validator("cache_dir", mode="before")
    @classmethod
    def validate_cache_dir(cls, value):
        """Validate and normalize cache_dir path.

        If not set, returns None and the factory will fall back to config_dir.
        If set, resolves to an absolute path and creates the directory if needed.
        """
        if not value:
            return None

        if isinstance(value, str):
            value = Path(value)
        # Resolve to absolute path to handle relative paths correctly
        value = value.resolve()
        if not value.exists():
            value.mkdir(parents=True, exist_ok=True)

        return str(value)

    @field_validator("database_url", mode="before")
    @classmethod
    def set_database_url(cls, value, info):
        if value and not is_valid_database_url(value):
            sanitized = sanitize_database_url(value)
            msg = f"Invalid database_url provided: '{sanitized}'"
            raise ValueError(msg)

        if langflow_database_url := os.getenv("LANGFLOW_DATABASE_URL"):
            value = langflow_database_url
            logger.debug("Using LANGFLOW_DATABASE_URL env variable")
        else:
            # Originally, we used sqlite:///./langflow.db
            # so we need to migrate to the new format
            # if there is a database in that location
            if not info.data["config_dir"]:
                msg = "config_dir not set, please set it or provide a database_url"
                raise ValueError(msg)

            from lfx.utils.version import get_version_info
            from lfx.utils.version import is_pre_release as langflow_is_pre_release

            version = get_version_info()["version"]
            is_pre_release = langflow_is_pre_release(version)

            if info.data["save_db_in_config_dir"]:
                database_dir = info.data["config_dir"]
            else:
                # Use langflow package path, not lfx, for backwards compatibility
                try:
                    import langflow

                    database_dir = Path(langflow.__file__).parent.resolve()
                except ImportError:
                    database_dir = Path(__file__).parent.parent.parent.resolve()

            pre_db_file_name = "langflow-pre.db"
            db_file_name = "langflow.db"
            new_pre_path = f"{database_dir}/{pre_db_file_name}"
            new_path = f"{database_dir}/{db_file_name}"
            final_path = None
            if is_pre_release:
                if Path(new_pre_path).exists():
                    final_path = new_pre_path
                elif Path(new_path).exists() and info.data["save_db_in_config_dir"]:
                    # We need to copy the current db to the new location
                    logger.debug("Copying existing database to new location")
                    copy2(new_path, new_pre_path)
                    logger.debug(f"Copied existing database to {new_pre_path}")
                elif Path(f"./{db_file_name}").exists() and info.data["save_db_in_config_dir"]:
                    logger.debug("Copying existing database to new location")
                    copy2(f"./{db_file_name}", new_pre_path)
                    logger.debug(f"Copied existing database to {new_pre_path}")
                else:
                    logger.debug(f"Creating new database at {new_pre_path}")
                    final_path = new_pre_path
            elif Path(new_path).exists():
                final_path = new_path
            elif Path(f"./{db_file_name}").exists():
                try:
                    logger.debug("Copying existing database to new location")
                    copy2(f"./{db_file_name}", new_path)
                    logger.debug(f"Copied existing database to {new_path}")
                except OSError:
                    logger.exception("Failed to copy database, using default path")
                    new_path = f"./{db_file_name}"
            else:
                final_path = new_path

            if final_path is None:
                final_path = new_pre_path if is_pre_release else new_path

            value = f"sqlite:///{final_path}"

        return value

    @field_validator("components_path", mode="before")
    @classmethod
    def set_components_path(cls, value):
        """Processes and updates the components path list, incorporating environment variable overrides.

        If the `LANGFLOW_COMPONENTS_PATH` environment variable is set and points to an existing path, it is
        appended to the provided list if not already present. If the input list is empty or missing, it is
        set to an empty list.
        """
        env_value = os.getenv("LANGFLOW_COMPONENTS_PATH")
        if env_value:
            logger.debug("Adding LANGFLOW_COMPONENTS_PATH to components_path")
            # Split on os.pathsep so multi-entry env vars
            # ("/path/A:/path/B" on POSIX, "C:\\a;D:\\b" on Windows) are
            # parsed as multiple components paths instead of one literal
            # non-existent path. Empty segments (e.g. trailing pathsep) are
            # ignored.
            for raw_entry in env_value.split(os.pathsep):
                entry = raw_entry.strip()
                if not entry:
                    continue
                if not Path(entry).exists():
                    # Surface at warning so a typo in LANGFLOW_COMPONENTS_PATH
                    # is visible in default log levels rather than silently
                    # producing zero components and zero diagnostics. The
                    # extension loader emits a typed ``inline-path-missing``
                    # warning at the same layer for events-pipeline consumers.
                    logger.warning(f"Skipping non-existent components path: {entry}")
                    continue
                if entry not in value:
                    value.append(entry)
                    logger.debug(f"Appending {entry} to components_path")

        if not value:
            value = [BASE_COMPONENTS_PATH]
        elif isinstance(value, Path):
            value = [str(value)]
        elif isinstance(value, list):
            value = [str(p) if isinstance(p, Path) else p for p in value]
        return value

    @model_validator(mode="after")
    def _enforce_components_paths_override(self):
        """Strip env-var-provided component paths when their bypass is disabled.

        When ``allow_custom_components`` is False the server only trusts components
        matching built-in templates. By default ``LANGFLOW_COMPONENTS_PATH`` and
        ``LANGFLOW_COMPONENTS_INDEX_PATH`` still contribute to that trust set (an
        admin-curated allow-list). Setting ``allow_components_paths_override=False``
        disables that bypass: here we remove the env-contributed entries so nothing
        downstream loads or trusts them.
        """
        if self.allow_custom_components or self.allow_components_paths_override:
            return self

        env_components_path = os.getenv("LANGFLOW_COMPONENTS_PATH")
        if env_components_path:
            # The env var may be a comma-separated list; CustomSource splits it
            # before the field validator runs, so self.components_path contains
            # individual entries rather than the raw comma-joined string.
            # In-place removal avoids re-triggering ``set_components_path``, which
            # would re-read LANGFLOW_COMPONENTS_PATH and append the paths again.
            env_paths = [p.strip() for p in env_components_path.split(",") if p.strip()]
            stripped_any = False
            for env_path in env_paths:
                while env_path in self.components_path:
                    self.components_path.remove(env_path)
                    stripped_any = True
            if stripped_any:
                logger.warning(
                    "Ignoring LANGFLOW_COMPONENTS_PATH=%s: "
                    "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False and "
                    "LANGFLOW_ALLOW_COMPONENTS_PATHS_OVERRIDE=False.",
                    env_components_path,
                )

        # Only strip the index path when it came from the env var, mirroring the
        # components_path handling above. A value set via config/YAML is not part of
        # the env-var bypass this flag governs, so leave it untouched.
        env_components_index_path = os.getenv("LANGFLOW_COMPONENTS_INDEX_PATH")
        if env_components_index_path and self.components_index_path == env_components_index_path:
            logger.warning(
                "Ignoring LANGFLOW_COMPONENTS_INDEX_PATH=%s: "
                "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False and "
                "LANGFLOW_ALLOW_COMPONENTS_PATHS_OVERRIDE=False.",
                self.components_index_path,
            )
            self.components_index_path = None

        return self

    model_config = SettingsConfigDict(validate_assignment=True, extra="ignore", env_prefix="LANGFLOW_")

    async def update_from_yaml(self, file_path: str, *, dev: bool = False) -> None:
        new_settings = await load_settings_from_yaml(file_path)
        self.components_path = new_settings.components_path or []
        self.dev = dev

    def update_settings(self, **kwargs) -> None:
        for key, value in kwargs.items():
            # value may contain sensitive information, so we don't want to log it
            if not hasattr(self, key):
                continue
            if isinstance(getattr(self, key), list):
                # value might be a '[something]' string
                value_ = value
                with contextlib.suppress(json.decoder.JSONDecodeError):
                    value_ = orjson.loads(str(value))
                if isinstance(value_, list):
                    for item in value_:
                        item_ = str(item) if isinstance(item, Path) else item
                        if item_ not in getattr(self, key):
                            getattr(self, key).append(item_)
                else:
                    value_ = str(value_) if isinstance(value_, Path) else value_
                    if value_ not in getattr(self, key):
                        getattr(self, key).append(value_)
            else:
                setattr(self, key, value)

    @property
    def voice_mode_available(self) -> bool:
        """Check if voice mode is available by testing webrtcvad import."""
        try:
            import webrtcvad  # noqa: F401
        except ImportError:
            return False
        else:
            return True

    @classmethod
    @override
    def settings_customise_sources(  # type: ignore[misc]
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (CustomSource(settings_cls),)


def save_settings_to_yaml(settings: Settings, file_path: str) -> None:
    with Path(file_path).open("w", encoding="utf-8") as f:
        settings_dict = settings.model_dump()
        yaml.dump(settings_dict, f)


async def load_settings_from_yaml(file_path: str) -> Settings:
    # Check if a string is a valid path or a file name
    if "/" not in file_path:
        # Get current path
        current_path = Path(__file__).resolve().parent
        file_path_ = Path(current_path) / file_path
    else:
        file_path_ = Path(file_path)

    async with aiofiles.open(file_path_.name, encoding="utf-8") as f:
        content = await f.read()
        settings_dict = yaml.safe_load(content)
        settings_dict = {k.upper(): v for k, v in settings_dict.items()}

        for key in settings_dict:
            if key not in Settings.model_fields:
                msg = f"Key {key} not found in settings"
                raise KeyError(msg)
            await logger.adebug(f"Loading {len(settings_dict[key])} {key} from {file_path}")

    return await asyncio.to_thread(Settings, **settings_dict)
