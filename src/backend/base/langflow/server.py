import asyncio
import logging
import signal
from collections.abc import Callable
from typing import Any

from gunicorn import glogging
from gunicorn.app.base import BaseApplication
from lfx.log.logger import InterceptHandler
from uvicorn.workers import UvicornWorker


class LangflowUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {"loop": "asyncio"}
    _has_exited = False

    def init_process(self) -> None:
        from langflow.services.deps import get_settings_service

        trust_proxy = get_settings_service().settings.rate_limit_trust_proxy
        forwarded_allow_ips = "*" if trust_proxy else ""

        # Gunicorn cfg: keeps the value consistent for anything that reads it later.
        self.cfg.set("forwarded_allow_ips", forwarded_allow_ips)

        # Uvicorn Config: UvicornWorker.__init__ already snapshotted cfg.forwarded_allow_ips
        # into self.config before init_process runs.  ProxyHeadersMiddleware reads
        # self.config.forwarded_allow_ips at startup, so we must update it directly.
        self.config.forwarded_allow_ips = forwarded_allow_ips

        super().init_process()

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

    @classmethod
    def pre_fork(cls, server, _worker):
        import gc
        import os

        # Benign-thread allowlist + ghost detection live in lfx.fork (shared with lfx serve).
        from lfx.fork import find_ghost_connections, find_ghost_threads

        ghost_threads = find_ghost_threads()

        if os.environ.get("LANGFLOW_DEBUG_FORK_GHOSTS", "").lower() in ("1", "true", "yes"):
            import threading

            all_non_main = [t.name for t in threading.enumerate() if t.is_alive() and t is not threading.main_thread()]
            if all_non_main:
                server.log.debug("All non-main threads before fork (debug): %s", all_non_main)

        if ghost_threads:
            names = [t.name for t in ghost_threads]
            server.log.warning("Ghost threads found before fork (these will be dead in workers): %s", names)

        # find_ghost_connections() returns [] when psutil is absent; surface that here as a
        # debug breadcrumb so an empty result isn't mistaken for "checked and clean".
        import importlib.util

        if importlib.util.find_spec("psutil") is None:
            server.log.debug("psutil not installed; skipping ghost TCP connection check")

        try:
            ghost_conns = find_ghost_connections()
        except Exception as e:  # noqa: BLE001
            server.log.warning("Failed to inspect TCP connections before fork: %s", e)
            ghost_conns = []
        if ghost_conns:
            server.log.warning(
                "Ghost TCP connections found before fork (will be dead in workers): %s",
                ghost_conns,
            )

        try:
            gc.collect()
        except Exception as e:  # noqa: BLE001
            server.log.warning("gc.collect() raised during pre-fork hook: %s", e)
        gc.freeze()

    def load_config(self) -> None:
        # Apply options from GUNICORN_CMD_ARGS env var before programmatic options
        parser = self.cfg.parser()
        cmd_args = self.cfg.get_cmd_args_from_env()
        if cmd_args:
            env_args = parser.parse_args(cmd_args)
            for k, v in vars(env_args).items():
                # Skip unset/positional args and only apply known settings
                if v is None or k == "args" or k not in self.cfg.settings:
                    continue
                self.cfg.set(k.lower(), v)

        # Programmatic options override env args
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        if self.application is None:
            self.application = self._app_factory()
            # When preload_app is enabled, gunicorn calls load() once in the master
            # before forking workers. Take this opportunity to run all fork-safe
            # one-time initialization so workers inherit the big in-memory state
            # (component types dict, bundle Python modules, starter projects, etc.)
            # via copy-on-write. Preload may open the DB engine transiently for
            # migrations/seeding and dispose it before fork; long-lived pools and
            # other fork-unsafe resources (telemetry threads, MCP asyncio tasks,
            # prometheus server, ...) are not left running in the master. Each
            # worker still sets them up in its own FastAPI lifespan.
            if self.cfg.preload_app:
                from langflow.preload import preload_master

                preload_master()
        return self.application
