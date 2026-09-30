"""Langflow's own HTTP middleware is pure ASGI.

Each layer is pinned to the behaviour it had as a ``BaseHTTPMiddleware``, and the tests drive the
ASGI app directly (not through httpx, whose ASGI transport buffers the whole body) so they can
see every response message as the server would.
"""

import asyncio
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from langflow.main import JavaScriptMIMETypeMiddleware
from pydantic_core import PydanticSerializationError


def _scope(path: str, *, method: str = "GET", headers: dict[str, str] | None = None, query_string: bytes = b""):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": query_string,
        "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }


async def _call(app, scope: dict, *, body: bytes = b"", on_send=None) -> list[dict]:
    """Run one HTTP request through ``app`` and return every message it sent, in order."""
    sent: list[dict] = []
    request_delivered = False
    never = asyncio.Event()

    async def receive():
        nonlocal request_delivered
        if not request_delivered:
            request_delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        await never.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)
        if on_send is not None:
            await on_send(message)

    await asyncio.wait_for(app(scope, receive, send), timeout=10)
    return sent


def _headers(messages: list[dict]) -> dict[str, str]:
    start = next(message for message in messages if message["type"] == "http.response.start")
    return {key.decode(): value.decode() for key, value in start["headers"]}


def _body(messages: list[dict]) -> bytes:
    return b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")


class TestJavaScriptMIMETypeMiddleware:
    @staticmethod
    def _app(status_code: int = 200) -> FastAPI:
        app = FastAPI()
        app.add_middleware(JavaScriptMIMETypeMiddleware)

        @app.get("/{path:path}")
        async def asset(path: str):
            return PlainTextResponse(f"// {path}", status_code=status_code, media_type="application/octet-stream")

        return app

    async def test_js_path_is_served_as_javascript(self):
        messages = await _call(self._app(), _scope("/assets/index-abc.js"))

        assert _headers(messages)["content-type"] == "text/javascript"
        assert _body(messages) == b"// assets/index-abc.js"

    async def test_content_type_is_replaced_not_duplicated(self):
        messages = await _call(self._app(), _scope("/assets/index-abc.js"))

        start = messages[0]
        assert [key for key, _ in start["headers"]].count(b"content-type") == 1

    @pytest.mark.parametrize(
        ("path", "status_code"),
        [
            ("/api/v1/files/download/flow/script.js", 200),  # user files keep their stored type
            ("/assets/index-abc.css", 200),
            ("/assets/missing.js", 404),
        ],
    )
    async def test_other_responses_keep_their_content_type(self, path, status_code):
        messages = await _call(self._app(status_code), _scope(path))

        assert _headers(messages)["content-type"] == "application/octet-stream"

    async def test_streamed_js_response_is_rewritten_and_passed_through_unbuffered(self):
        app = FastAPI()
        app.add_middleware(JavaScriptMIMETypeMiddleware)
        first_chunk_sent = asyncio.Event()

        @app.get("/bundle.js")
        async def bundle():
            async def chunks():
                yield b"one;"
                # Only reachable if the first chunk already left the middleware.
                await asyncio.wait_for(first_chunk_sent.wait(), timeout=5)
                yield b"two;"

            return StreamingResponse(chunks(), media_type="application/octet-stream")

        async def on_send(message):
            if message["type"] == "http.response.body" and message.get("body") == b"one;":
                first_chunk_sent.set()

        messages = await _call(app, _scope("/bundle.js"), on_send=on_send)

        assert _headers(messages)["content-type"] == "text/javascript"
        assert [m.get("body") for m in messages if m["type"] == "http.response.body"] == [b"one;", b"two;", b""]

    async def test_serialization_error_before_the_response_becomes_a_500(self):
        async def app(_scope, _receive, _send):
            msg = "Unable to serialize unknown type: <class 'object'>"
            raise PydanticSerializationError(msg)

        with pytest.raises(HTTPException) as raised:
            await _call(JavaScriptMIMETypeMiddleware(app), _scope("/api/v1/flows/"))

        assert raised.value.status_code == 500
        message, detail = json.loads(raised.value.detail)
        assert message.startswith("Something went wrong while serializing the response.")
        assert detail == "Unable to serialize unknown type: <class 'object'>"
        assert isinstance(raised.value.__cause__, PydanticSerializationError)

    async def test_serialization_error_after_the_response_started_propagates_unchanged(self):
        async def app(_scope, _receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            msg = "late"
            raise PydanticSerializationError(msg)

        with pytest.raises(PydanticSerializationError):
            await _call(JavaScriptMIMETypeMiddleware(app), _scope("/api/v1/flows/"))

    async def test_other_errors_propagate_unchanged(self):
        async def app(_scope, _receive, _send):
            msg = "boom"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="boom"):
            await _call(JavaScriptMIMETypeMiddleware(app), _scope("/assets/index.js"))

    async def test_websocket_and_lifespan_scopes_pass_through(self):
        seen = []

        async def app(scope, _receive, _send):
            seen.append(scope["type"])

        middleware = JavaScriptMIMETypeMiddleware(app)
        await middleware({"type": "websocket", "path": "/ws"}, None, None)
        await middleware({"type": "lifespan"}, None, None)

        assert seen == ["websocket", "lifespan"]
