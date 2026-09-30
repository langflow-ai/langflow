"""Langflow's own HTTP middleware is pure ASGI.

Each layer is pinned to the behaviour it had as a ``BaseHTTPMiddleware``, and the tests drive the
ASGI app directly (not through httpx, whose ASGI transport buffers the whole body) so they can
see every response message as the server would.
"""

import asyncio
import json
from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.testclient import TestClient
from langflow import middleware as middleware_module
from langflow.main import JavaScriptMIMETypeMiddleware, create_app
from langflow.middleware import (
    ContentSizeLimitMiddleware,
    ExecutionClientMiddleware,
    FlattenQueryStringListsMiddleware,
    ForwardedPrefixMiddleware,
    LocaleMiddleware,
    MultipartBoundaryMiddleware,
)
from lfx.observability import get_execution_client
from pydantic_core import PydanticSerializationError
from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.websockets import WebSocket


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


class TestExecutionClientMiddleware:
    @staticmethod
    def _app() -> FastAPI:
        app = FastAPI()
        app.add_middleware(ExecutionClientMiddleware)

        @app.get("/client")
        async def client():
            return PlainTextResponse(str(get_execution_client()))

        @app.get("/stream")
        async def stream():
            async def frames():
                yield f"data: {get_execution_client()}\n\n"
                await asyncio.sleep(0)
                yield f"data: {get_execution_client()}\n\n"

            return StreamingResponse(frames(), media_type="text/event-stream")

        return app

    @pytest.mark.parametrize(
        ("headers", "expected"),
        [
            ({"x-langflow-client": "playground"}, b"playground"),
            ({"X-Langflow-Client": "sdk"}, b"sdk"),
            ({"x-langflow-client": "not-a-real-client"}, b"None"),
            ({}, b"None"),
        ],
    )
    async def test_the_declared_client_is_bound_for_the_handler(self, headers, expected):
        messages = await _call(self._app(), _scope("/client", headers=headers))

        assert _body(messages) == expected

    async def test_the_binding_covers_the_streamed_body_and_is_reset_afterwards(self):
        messages = await _call(self._app(), _scope("/stream", headers={"x-langflow-client": "cli"}))

        assert _body(messages) == b"data: cli\n\ndata: cli\n\n"
        assert get_execution_client() is None


class TestMultipartBoundaryMiddleware:
    BOUNDARY = "----langflowBoundary123"
    UPLOAD = "/api/v1/files/upload/5f0c3a8e-0000-4000-8000-000000000000"

    @classmethod
    def _multipart(cls, content: bytes = b"hello") -> bytes:
        return (
            (
                f"--{cls.BOUNDARY}\r\n"
                'Content-Disposition: form-data; name="file"; filename="a.txt"\r\n'
                "Content-Type: text/plain\r\n\r\n"
            ).encode()
            + content
            + f"\r\n--{cls.BOUNDARY}--\r\n".encode()
        )

    @staticmethod
    def _app(*, inner=None) -> FastAPI:
        app = FastAPI()
        if inner is not None:
            app.add_middleware(inner)
        app.add_middleware(MultipartBoundaryMiddleware)

        @app.post("/api/v1/files/upload/{flow_id}")
        async def upload(flow_id: str, request: Request):
            form = await request.form()
            upload = form["file"]
            return PlainTextResponse(f"{flow_id}:{upload.filename}:{(await upload.read()).decode()}")

        @app.post("/api/v1/echo")
        async def echo(request: Request):
            return PlainTextResponse(await request.body())

        return app

    async def test_a_well_formed_upload_reaches_the_route_intact(self):
        messages = await _call(
            self._app(),
            _scope(
                self.UPLOAD, method="POST", headers={"content-type": f"multipart/form-data; boundary={self.BOUNDARY}"}
            ),
            body=self._multipart(b"file body"),
        )

        assert messages[0]["status"] == 200
        assert _body(messages) == b"5f0c3a8e-0000-4000-8000-000000000000:a.txt:file body"

    @pytest.mark.parametrize(
        ("content_type", "body", "detail"),
        [
            (None, b"", "Content-Type header must be 'multipart/form-data' with a boundary parameter."),
            ("application/json", b"{}", "Content-Type header must be 'multipart/form-data' with a boundary parameter."),
            (
                "multipart/form-data",
                b"",
                "Content-Type header must be 'multipart/form-data' with a boundary parameter.",
            ),
            ("multipart/form-data; boundary=bad boundary!", b"", "Invalid boundary format"),
            ("multipart/form-data; boundary=----langflowBoundary123", b"not multipart", "Invalid multipart formatting"),
        ],
    )
    async def test_a_malformed_upload_is_rejected_with_422(self, content_type, body, detail):
        headers = {"content-type": content_type} if content_type else {}

        messages = await _call(self._app(), _scope(self.UPLOAD, method="POST", headers=headers), body=body)

        assert messages[0]["status"] == 422
        assert json.loads(_body(messages)) == {"detail": detail}

    async def test_other_paths_are_not_checked(self):
        messages = await _call(
            self._app(),
            _scope("/api/v1/echo", method="POST", headers={"content-type": "application/json"}),
            body=b'{"not": "multipart"}',
        )

        assert messages[0]["status"] == 200
        assert _body(messages) == b'{"not": "multipart"}'

    async def test_the_replayed_body_still_counts_against_the_upload_size_limit(self, monkeypatch):
        monkeypatch.setattr(
            middleware_module,
            "get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace(max_file_size_upload=1)),
        )
        body = self._multipart(b"x" * (1024 * 1024 + 1))

        messages = await _call(
            self._app(inner=ContentSizeLimitMiddleware),
            _scope(
                self.UPLOAD, method="POST", headers={"content-type": f"multipart/form-data; boundary={self.BOUNDARY}"}
            ),
            body=body,
        )

        assert messages[0]["status"] == 413


class TestForwardedPrefixMiddleware:
    @staticmethod
    async def _downstream_root_path(settings, headers: dict[str, str]) -> str:
        seen = {}

        async def app(scope, receive, send):
            seen["root_path"] = scope["root_path"]
            await PlainTextResponse("ok")(scope, receive, send)

        await _call(ForwardedPrefixMiddleware(app, settings=settings), _scope("/api/v1/mcp/sse", headers=headers))
        return seen["root_path"]

    async def test_the_header_sets_root_path_when_root_path_is_configured(self):
        settings = SimpleNamespace(root_path="/configured")

        assert await self._downstream_root_path(settings, {"X-Forwarded-Prefix": "/langflow/"}) == "/langflow"

    @pytest.mark.parametrize("prefix", ["https://evil.com", "/path?query=1", "/path#fragment", "no-slash", "", "/"])
    async def test_an_invalid_prefix_is_ignored(self, prefix):
        settings = SimpleNamespace(root_path="/configured")

        assert await self._downstream_root_path(settings, {"X-Forwarded-Prefix": prefix}) == ""

    async def test_the_header_is_ignored_unless_root_path_is_configured_at_request_time(self):
        settings = SimpleNamespace(root_path="")
        headers = {"X-Forwarded-Prefix": "/attacker-prefix"}

        assert await self._downstream_root_path(settings, headers) == ""
        settings.root_path = "/configured"
        assert await self._downstream_root_path(settings, headers) == "/attacker-prefix"


class TestFlattenQueryStringListsMiddleware:
    @staticmethod
    def _app() -> FastAPI:
        app = FastAPI()
        app.add_middleware(FlattenQueryStringListsMiddleware)

        @app.get("/flows")
        async def flows(request: Request, flow_id: Annotated[list[str], Query()] = []):  # noqa: B006
            return {"flow_id": flow_id, "query_string": request.scope["query_string"].decode()}

        return app

    @pytest.mark.parametrize(
        ("query_string", "flow_ids", "rewritten"),
        [
            (b"flow_id=a,b&flow_id=c", ["a", "b", "c"], "flow_id=a&flow_id=b&flow_id=c"),
            (b"flow_id=a%2Cb", ["a", "b"], "flow_id=a&flow_id=b"),
            (b"flow_id=a&other=x+y", ["a"], "flow_id=a&other=x+y"),
            (b"flow_id=", [""], "flow_id="),
            (b"", [], ""),
        ],
    )
    async def test_comma_separated_values_become_repeated_parameters(self, query_string, flow_ids, rewritten):
        messages = await _call(self._app(), _scope("/flows", query_string=query_string))

        assert json.loads(_body(messages)) == {"flow_id": flow_ids, "query_string": rewritten}


class TestLocaleMiddleware:
    @staticmethod
    def _app() -> FastAPI:
        app = FastAPI()
        app.add_middleware(LocaleMiddleware)

        @app.get("/locale")
        async def locale(request: Request):
            return PlainTextResponse(request.state.locale)

        return app

    @pytest.mark.parametrize(
        ("accept_language", "expected"),
        [
            ("fr-FR,fr;q=0.9,en;q=0.8", b"fr"),
            ("zh-Hans-CN,zh;q=0.9", b"zh-Hans"),
            ("ZH-HANS", b"zh-Hans"),
            ("de", b"de"),
            ("xx-YY", b"en"),
            ("", b"en"),
            (None, b"en"),
        ],
    )
    async def test_the_locale_is_normalised_into_request_state(self, accept_language, expected):
        headers = {"accept-language": accept_language} if accept_language is not None else {}

        messages = await _call(self._app(), _scope("/locale", headers=headers))

        assert _body(messages) == expected


class TestLangflowMiddlewareStack:
    """The real app: registration order, and a streamed response through every layer."""

    def test_the_http_layers_keep_their_order_and_none_is_base_http_middleware(self):
        app = create_app()
        classes = [middleware.cls for middleware in app.user_middleware]

        assert classes[:7] == [
            LocaleMiddleware,
            FlattenQueryStringListsMiddleware,
            ForwardedPrefixMiddleware,
            MultipartBoundaryMiddleware,
            ExecutionClientMiddleware,
            JavaScriptMIMETypeMiddleware,
            CORSMiddleware,
        ]
        assert classes[-2:] == [ContentSizeLimitMiddleware, GZipMiddleware]
        assert not any(isinstance(cls, type) and issubclass(cls, BaseHTTPMiddleware) for cls in classes)

    async def test_sse_frames_pass_every_layer_unbuffered_and_in_order(self):
        app = create_app()
        first_frame_out = asyncio.Event()
        background_ran = asyncio.Event()
        order: list[str] = []

        async def after_response():
            order.append("background")
            background_ran.set()

        @app.get("/api/v2/_middleware_probe")
        async def probe(request: Request, tag: Annotated[list[str], Query()] = []):  # noqa: B006
            async def frames():
                context = {"locale": request.state.locale, "client": get_execution_client(), "tag": tag}
                yield f"data: {json.dumps(context)}\n\n"
                # Only reachable once frame 1 has left the outermost layer.
                await asyncio.wait_for(first_frame_out.wait(), timeout=5)
                for index in range(2, 6):
                    yield f"data: {index}\n\n"

            return StreamingResponse(
                frames(), media_type="text/event-stream", background=BackgroundTask(after_response)
            )

        async def on_send(message):
            if message["type"] == "http.response.body":
                order.append("body" if message.get("more_body") else "end")
                if message.get("body", b"").startswith(b"data: {"):
                    first_frame_out.set()

        messages = await _call(
            app,
            _scope(
                "/api/v2/_middleware_probe",
                headers={
                    "accept-language": "fr-FR,fr;q=0.9",
                    "x-langflow-client": "sdk",
                    "origin": "https://app.example.com",
                    "accept-encoding": "gzip",
                },
                query_string=b"tag=a,b",
            ),
            on_send=on_send,
        )

        headers = _headers(messages)
        assert messages[0]["status"] == 200
        assert headers["content-type"].startswith("text/event-stream")
        assert "access-control-allow-origin" in headers  # CORS still decorates a streamed response
        assert "content-encoding" not in headers  # event streams stay uncompressed
        bodies = [m["body"] for m in messages if m["type"] == "http.response.body"]
        # One message per frame: nothing coalesced or re-chunked on the way out.
        assert bodies[0] == b'data: {"locale": "fr", "client": "sdk", "tag": ["a", "b"]}\n\n'
        assert bodies[1:] == [b"data: 2\n\n", b"data: 3\n\n", b"data: 4\n\n", b"data: 5\n\n", b""]
        assert background_ran.is_set()
        assert order == ["body"] * 5 + ["end", "background"]

    def test_websockets_pass_through_every_layer(self):
        app = create_app()

        @app.websocket("/api/v1/_middleware_probe_ws")
        async def echo(websocket: WebSocket):
            await websocket.accept()
            await websocket.send_text(await websocket.receive_text())
            await websocket.close()

        with TestClient(app).websocket_connect("/api/v1/_middleware_probe_ws?tag=a,b") as websocket:
            websocket.send_text("ping")
            assert websocket.receive_text() == "ping"
