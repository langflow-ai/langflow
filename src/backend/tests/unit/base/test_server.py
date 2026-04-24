from langflow.server import LangflowApplication


def _make_app(options=None, env_args=None, monkeypatch=None):
    """Create a LangflowApplication with a dummy WSGI app.

    Args:
        options: Programmatic options passed to LangflowApplication.
        env_args: If provided, set GUNICORN_CMD_ARGS env var before construction.
        monkeypatch: pytest monkeypatch fixture for env manipulation.
    """
    if env_args is not None and monkeypatch is not None:
        monkeypatch.setenv("GUNICORN_CMD_ARGS", env_args)

    def dummy_app(environ, start_response):
        pass

    return LangflowApplication(dummy_app, options=options)


class TestGunicornEnvArgs:
    def test_env_args_applied(self, monkeypatch):
        """GUNICORN_CMD_ARGS values should be reflected in the config."""
        app = _make_app(env_args="--max-requests 100 --max-requests-jitter 20", monkeypatch=monkeypatch)

        assert app.cfg.settings["max_requests"].get() == 100
        assert app.cfg.settings["max_requests_jitter"].get() == 20

    def test_programmatic_options_override_env(self, monkeypatch):
        """Programmatic options must take precedence over GUNICORN_CMD_ARGS."""
        app = _make_app(
            options={"workers": 2},
            env_args="--workers 8",
            monkeypatch=monkeypatch,
        )

        assert app.cfg.settings["workers"].get() == 2

    def test_no_env_var_uses_defaults(self):
        """Without GUNICORN_CMD_ARGS, Gunicorn defaults should remain intact."""
        app = _make_app()

        # Gunicorn default for max_requests is 0 (disabled)
        assert app.cfg.settings["max_requests"].get() == 0

    def test_env_does_not_override_worker_class(self, monkeypatch):
        """worker_class is always set programmatically and must not be overridden by env."""
        app = _make_app(
            env_args="--worker-class sync",
            monkeypatch=monkeypatch,
        )

        assert app.cfg.settings["worker_class"].get() == "langflow.server.LangflowUvicornWorker"
