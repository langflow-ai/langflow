from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from fastapi import HTTPException
from lfx.log.logger import logger
from starlette.datastructures import QueryParams

if TYPE_CHECKING:
    from lfx.services.settings.base import Settings
    from starlette.types import ASGIApp, Receive, Scope, Send


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
        app: ASGIApp,
    ):
        self.app = app
        self.logger = logger

    @staticmethod
    def receive_wrapper(receive: Receive):
        received = 0

        async def inner():
            from langflow.services.deps import get_settings_service

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

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        wrapper = self.receive_wrapper(receive)
        await self.app(scope, wrapper, send)


FORWARDED_PREFIX_RE = re.compile(r"(?:/[a-zA-Z0-9._~-]+)+")
DEFAULT_VERBATIM_QUERY_PARAMS = frozenset({"q"})


class ForwardedPrefixMiddleware:
    """Honour X-Forwarded-Prefix set by a reverse proxy.

    When a reverse proxy (e.g. Nginx) strips a URL prefix before forwarding
    the request, it can advertise the original prefix via X-Forwarded-Prefix.
    We propagate this into the ASGI ``root_path`` so that transports like
    MCP SSE include the prefix in the POST-back URLs they hand to clients.

    This middleware is only active when ``root_path`` is configured in
    settings (i.e. the operator has explicitly opted into reverse-proxy
    mode). The header value takes precedence over the static setting
    because the proxy is the runtime source of truth for the prefix.
    """

    def __init__(
        self,
        app: ASGIApp,
        settings: Settings | None = None,
    ) -> None:
        self.app = app
        self._settings = settings

    @property
    def settings(self) -> Settings:
        if self._settings is not None:
            return self._settings
        from langflow.services.deps import get_settings_service

        return get_settings_service().settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not self.settings.root_path:
            await self.app(scope, receive, send)
            return

        prefix = ""
        for key, value in scope.get("headers", []):
            if key.lower() == b"x-forwarded-prefix":
                prefix = value.decode("latin-1", errors="replace").rstrip("/")
                break

        # Restrict transport URLs to path segments that cannot change their origin.
        if FORWARDED_PREFIX_RE.fullmatch(prefix) and not any(part in {".", ".."} for part in prefix.split("/")):
            scope["root_path"] = prefix

        await self.app(scope, receive, send)


class FlattenQueryStringMiddleware:
    """Expand comma-separated query values into repeated query parameters."""

    def __init__(
        self,
        app: ASGIApp,
        verbatim_params: frozenset[str] | set[str] | None = None,
    ) -> None:
        self.app = app
        self.verbatim_params = DEFAULT_VERBATIM_QUERY_PARAMS if verbatim_params is None else verbatim_params

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        query_string = scope.get("query_string", b"")
        if not query_string:
            await self.app(scope, receive, send)
            return

        qp = QueryParams(query_string)
        flattened: list[tuple[str, str]] = []
        for key, value in qp.multi_items():
            if key in self.verbatim_params:
                flattened.append((key, value))
            else:
                flattened.extend((key, entry) for entry in value.split(","))

        scope["query_string"] = urlencode(flattened, doseq=True).encode("utf-8")
        await self.app(scope, receive, send)


class SetLocaleMiddleware:
    """Parse Accept-Language header and store normalised locale in request.state.

    Handles quality values ("fr-FR,fr;q=0.9,en;q=0.8" → "fr") and preserves
    zh-Hans as a full tag. All other locales are reduced to the language code.
    Validates against the loaded locale files and falls back to "en" for unknown
    values — prevents client-supplied headers from polluting the per-locale cache.
    Result is available as request.state.locale in any endpoint.
    """

    def __init__(
        self,
        app: ASGIApp,
        supported_locales: frozenset[str] | set[str] | None = None,
    ) -> None:
        self.app = app
        self._supported_locales = supported_locales

    @property
    def supported_locales(self) -> frozenset[str] | set[str]:
        if self._supported_locales is None:
            from langflow.utils.i18n import get_supported_locales

            self._supported_locales = frozenset(get_supported_locales())
        return self._supported_locales

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        accept_lang = "en"
        for key, value in scope.get("headers", []):
            if key.lower() == b"accept-language":
                accept_lang = value.decode("latin-1", errors="replace")
                break

        primary = accept_lang.split(",")[0].strip()
        locale = "zh-Hans" if primary.lower().startswith("zh-hans") else primary.split("-")[0]
        if locale not in self.supported_locales:
            locale = "en"

        state = scope.get("state")
        if state is None:
            state = {}
            scope["state"] = state
        if isinstance(state, dict):
            state["locale"] = locale
        else:
            state.locale = locale

        await self.app(scope, receive, send)


__all__ = [
    "DEFAULT_VERBATIM_QUERY_PARAMS",
    "ContentSizeLimitMiddleware",
    "FlattenQueryStringMiddleware",
    "ForwardedPrefixMiddleware",
    "MaxFileSizeException",
    "SetLocaleMiddleware",
]
