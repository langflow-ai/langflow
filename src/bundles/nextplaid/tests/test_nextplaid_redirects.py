"""Exercise the real SDK against local redirecting HTTP servers."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
import requests
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_nextplaid import NextPlaidVectorStoreComponent


@pytest.fixture
def redirect_servers(monkeypatch):
    """Allow only the first server while recording requests reaching the second."""
    received = []

    class Destination(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"metadata": []}')

        do_POST = do_GET  # noqa: N815

        def log_message(self, *_args):
            pass

    destination = ThreadingHTTPServer(("127.0.0.1", 0), Destination)
    target_url = f"http://localhost:{destination.server_port}/target"

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/ok/"):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")
                return
            self.send_response(307)
            self.send_header("Location", target_url)
            self.end_headers()

        do_POST = do_GET  # noqa: N815

        def log_message(self, *_args):
            pass

    source = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threads = [Thread(target=server.serve_forever, daemon=True) for server in (destination, source)]
    for thread in threads:
        thread.start()
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "false")
    monkeypatch.setattr("lfx.utils.ssrf_protection.get_allowed_hosts", lambda: ["127.0.0.1"])
    try:
        yield f"http://127.0.0.1:{source.server_port}", received
    finally:
        for server in (source, destination):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join()


def test_sdk_index_lookup_refuses_redirect_before_destination_connects(redirect_servers):
    """The SDK constructor must not follow a redirect while checking its index."""
    url, received = redirect_servers
    component = NextPlaidVectorStoreComponent(url=url, embedding=object(), _session_id="test-session")

    with pytest.raises(SSRFProtectionError, match="redirect"):
        component.build_vector_store()

    assert received == []


def test_sdk_later_post_refuses_redirect_before_destination_connects(redirect_servers):
    """A store returned by the component retains the same destination protection."""
    url, received = redirect_servers
    component = NextPlaidVectorStoreComponent(
        url=url, embedding=object(), create_index_if_not_exists=False, _session_id="test-session"
    )
    store = component.build_vector_store()

    with pytest.raises(SSRFProtectionError, match="redirect"):
        store.get_by_ids(["document"])

    assert received == []


def test_sdk_keeps_operator_allowlisted_service(redirect_servers):
    """A normal response from an operator-allowlisted service remains usable."""
    url, received = redirect_servers
    component = NextPlaidVectorStoreComponent(url=f"{url}/ok", embedding=object(), _session_id="test-session")

    assert component.build_vector_store() is not None
    assert received == []


@pytest.mark.parametrize("setting", ["LANGFLOW_SSRF_PROTECTION_ENABLED", "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED"])
def test_sdk_keeps_operator_policy_opt_out(monkeypatch, redirect_servers, setting):
    """An operator who disables the applicable policy retains the SDK behavior."""
    url, received = redirect_servers
    monkeypatch.setenv(setting, "false")
    component = NextPlaidVectorStoreComponent(url=url, embedding=object(), _session_id="test-session")

    component.build_vector_store()

    assert received == ["/target"]


def test_sdk_policy_does_not_replace_process_requests(redirect_servers):
    """Hardening NextPlaid must leave unrelated Requests clients unchanged."""
    url, received = redirect_servers
    component = NextPlaidVectorStoreComponent(
        url=url, embedding=object(), create_index_if_not_exists=False, _session_id="test-session"
    )
    component.build_vector_store()

    requests.get(url, timeout=5).raise_for_status()

    assert received == ["/target"]
