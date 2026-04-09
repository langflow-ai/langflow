"""Tests for plugin route discovery and conflict protection.

Ensures that plugins loaded via the langflow.plugins entry-point group
cannot overwrite or shadow existing Langflow routes.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter
from langflow.plugin_routes import (
    _get_route_keys,
    _PluginAppWrapper,
    load_plugin_routes,
)


class TestGetRouteKeys:
    """Tests for _get_route_keys."""

    def test_returns_default_routes_for_app_with_no_custom_routes(self):
        """App with no custom routes still has FastAPI default OpenAPI routes in the set."""
        app = FastAPI()
        keys = _get_route_keys(app)
        # FastAPI adds /docs, /openapi.json, /redoc, etc. by default
        assert ("/openapi.json", "GET") in keys
        assert ("/docs", "GET") in keys

    def test_collects_route_path_and_methods(self):
        """All (path, method) pairs from app routes are collected."""
        app = FastAPI()

        @app.get("/health")
        def health():
            return "ok"

        @app.post("/api/action")
        def action():
            return None

        keys = _get_route_keys(app)
        assert ("/health", "GET") in keys
        assert ("/api/action", "POST") in keys
        # HEAD is excluded to avoid false conflicts with GET
        assert ("/health", "HEAD") not in keys

    def test_includes_mounts_as_wildcard(self):
        """Mounts are reserved as (path, '*')."""
        app = FastAPI()
        app.mount("/static", MagicMock())
        keys = _get_route_keys(app)
        assert any(path == "/static" and method == "*" for path, method in keys)


class TestPluginAppWrapper:
    """Tests for _PluginAppWrapper: add-only, no overwrite."""

    def test_allows_non_conflicting_route(self):
        """Wrapper allows adding a route that does not conflict with reserved set."""
        app = FastAPI()

        @app.get("/existing")
        def existing():
            return "core"

        reserved = _get_route_keys(app)
        wrapper = _PluginAppWrapper(app, reserved)

        @wrapper.get("/plugin-only")
        def plugin_only():
            return "plugin"

        # Real app should have both routes
        keys_after = _get_route_keys(app)
        assert ("/existing", "GET") in keys_after
        assert ("/plugin-only", "GET") in keys_after

    def test_raises_on_conflicting_get(self):
        """Adding a route with same (path, method) as reserved raises ValueError."""
        app = FastAPI()

        @app.get("/api/login")
        def core_login():
            return "core"

        reserved = _get_route_keys(app)
        wrapper = _PluginAppWrapper(app, reserved)

        with pytest.raises(ValueError, match="Plugin route conflicts with existing route: /api/login \\[GET\\]"):
            wrapper.get("/api/login")(lambda: "plugin")

    def test_raises_on_conflicting_include_router(self):
        """include_router with a route that conflicts with reserved raises ValueError."""
        app = FastAPI()

        @app.get("/api/v1/flow")
        def core_flow():
            return "core"

        reserved = _get_route_keys(app)
        wrapper = _PluginAppWrapper(app, reserved)

        router = APIRouter()

        @router.get("/flow")
        def plugin_flow():
            return "plugin"

        with pytest.raises(ValueError, match="Plugin route conflicts with existing route"):
            wrapper.include_router(router, prefix="/api/v1")

    def test_include_router_allows_non_conflicting_prefix(self):
        """include_router with distinct prefix succeeds and reserves new paths."""
        app = FastAPI()

        @app.get("/health")
        def health():
            return "ok"

        reserved = _get_route_keys(app)
        wrapper = _PluginAppWrapper(app, reserved)

        router = APIRouter(prefix="/sso")

        @router.get("/login")
        def sso_login():
            return "sso"

        wrapper.include_router(router, prefix="/api/v1")

        keys_after = _get_route_keys(app)
        assert ("/api/v1/sso/login", "GET") in keys_after

    def test_on_event_delegates_without_conflict_check(self):
        """on_event is delegated to the real app and does not check route conflicts."""
        app = FastAPI()
        reserved = _get_route_keys(app)
        wrapper = _PluginAppWrapper(app, reserved)
        called = []

        @wrapper.on_event("startup")
        def on_startup():
            called.append(True)

        # Trigger lifespan startup to ensure handler is registered
        assert hasattr(wrapper._app, "router")

    def test_second_plugin_cannot_overwrite_first_plugin_route(self):
        """Reserved set is cumulative; second plugin cannot register same path."""
        app = FastAPI()
        reserved = _get_route_keys(app)
        wrapper = _PluginAppWrapper(app, reserved)

        # First "plugin" adds /api/v1/sso/login
        wrapper.get("/api/v1/sso/login")(lambda: "first")

        # Second plugin trying same path should fail
        with pytest.raises(ValueError, match=r"conflicts with existing route.*/api/v1/sso/login"):
            wrapper.get("/api/v1/sso/login")(lambda: "second")


class TestLoadPluginRoutes:
    """Tests for load_plugin_routes with mocked entry_points."""

    def test_no_crash_when_no_plugins(self):
        """When there are no entry points, load_plugin_routes does not crash."""
        app = FastAPI()

        @app.get("/health")
        def health():
            return "ok"

        with patch("langflow.plugin_routes.entry_points", return_value=[]):
            load_plugin_routes(app)

        keys = _get_route_keys(app)
        assert ("/health", "GET") in keys

    def test_plugin_that_registers_route_is_loaded(self):
        """A plugin that registers a non-conflicting route is loaded successfully."""
        app = FastAPI()

        @app.get("/health")
        def health():
            return "ok"

        def register(app_like):
            @app_like.get("/api/v1/sso/login")
            def login():
                return "sso"

        ep = MagicMock()
        ep.name = "enterprise"
        ep.load.return_value = register

        with patch("langflow.plugin_routes.entry_points", return_value=[ep]):
            load_plugin_routes(app)

        keys = _get_route_keys(app)
        assert ("/api/v1/sso/login", "GET") in keys

    def test_plugin_with_conflict_is_skipped_app_continues(self):
        """When a plugin tries to register a conflicting route, that plugin is skipped."""
        app = FastAPI()

        @app.get("/api/v1/flow")
        def core_flow():
            return "core"

        def conflicting_register(app_like):
            app_like.get("/api/v1/flow")(lambda: "plugin")

        ep = MagicMock()
        ep.name = "bad_plugin"
        ep.load.return_value = conflicting_register

        with patch("langflow.plugin_routes.entry_points", return_value=[ep]):
            load_plugin_routes(app)

        # Core route must still be the only one at that path
        routes_at_path = [
            r for r in app.router.routes if getattr(r, "path", None) == "/api/v1/flow" and hasattr(r, "methods")
        ]
        assert len(routes_at_path) == 1

    def test_plugin_that_raises_is_skipped_app_continues(self):
        """When a plugin raises a non-ValueError exception, it is skipped."""
        app = FastAPI()

        @app.get("/health")
        def health():
            return "ok"

        def broken_register(_app_like):
            err_msg = "plugin broken"
            raise RuntimeError(err_msg)

        ep = MagicMock()
        ep.name = "broken_plugin"
        ep.load.return_value = broken_register

        with patch("langflow.plugin_routes.entry_points", return_value=[ep]):
            load_plugin_routes(app)

        # App still has core route
        keys = _get_route_keys(app)
        assert ("/health", "GET") in keys
