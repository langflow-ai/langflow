"""gunicorn process manager for ``lfx serve --workers N`` on Unix.

Uses ``preload_app=True`` so the master builds the warm app once and forks
workers (copy-on-write). ``--max-requests 1`` recycles each worker after a single
request so no request inherits another's process environment.

The ``pre_fork`` hook (mirrors ``langflow.server.LangflowApplication``) runs in
the master immediately before each worker is forked: it ``gc.freeze()``s the
fully-built, warmed preload heap so workers inherit it via copy-on-write without
the GC dirtying shared pages (preserving the preload memory savings), and warns
about any fork-unsafe state — background threads or open TCP connections (e.g. a
DB connection pool) left alive in the master, which would be silently dead or
corrupt in the forked workers.
"""

from __future__ import annotations

from gunicorn.app.base import BaseApplication
from uvicorn.workers import UvicornWorker


class LFXUvicornWorker(UvicornWorker):
    """UvicornWorker that applies ``LFX_SERVE_LIMIT_CONCURRENCY`` per worker.

    gunicorn's stock ``UvicornWorker`` maps ``max_requests`` (recycling) but never
    exposes uvicorn's ``limit_concurrency``, and gunicorn has no setting that
    forwards to it. So we read the limit from the ``LFX_SERVE_*`` environment (set
    by ``serve_command`` and inherited by each forked worker) and apply it to the
    worker's uvicorn ``Config``.

    The env var holds the user-facing cap N (max in-flight requests per worker).
    uvicorn's ``limit_concurrency`` counts the active connection itself, so it
    rejects once ``len(connections) >= limit`` — i.e. ``limit_concurrency=1``
    rejects EVERY request. To allow exactly N in-flight we set uvicorn's value to
    ``N + 1`` (empirically verified). With ``--limit-concurrency 1`` a worker then
    accepts one in-flight request and returns HTTP 503 for a concurrent second —
    combined with ``--max-requests 1`` this guarantees no two requests ever share a
    worker process / ``os.environ``.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._apply_limit_concurrency(self.config)

    @staticmethod
    def _apply_limit_concurrency(config) -> None:
        import os

        from lfx.cli.serve_app import _SERVE_LIMIT_CONCURRENCY_ENV

        raw = os.environ.get(_SERVE_LIMIT_CONCURRENCY_ENV)
        if raw:
            # +1: uvicorn counts the active connection, so its limit must exceed the
            # desired in-flight count (limit_concurrency=1 would reject everything).
            config.limit_concurrency = int(raw) + 1


class LFXGunicornApp(BaseApplication):
    def __init__(self, app_import_string: str, options: dict) -> None:
        self._app_import_string = app_import_string
        self._options = options or {}
        # Freeze + fork-safety diagnostics happen in the master right before each
        # fork. Doing the freeze here (not at app-import time) means the fully
        # warmed preload heap is frozen immediately before fork, so workers still
        # inherit it via copy-on-write — the preload memory savings are preserved.
        self._options.setdefault("pre_fork", self.pre_fork)
        super().__init__()

    # Thread-name prefixes known to be benign before fork: they never survive into
    # workers and produce no side effects when their fd is inherited.
    _BENIGN_THREAD_PREFIXES = (
        "OTel",  # OpenTelemetry SDK (BatchSpanProcessor, etc.)
        "opentelemetry",  # alternate OTel naming
        "prometheus",  # Prometheus client background threads
        "loguru",  # loguru enqueue=True worker
        "asyncio",  # event-loop helper threads (Python internals)
        "ThreadPoolExecutor",  # stdlib executor - harmless in parent
        "concurrent.futures",  # same pool, different prefix
    )

    @classmethod
    def _is_benign_thread(cls, thread) -> bool:
        return any(thread.name.startswith(prefix) for prefix in cls._BENIGN_THREAD_PREFIXES)

    @classmethod
    def pre_fork(cls, server, _worker) -> None:
        """Run in the master before each fork: warn on fork-unsafe state, then freeze.

        Any non-benign background thread or non-listening TCP connection still alive
        here will be dead/corrupt in the forked workers (e.g. a DB engine pool opened
        during preload). lfx serve is DB-less by default and opens nothing fork-unsafe
        at preload, so this is normally silent — but it loudly flags the day something
        leaves a live connection or thread in the master.
        """
        import gc
        import threading

        non_main = [t for t in threading.enumerate() if t.is_alive() and t is not threading.main_thread()]
        suspicious = [t for t in non_main if not cls._is_benign_thread(t)]
        if suspicious:
            server.log.warning(
                "Ghost threads found before fork (these will be dead in workers): %s",
                [t.name for t in suspicious],
            )

        try:
            import psutil

            ghost_conns = [c for c in psutil.Process().net_connections(kind="tcp") if c.status != "LISTEN"]
            if ghost_conns:
                server.log.warning(
                    "Ghost TCP connections found before fork (these will be dead/corrupt in workers): %s",
                    [(c.laddr, c.raddr, c.status) for c in ghost_conns],
                )
        except ImportError:
            server.log.debug("psutil not installed; skipping ghost TCP connection check")
        except Exception as e:  # noqa: BLE001
            server.log.warning("Failed to inspect TCP connections before fork: %s", e)

        try:
            gc.collect()
        except Exception as e:  # noqa: BLE001
            server.log.warning("gc.collect() raised during pre-fork hook: %s", e)
        gc.freeze()

    def load_config(self) -> None:
        for key, value in self._options.items():
            if value is not None and key in self.cfg.settings:
                self.cfg.set(key, value)

    def load(self):
        # preload_app=True -> gunicorn imports this string in the master pre-fork.
        from lfx.cli.serve_preloaded_app import app

        return app
