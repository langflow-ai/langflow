"""Shared ``--help`` text for the multi-line ``lfx serve`` options.

These options are declared twice — in the lazy CLI wrapper (``_running_commands``) and in
the implementation ``commands.serve_command`` (which is also registered as a standalone
typer command in tests). Defining the substantial help text once here keeps the two from
drifting. Trivial one-line help (host, port, ...) stays inline at each call site.

Kept dependency-free so importing it never defeats the wrapper's lazy import of the heavy
``commands`` module.
"""

FLOW_DIR = (
    "Directory for filesystem-backed flow storage. "
    "All uvicorn workers sharing this path will serve the same flows. "
    "Use /tmp/lfx-flows for single-pod sharing or a PVC mount for cross-pod. "
    "Defaults to in-memory only when omitted."
)

MAX_REQUESTS = (
    "Recycle each worker after N requests to bound memory (gunicorn, Unix, --workers > 1). "
    "Default: recycle every ~1000 (10% jitter); 0 disables; 1 = every request. Not applied "
    "on Windows. Worker hygiene, NOT per-request isolation — for that use --use-sync-workers "
    "or --reset-environ."
)

TIMEOUT = (
    "Worker timeout in seconds (gunicorn, Unix, --workers > 1): a worker that does not "
    "complete a request within this many seconds is killed and restarted. Raise it for "
    "long-running flows, especially with --use-sync-workers (a blocking sync worker cannot "
    "heartbeat mid-request). Default: 120. No effect on Windows (uvicorn fallback)."
)

NO_ENV_FALLBACK = (
    "Disable os.environ fallback for credential variables. "
    "Variables not supplied via global_vars on each request resolve to None "
    "instead of reading from the process environment."
)

RESET_ENVIRON = (
    "Snapshot os.environ before each flow run and restore it afterward, so a "
    "flow's environment mutations (or request-scoped credentials) cannot leak "
    "into the next request served by the same warm worker. Off by default."
)

SYNC_WORKERS = (
    "Use gunicorn's blocking 'sync' worker (Unix, --workers > 1) so the kernel "
    "routes each request to an idle worker instead of queueing it behind an "
    "in-flight request on a busy async worker. Requires the 'a2wsgi' package. "
    "Off by default (async worker)."
)
