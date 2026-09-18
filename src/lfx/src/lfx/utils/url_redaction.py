"""Strip credentials out of URLs before they reach anyone reading a message.

A URL is a common carrier for a secret — userinfo and query strings both routinely hold
one — and the places a URL ends up (error messages, tracebacks, log aggregators, support
tickets) are exactly the places a secret must not. The reduction is deliberate rather than
clever: keep enough to identify the target, drop everything that can authenticate to it.
"""

import logging
import re
from contextlib import asynccontextmanager
from contextvars import ContextVar
from urllib.parse import urlparse

_sensitive_http_request: ContextVar[bool] = ContextVar("sensitive_http_request", default=False)


class _SensitiveHTTPLogFilter(logging.Filter):
    def filter(self, _record: logging.LogRecord) -> bool:
        return not _sensitive_http_request.get()


_sensitive_http_filter = _SensitiveHTTPLogFilter()


@asynccontextmanager
async def suppress_sensitive_http_logs():
    """Keep preauthenticated URLs and redirect headers out of HTTP transport logs.

    The filter is task-local, so concurrent ordinary requests keep their logs.
    HTTPX logs full request URLs at INFO; HTTP Core logs response headers (which
    can include signed download locations) at DEBUG.
    """
    names = {"httpx", "httpcore"}
    names.update(f"httpcore.{suffix}" for suffix in ("connection", "http11", "http2", "proxy", "socks_proxy"))
    names.update(name for name in logging.Logger.manager.loggerDict.copy() if name.startswith("httpcore."))
    for name in names:
        logging.getLogger(name).addFilter(_sensitive_http_filter)
    token = _sensitive_http_request.set(True)
    try:
        yield
    finally:
        _sensitive_http_request.reset(token)


URL_IN_TEXT_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s'\"<>]+")


def sanitize_url_for_display(url: str) -> str:
    """Reduce a URL to scheme, host, port and path.

    The port has to survive: a target named without it is the wrong target whenever the
    plane runs on anything but 80/443.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if not parsed.scheme or not parsed.hostname:
        return url
    host = f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
    return f"{parsed.scheme}://{host}{parsed.path}"


def redact_urls_in_text(text: str) -> str:
    """Sanitize every URL embedded in text we did not compose.

    Formatting our own targets safely is not enough. ``raise_for_status`` builds a message
    containing the full request URL, so a 401 arrives carrying the credential it just
    rejected, and that message is reproduced verbatim inside any traceback that crosses it.
    """
    return URL_IN_TEXT_PATTERN.sub(lambda match: sanitize_url_for_display(match.group(0)), text)
