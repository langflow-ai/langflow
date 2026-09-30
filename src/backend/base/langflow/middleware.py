import re
from urllib.parse import urlencode

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from lfx.log.logger import logger
from lfx.observability import EXECUTION_CLIENT_HEADER, execution_client
from starlette.datastructures import Headers, QueryParams
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from langflow.services.deps import get_settings_service


class MaxFileSizeException(HTTPException):
    def __init__(self, detail: str = "File size is larger than the maximum file size {}MB"):
        super().__init__(status_code=413, detail=detail)


# Adapted from https://github.com/steinnes/content-size-limit-asgi/blob/master/content_size_limit_asgi/middleware.py#L26
class ContentSizeLimitMiddleware:
    """Content size limiting middleware for ASGI applications.

    Args:
      app (ASGI application): ASGI application
      max_content_size (optional): the maximum content size allowed in bytes, None for no limit
      exception_cls (optional): the class of exception to raise (ContentSizeExceeded is the default)
    """

    def __init__(
        self,
        app,
    ):
        self.app = app
        self.logger = logger

    @staticmethod
    def receive_wrapper(receive):
        received = 0

        async def inner():
            max_file_size_upload = get_settings_service().settings.max_file_size_upload
            nonlocal received
            message = await receive()
            if message["type"] != "http.request" or max_file_size_upload is None:
                return message
            body_len = len(message.get("body", b""))
            received += body_len
            if received > max_file_size_upload * 1024 * 1024:
                # max_content_size is in bytes, convert to MB
                received_in_mb = round(received / (1024 * 1024), 3)
                msg = (
                    f"Content size limit exceeded. Maximum allowed is {max_file_size_upload}MB"
                    f" and got {received_in_mb}MB."
                )
                raise MaxFileSizeException(msg)
            return message

        return inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        wrapper = self.receive_wrapper(receive)
        await self.app(scope, wrapper, send)


class ExecutionClientMiddleware:
    """Bind the caller's self-declared client for the life of the request.

    Middleware rather than per-route wiring because every surface wants it and a route that
    forgot would silently report nothing. The value is read from a header rather than the
    request body: the v2 run model rejects extra fields, so a body field would be a public
    schema change, and this is advisory metadata rather than part of the contract.

    Self-reported, so it is spoofable, and execution_client drops anything outside the known
    vocabulary. Never use it for authorization.

    Pure ASGI, like the rest of this module: the binding covers the whole response, streamed
    body included, without relaying each message through BaseHTTPMiddleware's memory stream.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        with execution_client(Headers(scope=scope).get(EXECUTION_CLIENT_HEADER)):
            await self.app(scope, receive, send)


class ForwardedPrefixMiddleware:
    """Honour X-Forwarded-Prefix set by a reverse proxy.

    When a reverse proxy (e.g. Nginx) strips a URL prefix before forwarding
    the request, it can advertise the original prefix via X-Forwarded-Prefix.
    We propagate this into the ASGI ``root_path`` so that transports like
    MCP SSE include the prefix in the POST-back URLs they hand to clients.

    This middleware is only active when ``root_path`` is configured in
    settings (i.e. the operator has explicitly opted into reverse-proxy
    mode).  The header value takes precedence over the static setting
    because the proxy is the runtime source of truth for the prefix.
    """

    def __init__(self, app: ASGIApp, settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.settings.root_path:
            await self.app(scope, receive, send)
            return

        prefix = Headers(scope=scope).get("X-Forwarded-Prefix", "").rstrip("/")
        if prefix and prefix.startswith("/") and "://" not in prefix and "?" not in prefix and "#" not in prefix:
            scope["root_path"] = prefix
        await self.app(scope, receive, send)


class FlattenQueryStringListsMiddleware:
    """Split comma-separated query values into repeated parameters (``?a=1,2`` becomes ``?a=1&a=2``)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        flattened: list[tuple[str, str]] = []
        for key, value in QueryParams(scope["query_string"]).multi_items():
            flattened.extend((key, entry) for entry in value.split(","))

        scope["query_string"] = urlencode(flattened, doseq=True).encode("utf-8")

        await self.app(scope, receive, send)


class LocaleMiddleware:
    """Parse Accept-Language header and store normalised locale in request.state.

    Handles quality values ("fr-FR,fr;q=0.9,en;q=0.8" → "fr") and preserves
    zh-Hans as a full tag. All other locales are reduced to the language code.
    Validates against the loaded locale files and falls back to "en" for unknown
    values — prevents client-supplied headers from polluting the per-locale cache.
    Result is available as request.state.locale in any endpoint.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._supported_locales: frozenset[str] | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._supported_locales is None:
            from langflow.utils.i18n import get_supported_locales

            self._supported_locales = frozenset(get_supported_locales())

        accept_lang = Headers(scope=scope).get("Accept-Language", "en")
        primary = accept_lang.split(",")[0].strip()
        locale = "zh-Hans" if primary.lower().startswith("zh-hans") else primary.split("-")[0]
        if locale not in self._supported_locales:
            locale = "en"
        # The dict request.state reads and writes.
        scope.setdefault("state", {})["locale"] = locale
        await self.app(scope, receive, send)


class MultipartBoundaryMiddleware:
    """Reject a file upload whose multipart boundary is missing, malformed or not framing the body.

    The body is read in full here and replayed to the app as one ``http.request`` message, as
    BaseHTTPMiddleware's cached request did, so ContentSizeLimitMiddleware further in still
    counts every byte. Other paths pass straight through without touching the body.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if "/api/v1/files/upload" not in request.url.path:
            await self.app(scope, receive, send)
            return

        content_type = request.headers.get("Content-Type")

        if not content_type or "multipart/form-data" not in content_type or "boundary=" not in content_type:
            response = JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"detail": "Content-Type header must be 'multipart/form-data' with a boundary parameter."},
            )
            await response(scope, receive, send)
            return

        boundary = content_type.split("boundary=")[-1].strip()

        if not re.match(r"^[\w\-]{1,70}$", boundary):
            response = JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"detail": "Invalid boundary format"},
            )
            await response(scope, receive, send)
            return

        body = await request.body()

        boundary_start = f"--{boundary}".encode()
        # The multipart/form-data spec doesn't require a newline after the boundary, however many clients do
        # implement it that way
        boundary_end = f"--{boundary}--\r\n".encode()
        boundary_end_no_newline = f"--{boundary}--".encode()

        if not body.startswith(boundary_start) or not body.endswith((boundary_end, boundary_end_no_newline)):
            response = JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"detail": "Invalid multipart formatting"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, _replay_body(body, receive), send)


def _replay_body(body: bytes, receive: Receive) -> Receive:
    """Hand the already-read body to the app once, then defer to the server (for the disconnect)."""
    body_sent = False

    async def replay() -> Message:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay
