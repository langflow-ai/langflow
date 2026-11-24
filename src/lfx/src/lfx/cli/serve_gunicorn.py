"""gunicorn process manager for ``lfx serve --workers N`` on Unix.

Uses ``preload_app=True`` so the master builds the warm app once and forks
workers (copy-on-write). ``--max-requests`` recycles workers to bound memory (worker
hygiene, not per-request isolation — see ``_launch_workers`` for the isolation story).

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
    """Async worker class for ``lfx serve --workers N`` (the default, non-sync path).

    A thin named subclass of gunicorn's ``UvicornWorker`` so the worker class is owned
    here and can host per-worker customization if needed later.
    """


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
        if any(thread.name.startswith(prefix) for prefix in cls._BENIGN_THREAD_PREFIXES):
            return True
        # gunicorn's own master-only threads (e.g. the control-socket server's `_run_loop`,
        # added in gunicorn 23) are managed by gunicorn's own fork handlers and are meant to
        # be absent in workers — they are gunicorn infrastructure, not app state to flag.
        target = getattr(thread, "_target", None)
        return (getattr(target, "__module__", "") or "").startswith("gunicorn")

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
        # preload_app=True -> gunicorn imports this "module:attr" string in the master
        # pre-fork. The async path passes the ASGI app ("...:app"); --use-sync-workers
        # passes the WSGI bridge ("...:wsgi_application"). Honor whichever was given
        # rather than hardcoding one, so the worker gets the callable it expects.
        import importlib

        module_str, _, attr = self._app_import_string.partition(":")
        module = importlib.import_module(module_str)
        return getattr(module, attr)
