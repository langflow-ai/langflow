"""Unit tests for LangflowApplication in langflow.server."""

import gc
import threading
from unittest.mock import MagicMock, patch

import pytest
from langflow.server import LangflowApplication


class _FakeServer:
    """Minimal stand-in for the gunicorn Server object passed to pre_fork."""

    def __init__(self):
        self.log = MagicMock()


@pytest.fixture
def fake_server():
    return _FakeServer()


def _find_warning(mock_log, substring: str):
    """Return the first warning call whose format string contains *substring*, or None."""
    return next(
        (c for c in mock_log.warning.call_args_list if substring in (c.args[0] if c.args else "")),
        None,
    )


def _make_fake_conn(status: str):
    """Return a psutil-style connection named-tuple substitute."""
    conn = MagicMock()
    conn.status = status
    conn.laddr = ("127.0.0.1", 12345)
    conn.raddr = ("127.0.0.1", 9999)
    return conn


# ---------------------------------------------------------------------------
# Thread-safety warnings
# ---------------------------------------------------------------------------


def test_pre_fork_warns_for_non_main_threads(fake_server):
    """pre_fork should warn when live non-main threads are present before fork."""
    ready = threading.Event()
    stop = threading.Event()

    def _worker():
        ready.set()
        stop.wait()

    t = threading.Thread(target=_worker, name="ghost-worker", daemon=True)
    t.start()
    try:
        ready.wait(timeout=2)
        LangflowApplication.pre_fork(fake_server, None)
    finally:
        stop.set()
        t.join(timeout=2)

    warning = _find_warning(fake_server.log, "Ghost threads")
    assert warning is not None, "Expected a 'Ghost threads' warning but none was logged"
    assert "ghost-worker" in warning.args[1]


def test_pre_fork_no_thread_warning_for_benign_threads(fake_server):
    """pre_fork should not emit a thread warning for threads with known benign prefixes."""
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True
    mock_thread.name = "loguru-worker-1"

    with (
        patch("threading.enumerate", return_value=[threading.main_thread(), mock_thread]),
        patch("psutil.Process") as mock_proc,
    ):
        mock_proc.return_value.net_connections.return_value = []
        LangflowApplication.pre_fork(fake_server, None)

    assert _find_warning(fake_server.log, "Ghost threads") is None


def test_pre_fork_no_thread_warning_when_only_main_thread(fake_server):
    """pre_fork should not emit a thread warning when only the main thread is alive."""
    with (
        patch("threading.enumerate", return_value=[threading.main_thread()]),
        patch("psutil.Process") as mock_proc,
    ):
        mock_proc.return_value.net_connections.return_value = []
        LangflowApplication.pre_fork(fake_server, None)

    assert _find_warning(fake_server.log, "Ghost threads") is None


# ---------------------------------------------------------------------------
# TCP-connection warnings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["ESTABLISHED", "TIME_WAIT", "CLOSE_WAIT", "CLOSING", "SYN_SENT"])
def test_pre_fork_warns_for_non_listen_tcp_connections(fake_server, status):
    """pre_fork should warn for any non-LISTEN TCP connection status."""
    conn = _make_fake_conn(status)

    with (
        patch("threading.enumerate", return_value=[threading.main_thread()]),
        patch("psutil.Process") as mock_proc,
    ):
        mock_proc.return_value.net_connections.return_value = [conn]
        LangflowApplication.pre_fork(fake_server, None)

    warning = _find_warning(fake_server.log, "Ghost TCP connections")
    assert warning is not None, f"Expected a 'Ghost TCP connections' warning for status={status!r}"
    logged_details = warning.args[1]
    assert any(status in str(d) for d in logged_details), (
        f"Expected connection status {status!r} in logged details, got: {logged_details}"
    )


def test_pre_fork_no_tcp_warning_for_listen_only_connections(fake_server):
    """pre_fork should not warn when all TCP connections are in LISTEN state."""
    with (
        patch("threading.enumerate", return_value=[threading.main_thread()]),
        patch("psutil.Process") as mock_proc,
    ):
        mock_proc.return_value.net_connections.return_value = [_make_fake_conn("LISTEN")]
        LangflowApplication.pre_fork(fake_server, None)

    assert _find_warning(fake_server.log, "Ghost TCP connections") is None


# ---------------------------------------------------------------------------
# Error-resilience
# ---------------------------------------------------------------------------


def test_pre_fork_handles_psutil_import_error(fake_server):
    """pre_fork should silently skip TCP inspection when psutil is unavailable."""
    with (
        patch("threading.enumerate", return_value=[threading.main_thread()]),
        patch.dict("sys.modules", {"psutil": None}),
    ):
        LangflowApplication.pre_fork(fake_server, None)

    assert _find_warning(fake_server.log, "TCP") is None, "Should not log TCP warnings when psutil is missing"


def test_pre_fork_warns_when_psutil_raises(fake_server):
    """pre_fork should log a warning (not raise) when psutil throws unexpectedly."""
    with (
        patch("threading.enumerate", return_value=[threading.main_thread()]),
        patch("psutil.Process") as mock_proc,
    ):
        mock_proc.return_value.net_connections.side_effect = RuntimeError("permission denied")
        LangflowApplication.pre_fork(fake_server, None)

    warning = _find_warning(fake_server.log, "Failed to inspect")
    assert warning is not None, "Expected a 'Failed to inspect' warning when psutil raises"
    assert "permission denied" in str(warning.args[1])


# ---------------------------------------------------------------------------
# GC contract
# ---------------------------------------------------------------------------


def test_pre_fork_always_runs_gc(fake_server):
    """pre_fork must call gc.collect() and gc.freeze() unconditionally."""
    with (
        patch("threading.enumerate", return_value=[threading.main_thread()]),
        patch("psutil.Process") as mock_proc,
        patch.object(gc, "collect") as mock_collect,
        patch.object(gc, "freeze") as mock_freeze,
    ):
        mock_proc.return_value.net_connections.return_value = []
        LangflowApplication.pre_fork(fake_server, None)

    mock_collect.assert_called_once()
    mock_freeze.assert_called_once()


def test_pre_fork_handles_gc_collect_exception(fake_server):
    """pre_fork must not crash if gc.collect() raises, and must still call gc.freeze()."""
    with (
        patch("threading.enumerate", return_value=[threading.main_thread()]),
        patch("psutil.Process") as mock_proc,
        patch.object(gc, "collect", side_effect=RuntimeError("bad finalizer")),
        patch.object(gc, "freeze") as mock_freeze,
    ):
        mock_proc.return_value.net_connections.return_value = []
        # Must not raise
        LangflowApplication.pre_fork(fake_server, None)

    warning = _find_warning(fake_server.log, "gc.collect() raised")
    assert warning is not None, "Expected a warning when gc.collect() raises"
    assert "bad finalizer" in str(warning.args[1])
    mock_freeze.assert_called_once()


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
