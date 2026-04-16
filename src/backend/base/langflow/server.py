import asyncio
import logging
import signal

from gunicorn import glogging
from gunicorn.app.base import BaseApplication
from lfx.log.logger import InterceptHandler
from uvicorn.workers import UvicornWorker


class LangflowUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {"loop": "asyncio"}
    _has_exited = False

    def _install_sigint_handler(self) -> None:
        """Install a SIGQUIT handler on workers.

        - https://github.com/encode/uvicorn/issues/1116
        - https://github.com/benoitc/gunicorn/issues/2604
        """
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, self.handle_exit, signal.SIGINT, None)
        loop.add_signal_handler(signal.SIGTERM, self.handle_exit, signal.SIGTERM, None)

    def handle_exit(self, sig, frame):
        if not self._has_exited:
            self._has_exited = True

        super().handle_exit(sig, frame)

    async def _serve(self) -> None:
        # We do this to not log the "Worker (pid:XXXXX) was sent SIGINT"
        self._install_sigint_handler()
        await super()._serve()


class Logger(glogging.Logger):
    """Implements and overrides the gunicorn logging interface.

    This class inherits from the standard gunicorn logger and overrides it by
    replacing the handlers with `InterceptHandler` in order to route the
    gunicorn logs to loguru.
    """

    def __init__(self, cfg) -> None:
        super().__init__(cfg)
        logging.getLogger("gunicorn.error").setLevel(logging.WARNING)
        logging.getLogger("gunicorn.access").setLevel(logging.WARNING)

        logging.getLogger("gunicorn.error").handlers = [InterceptHandler()]
        logging.getLogger("gunicorn.access").handlers = [InterceptHandler()]

    def error(self, msg, *args, **kwargs):
        """Override error method to filter out SIGSEGV messages."""
        # Filter out "Worker was sent SIGSEGV" messages which are common on macOS
        # with multiprocessing issues - these are typically handled by worker restart
        if "SIGSEGV" in str(msg):
            # Log at debug level instead of error
            self.log.debug(msg, *args, **kwargs)
        else:
            super().error(msg, *args, **kwargs)


class LangflowApplication(BaseApplication):
    def __init__(self, app, options=None) -> None:
        self.options = options or {}

        self.options["worker_class"] = "langflow.server.LangflowUvicornWorker"
        self.options["logger_class"] = Logger
        self.options["pre_fork"] = self.pre_fork
        self.application = app
        super().__init__()

    # Thread name prefixes that are known to be benign before fork.
    # BatchSpanProcessor (OTel), Prometheus scrape threads, and loguru's
    # async queue worker are all safe to ignore here - they never survive
    # into workers and produce no side-effects when the fd is inherited.
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
    def pre_fork(cls, server, _worker):
        import gc
        import os
        import threading

        all_non_main = [t for t in threading.enumerate() if t.is_alive() and t is not threading.main_thread()]
        debug_mode = os.environ.get("LANGFLOW_DEBUG_FORK_GHOSTS", "").lower() in ("1", "true", "yes")

        if debug_mode and all_non_main:
            names = [t.name for t in all_non_main]
            server.log.debug("All non-main threads before fork (debug): %s", names)

        suspicious = [t for t in all_non_main if not cls._is_benign_thread(t)]
        if suspicious:
            names = [t.name for t in suspicious]
            server.log.warning("Ghost threads found before fork (these will be dead in workers): %s", names)

        try:
            import psutil

            conns = psutil.Process().net_connections(kind="tcp")
            ghost_conns = [c for c in conns if c.status != "LISTEN"]
            if ghost_conns:
                details = [(c.laddr, c.raddr, c.status) for c in ghost_conns]
                server.log.warning(
                    "Ghost TCP connections found before fork (will be dead in workers): %s",
                    details,
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
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application
