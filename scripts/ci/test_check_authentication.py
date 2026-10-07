"""The release gate must fail on an open, missing or broken auth boundary."""

import json
import threading
from collections import deque
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from secrets import token_urlsafe

import pytest

from scripts.ci.check_authentication import check_authentication


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
