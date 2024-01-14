from gunicorn.app.base import BaseApplication  # type: ignore


class LangflowApplication(BaseApplication):
    def __init__(self, options=None):
        self.options = options or {}
        from langflow.main import create_app

        self.options["worker_class"] = "uvicorn.workers.UvicornWorker"
        self.application = create_app()
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application
