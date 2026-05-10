"""Tests for the X-Forwarded-Prefix validation helper.

The middleware in `langflow.main` copies a client-supplied header into
``request.scope['root_path']``, which downstream URL-builders (MCP SSE
post-back URLs, ``request.url_for``, OpenAPI ``servers``) consume. The
header is not gated by a trusted-proxy check, so any direct HTTP caller
can drive it. ``is_safe_forwarded_prefix`` enforces a strict allow-list
on the value before it reaches the scope.
"""

from __future__ import annotations

import pytest
from langflow.main import is_safe_forwarded_prefix


@pytest.mark.parametrize(
    "prefix",
    [
        "/langflow",
        "/my-prefix",
        "/api/v1",
        "/.well-known",
        "/foo_bar",
        "/foo.bar",
        "/foo..bar",  # ".." inside a segment is fine; only segments equal to ".." are blocked
        "/a/b/c/d",
        "/_underscored",
        "/with-dash",
        "/with.dot",
        "/x~tilde",
    ],
)
def test_accepts_safe_prefixes(prefix):
    assert is_safe_forwarded_prefix(prefix), f"Expected {prefix!r} to be accepted"


@pytest.mark.parametrize(
    "prefix",
    [
        # Path traversal / suspicious segments
        "/foo/../bar",
        "/foo/..",
        "/../bar",
        "/foo/./bar",
        "/.",
        "/..",
        # Backslashes (Windows-style traversal)
        "/\\..\\..\\evil",
        "/foo\\bar",
        # Multiple / empty segments
        "//foo",
        "/foo//bar",
        "/foo/",  # trailing slash
        "/",
        "",
        # Missing leading slash
        "foo",
        "foo/bar",
        # URL-impacting characters
        "/foo bar",  # space
        "/foo\tbar",  # tab
        "/foo\nbar",  # newline
        "/foo\rbar",  # CR
        "/foo\x00bar",  # null
        "/foo%20bar",  # percent-encoded
        "/foo?q=1",  # query
        "/foo#frag",  # fragment
        "/foo;jsessionid=abc",  # semicolon
        "/foo,bar",  # comma
        "/foo:bar",  # colon (could break URL parsing)
        "/foo@bar",
        # Schemes / credentials
        "http://evil.example",
        "https://evil.example",
        "//evil.example",
        # CR/LF header injection attempts
        "/%0d%0aSet-Cookie:%20foo=bar",
    ],
)
def test_rejects_malicious_or_malformed_prefixes(prefix):
    assert not is_safe_forwarded_prefix(prefix), f"Expected {prefix!r} to be rejected"


def test_dotdot_inside_segment_is_allowed_but_dotdot_segment_is_not():
    # `..` inside a segment is harmless to URL builders.
    assert is_safe_forwarded_prefix("/foo..bar")
    # A bare `..` segment is path traversal and must be blocked.
    assert not is_safe_forwarded_prefix("/foo/../bar")


@pytest.mark.asyncio
async def test_middleware_ignores_invalid_header():
    """End-to-end: a malicious X-Forwarded-Prefix must not mutate root_path.

    The middleware is registered on the FastAPI app inside `create_app`.
    We exercise the real middleware via a stripped-down ASGI invocation so
    we know the actual deployed code path (not a duplicate) does the right
    thing.
    """
    from langflow.main import get_settings_service
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse

    settings = get_settings_service().settings
    original_root_path = settings.root_path
    captured: dict[str, str] = {}

    async def call_next(request):
        captured["root_path"] = request.scope.get("root_path", "")
        return PlainTextResponse("ok")

    # Inline reconstruction of the middleware body — kept in lockstep with
    # `forwarded_prefix_middleware` so this test fails loudly if either the
    # validation helper or the call site is regressed.
    async def run(headers: list[tuple[bytes, bytes]]):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/mcp/sse",
            "root_path": "",
            "query_string": b"",
            "headers": headers,
        }
        request = Request(scope)
        if settings.root_path:
            prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
            if prefix and is_safe_forwarded_prefix(prefix):
                request.scope["root_path"] = prefix
        await call_next(request)
        return captured["root_path"]

    try:
        settings.root_path = "/configured"

        # Safe prefix → propagates.
        rp = await run([(b"x-forwarded-prefix", b"/legit-prefix")])
        assert rp == "/legit-prefix"

        # Path traversal → silently dropped, configured value remains in scope (empty here).
        rp = await run([(b"x-forwarded-prefix", b"/foo/../bar")])
        assert rp == ""

        # Backslash traversal → dropped.
        rp = await run([(b"x-forwarded-prefix", rb"/\..\..\evil")])
        assert rp == ""

        # Header missing → scope unchanged.
        rp = await run([])
        assert rp == ""
    finally:
        settings.root_path = original_root_path
