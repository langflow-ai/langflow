from gunicorn.app.base import BaseApplication  # type: ignore
from uvicorn.workers import UvicornWorker


class LangflowUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {"loop": "asyncio"}


class LangflowApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}

        self.options["worker_class"] = "langflow.server.LangflowUvicornWorker"
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application
