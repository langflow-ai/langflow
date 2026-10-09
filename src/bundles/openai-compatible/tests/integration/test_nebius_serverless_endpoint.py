"""Run the exported example against a local authenticated OpenAI-compatible API.

These tests exercise real graph loading, provider configuration, HTTP clients,
and SSE parsing. They do not provision or contact Nebius resources.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from lfx.base.models import provider_registry
from lfx.extension import load_extension
from lfx.graph import Graph
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType
from lfx.services.variable.service import VariableService
from lfx_openai_compatible.discovery import (
    fetch_live_openai_compatible_models,
    validate_openai_compatible_credentials,
)

pytestmark = pytest.mark.integration

_BUNDLE_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE = _BUNDLE_ROOT / "examples" / "nebius-serverless-chat.json"
_MODEL = "Qwen/Qwen3-0.6B"
_TOKEN = "example-test-token"  # noqa: S105 - only used by the local test server
_USER_ID = "11111111-1111-4111-8111-111111111111"


@contextmanager
def _example_provider():
    """Reuse an existing provider and unregister only a registration we create."""
    already_registered = provider_registry.is_registered("OpenAI Compatible")
    try:
        if not already_registered:
            result = load_extension(_BUNDLE_ROOT / "src" / "lfx_openai_compatible")
            assert result.ok, (result.errors, result.warnings)
        yield
    finally:
        if not already_registered:
            provider_registry.unregister_provider("OpenAI Compatible")


@pytest.fixture
def endpoint(monkeypatch):
    """Serve a small authenticated API on loopback, with real HTTP/SSE framing."""
    requests = []
    # Standalone graph tests do not initialize Langflow's application services.
    # Use LFX's real environment-backed variable service for user-scoped discovery.
    monkeypatch.setitem(get_service_manager().services, ServiceType.VARIABLE_SERVICE, VariableService())

    class Handler(BaseHTTPRequestHandler):
        """Implement the authenticated discovery, chat and SSE test API."""

        def log_message(self, *_args):
            """Suppress routine HTTP access logs in test output."""

        def respond(self, status, data, content_type="application/json"):
            """Send a complete JSON or SSE response with its content length."""
            body = data.encode() if isinstance(data, str) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            """Accept the fixture bearer token or return an authentication error."""
            if self.headers.get("Authorization") == f"Bearer {_TOKEN}":
                return True
            self.respond(401, {"error": {"message": "Invalid token", "type": "authentication_error"}})
            return False

        def do_GET(self):
            """Serve authenticated model discovery and record the request."""
            requests.append(("GET", self.path, self.headers.get("Authorization"), None))
            if not self.authorized():
                return
            if self.path != "/v1/models":
                self.respond(404, {})
                return
            self.respond(200, {"data": [{"id": _MODEL, "object": "model"}]})

        def do_POST(self):
            """Serve authenticated chat completion or SSE and record the request."""
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(("POST", self.path, self.headers.get("Authorization"), data))
            if not self.authorized():
                return
            if self.path != "/v1/chat/completions":
                self.respond(404, {})
                return
            if data["model"] != _MODEL:
                self.respond(400, {"error": {"message": "Unknown model"}})
                return
            common = {"id": "chatcmpl-example", "created": 0, "model": _MODEL}
            if data.get("stream"):
                chunks = [
                    {"delta": {"role": "assistant", "content": "Hello"}, "finish_reason": None},
                    {"delta": {"content": " from the endpoint."}, "finish_reason": None},
                    {"delta": {}, "finish_reason": "stop"},
                ]
                frames = [
                    "data: "
                    + json.dumps({**common, "object": "chat.completion.chunk", "choices": [{"index": 0, **chunk}]})
                    + "\n\n"
                    for chunk in chunks
                ]
                self.respond(200, "".join(frames) + "data: [DONE]\n\n", "text/event-stream")
            else:
                self.respond(
                    200,
                    {
                        **common,
                        "object": "chat.completion",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "Hello from the endpoint."},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
                    },
                )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", _TOKEN)
        # Local connector access is explicitly limited to this test's loopback server.
        monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "true")
        with _example_provider():
            yield requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("stream", [False, True])
def test_imported_example_runs_with_authenticated_provider(endpoint, stream):
    """Execute the exported graph through real authenticated HTTP or SSE."""
    assert [model["name"] for model in fetch_live_openai_compatible_models(_USER_ID)] == [_MODEL]
    payload = json.loads(_EXAMPLE.read_text())
    for node in payload["data"]["nodes"]:
        if node["id"] == "LanguageModelComponent-nebius":
            node["data"]["node"]["template"]["stream"]["value"] = stream
        if node["id"] == "ChatInput-nebius":
            node["data"]["node"]["template"]["input_value"]["value"] = "Say hello."

    # Serialize/reload again to check that no live component objects are needed.
    graph = Graph.from_payload(json.loads(json.dumps(payload)))

    async def run_graph():
        """Consume every graph result so all connected components execute."""
        return [result async for result in graph.async_start()]

    asyncio.run(asyncio.wait_for(run_graph(), timeout=20))
    message = graph.get_vertex("ChatOutput-nebius").results["message"]
    assert message.text == "Hello from the endpoint."
    posts = [request for request in endpoint if request[0] == "POST"]
    assert len(posts) == 1
    _, path, authorization, body = posts[0]
    assert path == "/v1/chat/completions"
    assert authorization == f"Bearer {_TOKEN}"
    assert body["model"] == _MODEL
    assert body["stream"] is stream
    assert body["messages"][-1]["content"] == "Say hello."


def test_wrong_endpoint_token_is_rejected(endpoint, monkeypatch):
    """Reject incorrect credentials in both discovery and provider validation."""
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "incorrect-test-token")
    assert fetch_live_openai_compatible_models(_USER_ID) == []
    url = os.environ["OPENAI_COMPATIBLE_BASE_URL"]
    with pytest.raises(ValueError, match="Authentication failed"):
        validate_openai_compatible_credentials(
            "OpenAI Compatible",
            {"OPENAI_COMPATIBLE_BASE_URL": url, "OPENAI_COMPATIBLE_API_KEY": os.environ["OPENAI_COMPATIBLE_API_KEY"]},
        )
    assert len(endpoint) == 2


def test_provider_scope_preserves_existing_registrations_on_failure():
    """Keep unrelated and reused providers intact, including exceptional teardown."""
    name = "Nebius Example Isolation Sentinel"
    previous = provider_registry.get_provider_descriptor("OpenAI Compatible")
    sentinel = provider_registry.ProviderDescriptor(
        name=name,
        metadata={"mapping": {"model_class": "ChatOpenAI"}},
    )

    def fail_with_nested_provider_scope():
        """Exercise reused-provider cleanup before simulating a graph failure."""
        with _example_provider():
            registered = provider_registry.get_provider_descriptor("OpenAI Compatible")
            assert registered is not None
            with _example_provider():
                assert provider_registry.get_provider_descriptor("OpenAI Compatible") is registered
            assert provider_registry.get_provider_descriptor("OpenAI Compatible") is registered
            assert provider_registry.get_provider_descriptor(name) is sentinel
            message = "simulated graph failure"
            raise RuntimeError(message)

    assert provider_registry.register_provider(sentinel)
    try:
        with pytest.raises(RuntimeError, match="simulated graph failure"):
            fail_with_nested_provider_scope()
        assert provider_registry.get_provider_descriptor("OpenAI Compatible") is previous
        assert provider_registry.get_provider_descriptor(name) is sentinel
    finally:
        provider_registry.unregister_provider(name)
