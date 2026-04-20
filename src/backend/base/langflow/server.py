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
        self.application = app
        super().__init__()

    def load_config(self) -> None:
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)
        # CNT-04: reset fork-unsafe resources in each worker after fork.
        # See _langflow_post_fork below + TelemetryService.start() guard.
        self.cfg.set("post_fork", _langflow_post_fork)

    def load(self):
        return self.application


def _langflow_post_fork(server, worker) -> None:  # noqa: ARG001
    """Reset fork-unsafe resources in each worker after gunicorn forks.

    Gunicorn calls this hook synchronously in the worker process immediately
    after fork, before any request is served. No event loop exists yet here —
    this function MUST remain fully synchronous (no async calls, no
    asyncio.get_event_loop, no await).

    Current responsibilities (CNT-04 fork-hazard audit, RESEARCH.md section
    "Fork Hazard Audit (D-05)"):

    * TelemetryService.client (httpx.AsyncClient) — reset to None so that
      TelemetryService.start() reconstructs it inside the worker's event
      loop. httpx.AsyncClient has no synchronous .close(), so we cannot
      aclose() here; replacing the reference is the correct pattern
      (Pitfall 1).

    All other hazards audited in Phase 5 (SQLAlchemy engine, asyncio locks,
    ComponentCache.all_types_dict, Redis pool, asyncio.create_task, open
    file descriptors) are SAFE by construction — see the phase 05 SUMMARY
    for evidence.
    """
    try:
        from langflow.services.deps import get_telemetry_service

        tel = get_telemetry_service()
        tel.client = None
    except Exception:  # noqa: BLE001, S110
        # Service not yet initialized (e.g. preload_app=False path). The
        # hook must not crash gunicorn.
        pass
