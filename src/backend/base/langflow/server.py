import asyncio
import gc
import logging
import signal
import threading
from collections.abc import Callable
from typing import Any

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
    def __init__(self, app_factory: Callable[[], Any], options=None) -> None:
        self.options = options or {}

        self.options["worker_class"] = "langflow.server.LangflowUvicornWorker"
        self.options["logger_class"] = Logger
        self.options["pre_fork"] = self.pre_fork
        self._app_factory = app_factory
        self.application = None
        super().__init__()

    def load_config(self) -> None:
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    @staticmethod
    def pre_fork(server, _worker) -> None:
        """Inspect the master process before forking a worker."""
        non_main_threads = [thread for thread in threading.enumerate() if thread is not threading.main_thread()]
        if non_main_threads:
            thread_names = [thread.name for thread in non_main_threads if thread.is_alive()]
            if thread_names:
                server.log.warning("Ghost threads found before fork (these will be dead in workers): %s", thread_names)

        try:
            import psutil

            connections = psutil.Process().net_connections(kind="tcp")
            ghost_connections = [conn for conn in connections if conn.status != "LISTEN"]
            if ghost_connections:
                details = [(conn.laddr, conn.raddr, conn.status) for conn in ghost_connections]
                server.log.warning(
                    "Ghost TCP connections found before fork (these will be dead in workers): %s",
                    details,
                )
        except ImportError:
            pass
        except Exception as exc:  # noqa: BLE001
            server.log.warning("Failed to inspect TCP connections before fork: %s", exc)

        gc.collect()
        gc.freeze()

    def load(self):
        if self.application is None:
            self.application = self._app_factory()
        return self.application
