from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from langflow.middleware import (
    FlattenQueryStringMiddleware,
    ForwardedPrefixMiddleware,
    SetLocaleMiddleware,
)
from starlette.datastructures import State

if TYPE_CHECKING:
    from starlette.types import Scope


class MockSettings:
    def __init__(self, root_path: str = "") -> None:
        self.root_path = root_path


class TestForwardedPrefixMiddleware:
    """Test ForwardedPrefixMiddleware as pure ASGI middleware."""

    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self):
        called = False

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal called
            called = True
            assert scope["type"] == "websocket"

        mw = ForwardedPrefixMiddleware(inner_app, settings=MockSettings("/enabled"))
        scope = {"type": "websocket"}
        await mw(scope, None, None)
        assert called

    @pytest.mark.asyncio
    @pytest.mark.parametrize("prefix", ["/langflow", "/my-prefix", "/tools/langflow/", "/v1.2/~instance_1"])
    async def test_valid_prefix_updates_root_path(self, prefix: str):
        captured_root_path = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_root_path
            captured_root_path = scope.get("root_path")

        mw = ForwardedPrefixMiddleware(inner_app, settings=MockSettings("/enabled"))
        scope = {
            "type": "http",
            "root_path": "/enabled",
            "headers": [(b"x-forwarded-prefix", prefix.encode())],
        }
        await mw(scope, None, None)
        assert captured_root_path == prefix.rstrip("/")

    @pytest.mark.asyncio
    async def test_disabled_root_path_ignores_header(self):
        captured_root_path = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_root_path
            captured_root_path = scope.get("root_path")

        mw = ForwardedPrefixMiddleware(inner_app, settings=MockSettings(""))
        scope = {
            "type": "http",
            "root_path": "",
            "headers": [(b"x-forwarded-prefix", b"/proxy-prefix")],
        }
        await mw(scope, None, None)
        assert captured_root_path == ""

    @pytest.mark.asyncio
    async def test_missing_header_preserves_root_path(self):
        captured_root_path = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_root_path
            captured_root_path = scope.get("root_path")

        mw = ForwardedPrefixMiddleware(inner_app, settings=MockSettings("/default"))
        scope = {
            "type": "http",
            "root_path": "/default",
            "headers": [(b"accept", b"*/*")],
        }
        await mw(scope, None, None)
        assert captured_root_path == "/default"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "prefix",
        [
            "https://evil.example",
            "//evil.example",
            "///evil.example",
            r"/\evil.example",
            r"/path\evil.example",
            "/%2f%2fevil.example",
            "/%252f%252fevil.example",
            "/%5cevil.example",
            "/.",
            "/..",
            "/path/../other",
            "/path/./other",
            "/%2e%2e/other",
            "/path?query=1",
            "/path#fragment",
            "not-starting-with-slash",
            "/path//other",
            "/path with spaces",
            "/path\t/other",
            "/path\n/other",
            "",
            "/",
        ],
    )
    async def test_invalid_prefix_preserves_existing_root_path(self, prefix: str):
        captured_root_path = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_root_path
            captured_root_path = scope.get("root_path")

        mw = ForwardedPrefixMiddleware(inner_app, settings=MockSettings("/enabled"))
        scope = {
            "type": "http",
            "root_path": "/enabled",
            "headers": [(b"x-forwarded-prefix", prefix.encode())],
        }
        await mw(scope, None, None)
        assert captured_root_path == "/enabled"


class TestFlattenQueryStringMiddleware:
    """Test FlattenQueryStringMiddleware as pure ASGI middleware."""

    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self):
        called = False

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal called
            called = True
            assert scope["type"] == "lifespan"

        mw = FlattenQueryStringMiddleware(inner_app)
        scope = {"type": "lifespan"}
        await mw(scope, None, None)
        assert called

    @pytest.mark.asyncio
    async def test_empty_query_string_passthrough(self):
        captured_qs = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_qs
            captured_qs = scope.get("query_string")

        mw = FlattenQueryStringMiddleware(inner_app)
        scope = {"type": "http", "query_string": b""}
        await mw(scope, None, None)
        assert captured_qs == b""

    @pytest.mark.asyncio
    async def test_comma_separated_values_flattened(self):
        captured_qs = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_qs
            captured_qs = scope.get("query_string")

        mw = FlattenQueryStringMiddleware(inner_app)
        scope = {"type": "http", "query_string": b"tags=alpha,beta,gamma&active=true"}
        await mw(scope, None, None)
        assert captured_qs == b"tags=alpha&tags=beta&tags=gamma&active=true"

    @pytest.mark.asyncio
    async def test_verbatim_params_preserved(self):
        captured_qs = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_qs
            captured_qs = scope.get("query_string")

        mw = FlattenQueryStringMiddleware(inner_app, verbatim_params=frozenset({"q", "search"}))
        scope = {"type": "http", "query_string": b"tags=1,2&q=foo,bar&search=alice,bob"}
        await mw(scope, None, None)
        assert captured_qs == b"tags=1&tags=2&q=foo%2Cbar&search=alice%2Cbob"

    @pytest.mark.asyncio
    async def test_repeated_existing_keys_preserved(self):
        captured_qs = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_qs
            captured_qs = scope.get("query_string")

        mw = FlattenQueryStringMiddleware(inner_app)
        scope = {"type": "http", "query_string": b"id=1&id=2&id=3,4"}
        await mw(scope, None, None)
        assert captured_qs == b"id=1&id=2&id=3&id=4"


class TestSetLocaleMiddleware:
    """Test SetLocaleMiddleware as pure ASGI middleware."""

    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self):
        called = False

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal called
            called = True
            assert scope["type"] == "websocket"

        mw = SetLocaleMiddleware(inner_app)
        scope = {"type": "websocket"}
        await mw(scope, None, None)
        assert called

    @pytest.mark.asyncio
    async def test_extract_quality_value_locale(self):
        captured_locale = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_locale
            captured_locale = scope["state"]["locale"]

        mw = SetLocaleMiddleware(inner_app, supported_locales=frozenset({"en", "fr", "es"}))
        scope = {
            "type": "http",
            "headers": [(b"accept-language", b"fr-FR,fr;q=0.9,en;q=0.8")],
        }
        await mw(scope, None, None)
        assert captured_locale == "fr"

    @pytest.mark.asyncio
    async def test_preserves_zh_hans(self):
        captured_locale = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_locale
            captured_locale = scope["state"]["locale"]

        mw = SetLocaleMiddleware(inner_app, supported_locales=frozenset({"en", "zh-Hans"}))
        scope = {
            "type": "http",
            "headers": [(b"accept-language", b"zh-Hans-CN,zh;q=0.9")],
        }
        await mw(scope, None, None)
        assert captured_locale == "zh-Hans"

    @pytest.mark.asyncio
    async def test_unknown_locale_fallback_to_en(self):
        captured_locale = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_locale
            captured_locale = scope["state"]["locale"]

        mw = SetLocaleMiddleware(inner_app, supported_locales=frozenset({"en", "fr"}))
        scope = {
            "type": "http",
            "headers": [(b"accept-language", b"xx-YY,xx;q=0.9")],
        }
        await mw(scope, None, None)
        assert captured_locale == "en"

    @pytest.mark.asyncio
    async def test_missing_accept_language_defaults_to_en(self):
        captured_locale = None

        async def inner_app(scope: Scope, _receive, _send):
            nonlocal captured_locale
            captured_locale = scope["state"]["locale"]

        mw = SetLocaleMiddleware(inner_app, supported_locales=frozenset({"en", "fr"}))
        scope = {"type": "http", "headers": []}
        await mw(scope, None, None)
        assert captured_locale == "en"

    @pytest.mark.asyncio
    async def test_preserves_existing_state(self):
        scope_state = State({"user_id": 42})

        async def inner_app(scope: Scope, _receive, _send):
            assert scope["state"]["user_id"] == 42
            assert scope["state"]["locale"] == "en"

        mw = SetLocaleMiddleware(inner_app, supported_locales=frozenset({"en"}))
        scope = {"type": "http", "headers": [], "state": scope_state}
        await mw(scope, None, None)

    @pytest.mark.asyncio
    async def test_lazy_supported_locales_loader(self):
        async def inner_app(_scope: Scope, _receive, _send):
            pass

        mw = SetLocaleMiddleware(inner_app)
        assert "en" in mw.supported_locales
        assert "zh-Hans" in mw.supported_locales


class TestMiddlewarePipeline:
    """Test composed ASGI middleware stack."""

    @pytest.mark.asyncio
    async def test_pipeline_order_and_cooperation(self):
        captured = {}

        async def terminal_app(scope: Scope, _receive, _send):
            captured["root_path"] = scope.get("root_path")
            captured["query_string"] = scope.get("query_string")
            captured["locale"] = scope.get("state", {}).get("locale")

        settings = MockSettings("/proxy")
        app = ForwardedPrefixMiddleware(terminal_app, settings=settings)
        app = FlattenQueryStringMiddleware(app, verbatim_params=frozenset({"q"}))
        app = SetLocaleMiddleware(app, supported_locales=frozenset({"en", "pt"}))

        scope = {
            "type": "http",
            "root_path": "/proxy",
            "headers": [
                (b"x-forwarded-prefix", b"/api/v2"),
                (b"accept-language", b"pt-BR,pt;q=0.9"),
            ],
            "query_string": b"tags=red,blue&q=hello,world",
        }

        await app(scope, None, None)

        assert captured["root_path"] == "/api/v2"
        assert captured["query_string"] == b"tags=red&tags=blue&q=hello%2Cworld"
        assert captured["locale"] == "pt"

    @pytest.mark.asyncio
    async def test_downstream_exception_propagates_cleanly(self):
        class CustomError(Exception):
            pass

        msg = "pipeline failed"

        async def failing_app(_scope: Scope, _receive, _send):
            raise CustomError(msg)

        settings = MockSettings("/proxy")
        app = ForwardedPrefixMiddleware(failing_app, settings=settings)
        app = FlattenQueryStringMiddleware(app)
        app = SetLocaleMiddleware(app, supported_locales=frozenset({"en"}))

        scope = {
            "type": "http",
            "headers": [(b"accept-language", b"en")],
            "query_string": b"foo=bar",
        }

        with pytest.raises(CustomError, match="pipeline failed"):
            await app(scope, None, None)
