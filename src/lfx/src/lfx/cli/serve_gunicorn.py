"""gunicorn process manager for ``lfx serve --workers N`` on Unix.

Uses ``preload_app=True`` so the master builds the warm app once and forks
workers (copy-on-write). ``max_requests=1`` recycles each worker after a single
request so no request inherits another's process environment.
"""

from __future__ import annotations

from gunicorn.app.base import BaseApplication


class LFXGunicornApp(BaseApplication):
    def __init__(self, app_import_string: str, options: dict) -> None:
        self._app_import_string = app_import_string
        self._options = options or {}
        super().__init__()

    def load_config(self) -> None:
        for key, value in self._options.items():
            if value is not None and key in self.cfg.settings:
                self.cfg.set(key, value)

    def load(self):
        # preload_app=True -> gunicorn imports this string in the master pre-fork.
        from lfx.cli.serve_preloaded_app import app

        return app
