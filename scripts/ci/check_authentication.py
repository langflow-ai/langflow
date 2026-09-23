"""Check release authentication against a disposable local Langflow server.

Run with the installed wheel's Python and --start-server, or inside a running
test container. Credentials come from the environment and are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlencode

MAX_PORT = 65535


def request(
    port: int,
    method: str,
    path: str,
    expected: set[int],
    *,
    body: str | None = None,
    headers: dict[str, str] | None = None,
    read_json: bool = False,
) -> dict:
    """Check status before reading a body, including potentially open streams."""
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        if response.status not in expected:
            msg = f"{method} {path}: expected {sorted(expected)}, got {response.status}"
            raise RuntimeError(msg)
        return json.loads(response.read()) if read_json else {}
    finally:
        connection.close()


def wait_until_ready(port: int, timeout: float, process: subprocess.Popen | None = None) -> None:
    """Bound startup waits and stop promptly when the child server exits."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            msg = f"Langflow exited before becoming ready (exit {process.returncode})"
            raise RuntimeError(msg)
        try:
            request(port, "GET", "/health_check", {200})
        except (OSError, RuntimeError):
            time.sleep(1)
        else:
            return
    msg = "Langflow did not become ready within the startup timeout"
    raise RuntimeError(msg)


def check_authentication(port: int, username: str, password: str) -> None:
    """Verify anonymous denial, invalid-password denial and password sign-in."""
    request(port, "GET", "/api/v1/auto_login", {403})
    request(port, "GET", "/api/v1/users/whoami", {401, 403})
    # Check both global MCP transports without opening a session or calling tools.
    request(port, "GET", "/api/v1/mcp/sse", {401, 403})
    request(port, "POST", "/api/v1/mcp/", {401, 403})
    request(port, "GET", "/api/v1/mcp/streamable", {401, 403})
    login_headers = {"Content-Type": "application/x-www-form-urlencoded"}
    request(
        port,
        "POST",
        "/api/v1/login",
        {401},
        body=urlencode({"username": username, "password": password + "-incorrect"}),
        headers=login_headers,
    )
    tokens = request(
        port,
        "POST",
        "/api/v1/login",
        {200},
        body=urlencode({"username": username, "password": password}),
        headers=login_headers,
        read_json=True,
    )
    token = tokens.get("access_token")
    if not isinstance(token, str) or not token:
        msg = "Password sign-in did not return an access token"
        raise RuntimeError(msg)
    user = request(
        port,
        "GET",
        "/api/v1/users/whoami",
        {200},
        headers={"Authorization": f"Bearer {token}"},
        read_json=True,
    )
    if user.get("username") != username or user.get("is_superuser") is not True:
        msg = "Password sign-in did not resolve the configured administrator"
        raise RuntimeError(msg)


def check_installed_wheel(port: int, timeout: float, username: str, password: str) -> None:
    """Start installed code outside the checkout, with no auto-login override."""
    with tempfile.TemporaryDirectory(prefix="langflow-auth-smoke-") as directory:
        environment = dict(os.environ)
        environment.pop("LANGFLOW_AUTO_LOGIN", None)
        environment.pop("PYTHONPATH", None)
        environment.update(
            LANGFLOW_CONFIG_DIR=directory,
            LANGFLOW_DATABASE_URL=f"sqlite:///{Path(directory) / 'langflow.db'}",
            LANGFLOW_SUPERUSER=username,
            LANGFLOW_SUPERUSER_PASSWORD=password,
            LANGFLOW_SKIP_MCP_AUTO_INIT="true",
            LANGFLOW_MODELS_DEV_REFRESH="false",
            DO_NOT_TRACK="true",
        )
        # Uvicorn runs the installed app in a single process on every CI platform.
        # -I excludes the source checkout and PYTHONPATH from Python's search path.
        with Path(directory, "server.log").open("w") as log:
            process = subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "uvicorn",
                    "langflow.main:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=directory,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                wait_until_ready(port, timeout, process)
                check_authentication(port, username, password)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--start-server", action="store_true")
    args = parser.parse_args()
    if (args.port is not None and not 0 < args.port <= MAX_PORT) or args.timeout <= 0:
        parser.error("port must be 1-65535 and timeout must be positive")
    password = os.environ.get("LANGFLOW_SUPERUSER_PASSWORD")
    if not password:
        parser.error("LANGFLOW_SUPERUSER_PASSWORD must be set for the disposable test server")
    username = os.environ.get("LANGFLOW_SUPERUSER") or "langflow"
    if args.start_server:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", args.port or 0))
            port = listener.getsockname()[1]
        check_installed_wheel(port, args.timeout, username, password)
    else:
        port = args.port or 7860
        wait_until_ready(port, args.timeout)
        check_authentication(port, username, password)
    print("Authentication smoke check passed: anonymous access denied; password sign-in verified.")


if __name__ == "__main__":
    main()
