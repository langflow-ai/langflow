import asyncio
import logging
import signal

from gunicorn import glogging  # type: ignore
from gunicorn.app.base import BaseApplication  # type: ignore
from uvicorn.workers import UvicornWorker

from langflow.logging.logger import InterceptHandler  # type: ignore
from langflow.services.deps import get_database_service


class LangflowUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {"loop": "asyncio"}

    async def handle_cleanup_and_exit(self, sig, frame):
        await self.cleanup_db()
        super().handle_exit(sig, frame)

    async def handle_cleanup_and_quit(self, sig, frame):
        await self.cleanup_db()
        super().handle_quit(sig, frame)

    async def cleanup_db(self):
        print("Cleaning up database...")

        try:
            db_service = get_database_service()
            await db_service.teardown()
            print("Database cleaned up successfully")
        except Exception as e:
            print(f"Error cleaning up database: {e}")

    def _install_signal_handlers(self) -> None:
        """Install a SIGQUIT handler on workers.

        - https://github.com/encode/uvicorn/issues/1116
        - https://github.com/benoitc/gunicorn/issues/2604
        """

        loop = asyncio.get_running_loop()
        # TODO: using quit or exit?
        # https://github.com/benoitc/gunicorn/blob/master/gunicorn/workers/base.py
        # https://github.com/Kludex/uvicorn-worker/blob/main/uvicorn_worker/_workers.py
        loop.add_signal_handler(signal.SIGINT, self.handle_cleanup_and_quit, signal.SIGINT, None)
        loop.add_signal_handler(signal.SIGQUIT, self.handle_cleanup_and_exit, signal.SIGQUIT, None)
        loop.add_signal_handler(signal.SIGTERM, self.handle_cleanup_and_exit, signal.SIGTERM, None)

    async def _serve(self) -> None:
        # We do this to not log the "Worker (pid:XXXXX) was sent SIGINT"
        self._install_signal_handlers()
        await super()._serve()


class Logger(glogging.Logger):
    """Implements and overrides the gunicorn logging interface.

    This class inherits from the standard gunicorn logger and overrides it by
    replacing the handlers with `InterceptHandler` in order to route the
    gunicorn logs to loguru.
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        logging.getLogger("gunicorn.error").handlers = [InterceptHandler()]
        logging.getLogger("gunicorn.access").handlers = [InterceptHandler()]


class LangflowApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}

        self.options["worker_class"] = "langflow.server.LangflowUvicornWorker"
        self.options["logger_class"] = Logger
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application
