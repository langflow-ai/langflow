"""The release gate must fail on an open, missing or broken auth boundary."""

import json
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from secrets import token_urlsafe
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.ci import check_authentication as smoke
from scripts.ci.check_authentication import check_authentication, check_installed_wheel


@contextmanager
def local_server(responses):
    pending = deque(responses)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append((self.command, self.path, self.headers.get("Authorization"), body))
            status, payload = pending.popleft()
            encoded = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        do_GET = respond  # noqa: N815
        do_POST = respond  # noqa: N815

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def accepted_responses():
    return [
        (403, {}),  # Auto-login is disabled.
        (401, {}),  # Current user requires authentication.
        (403, {}),  # SSE connection requires authentication.
        (403, {}),  # SSE messages require authentication.
        (403, {}),  # Streamable HTTP requires authentication.
        (401, {}),  # Wrong password fails.
        (200, {"access_token": "test-session"}),
        (200, {"username": "smoke-admin", "is_superuser": True}),
    ]


def test_checks_do_not_reuse_authentication_for_anonymous_requests():
    with local_server(accepted_responses()) as (port, requests):
        check_authentication(port, "smoke-admin", token_urlsafe(32))
    assert len(requests) == 8
    assert all(authorization is None for _, _, authorization, _ in requests[:-1])
    assert requests[-1][2] == "Bearer test-session"


@pytest.mark.parametrize("endpoint_index", range(6))
def test_rejects_success_from_each_negative_authentication_check(endpoint_index):
    responses = accepted_responses()
    responses[endpoint_index] = (200, {"access_token": "must-not-be-printed"})
    with local_server(responses) as (port, _), pytest.raises(RuntimeError, match="got 200") as error:
        check_authentication(port, "smoke-admin", token_urlsafe(32))
    assert "must-not-be-printed" not in str(error.value)


@pytest.mark.parametrize("status", [302, 404, 500])
def test_missing_or_broken_routes_are_not_accepted_as_authentication_denial(status):
    responses = accepted_responses()
    responses[2] = (status, {})
    with local_server(responses) as (port, _), pytest.raises(RuntimeError, match=f"got {status}"):
        check_authentication(port, "smoke-admin", token_urlsafe(32))


@pytest.mark.parametrize("tokens", [{}, {"access_token": ""}, {"access_token": None}])
def test_password_sign_in_must_return_a_usable_token(tokens):
    responses = accepted_responses()
    responses[6] = (200, tokens)
    with local_server(responses) as (port, _), pytest.raises(RuntimeError, match="did not return an access token"):
        check_authentication(port, "smoke-admin", token_urlsafe(32))


@pytest.mark.parametrize(
    "user",
    [{"username": "someone-else", "is_superuser": True}, {"username": "smoke-admin", "is_superuser": False}],
)
def test_password_sign_in_must_resolve_the_configured_administrator(user):
    responses = accepted_responses()
    responses[-1] = (200, user)
    with local_server(responses) as (port, _), pytest.raises(RuntimeError, match="configured administrator"):
        check_authentication(port, "smoke-admin", token_urlsafe(32))


def test_failed_startup_reports_server_log_without_password_and_reaps_process(monkeypatch, capsys):
    original_popen = subprocess.Popen
    processes = []

    def exited_server(_command, **kwargs):
        # A real child models startup failure, including a diagnostic quoting its environment.
        process = original_popen(
            [
                sys.executable,
                "-c",
                "import os, sys; print('startup failure: ' + os.environ['LANGFLOW_SUPERUSER_PASSWORD'], "
                "flush=True); sys.exit(7)",
            ],
            **kwargs,
        )
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", exited_server)
    password = token_urlsafe(32)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with pytest.raises(RuntimeError, match="exit 7"):
        check_installed_wheel(port, 5, "smoke-admin", password)

    diagnostic = capsys.readouterr().err
    assert "startup failure: [redacted]" in diagnostic
    assert password not in diagnostic
    assert processes[0].poll() == 7


def test_windows_shutdown_kills_tree_before_waiting_for_launcher(monkeypatch):
    process = Mock(pid=1234)
    process.poll.return_value = None
    events = []

    def taskkill(command, **kwargs):
        assert command == ["taskkill", "/PID", "1234", "/T", "/F"]
        assert kwargs["timeout"] == 15
        process.terminate.assert_not_called()
        process.kill.assert_not_called()
        events.append("tree stopped")
        return subprocess.CompletedProcess(command, 0)

    process.wait.side_effect = lambda **_kwargs: events.append("launcher reaped")
    monkeypatch.setattr(smoke, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(subprocess, "run", taskkill)

    smoke.stop_server(process)

    assert events == ["tree stopped", "launcher reaped"]


def test_windows_shutdown_leaves_already_exited_process_alone(monkeypatch):
    process = Mock()
    process.poll.return_value = 7
    taskkill = Mock()
    monkeypatch.setattr(smoke, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(subprocess, "run", taskkill)

    smoke.stop_server(process)

    taskkill.assert_not_called()
    process.terminate.assert_not_called()


@pytest.mark.parametrize("returncode_after_taskkill", [None, 0])
def test_windows_shutdown_only_tolerates_taskkill_failure_when_process_exited(monkeypatch, returncode_after_taskkill):
    process = Mock(pid=1234)
    process.poll.side_effect = [None, returncode_after_taskkill]
    monkeypatch.setattr(smoke, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(subprocess, "run", lambda *args, **_kwargs: subprocess.CompletedProcess(args[0], 1))

    if returncode_after_taskkill is None:
        with pytest.raises(subprocess.CalledProcessError):
            smoke.stop_server(process)
    else:
        smoke.stop_server(process)
        process.wait.assert_called_once()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows refuses deletion while a descendant has SQLite open")
def test_windows_shutdown_releases_database_held_by_descendant(tmp_path):
    child_script = (
        "import os, sqlite3, time; from pathlib import Path; "
        "db = sqlite3.connect('langflow.db'); db.execute('CREATE TABLE smoke (id INTEGER)'); "
        "Path('ready').write_text(str(os.getpid())); time.sleep(60)"
    )
    launcher_script = f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {child_script!r}]).wait()"
    process = subprocess.Popen([sys.executable, "-c", launcher_script], cwd=tmp_path)  # noqa: S603
    ready = tmp_path / "ready"
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "The descendant did not open its database"

        smoke.stop_server(process)

        # This raises WinError 32 if only the launcher was terminated.
        (tmp_path / "langflow.db").unlink()
        assert process.poll() is not None
    finally:
        # Reap the test tree even when the regression leaves an orphan behind.
        pids = [str(process.pid)]
        if ready.exists():
            pids.append(ready.read_text())
        for pid in pids:
            subprocess.run(  # noqa: S603
                ["taskkill", "/PID", pid, "/T", "/F"],  # noqa: S607
                capture_output=True,
                timeout=15,
                check=False,
            )
        process.wait(timeout=5)
