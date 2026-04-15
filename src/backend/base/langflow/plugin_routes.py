"""Plugin route discovery and registration with conflict protection.

Plugins register via the ``langflow.plugins`` entry-point group. They receive
a wrapper so they cannot overwrite or shadow existing Langflow routes.
"""

from importlib.metadata import entry_points

from fastapi import FastAPI
from lfx.log.logger import logger


def _get_route_keys(app: FastAPI) -> set[tuple[str, str]]:
    """Collect (path, method) for all routes already on the app.

    Used to build the reserved set before loading plugins so that plugin
    routes cannot overwrite or shadow existing Langflow routes.
    """
    keys: set[tuple[str, str]] = set()
    for route in app.router.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            for method in route.methods:
                if method != "HEAD":  # often same as GET
                    keys.add((route.path, method))
        elif hasattr(route, "path") and hasattr(route, "path_regex"):
            # Mount or similar: reserve path for all methods
            keys.add((route.path, "*"))
    return keys


class _PluginAppWrapper:
    """Wrapper around the real FastAPI app that only allows adding routes.

    - Rejects adding a route if (path, method) is already reserved (no shadowing).
    - Does not expose router/routes so plugins cannot remove or reorder routes.
    """

    def __init__(self, app: FastAPI, reserved: set[tuple[str, str]]) -> None:
        self._app = app
        self._reserved = set(reserved)

    def _check_and_reserve(self, path: str, methods: set[str]) -> None:
        for method in methods:
            if method == "HEAD":
                continue
            key = (path, method)
            if key in self._reserved:
                msg = f"Plugin route conflicts with existing route: {path} [{method}]"
                raise ValueError(msg)
            self._reserved.add(key)

    def include_router(self, router, prefix: str = "", **kwargs) -> None:
        # Effective prefix: include_router(prefix=) + router's own prefix (e.g. APIRouter(prefix="/sso"))
        router_prefix = getattr(router, "prefix", "") or ""
        base = (prefix or "") + router_prefix

        for route in router.routes:
            if hasattr(route, "path") and hasattr(route, "methods"):
                full_path = base + route.path
                self._check_and_reserve(full_path, set(route.methods))
            elif hasattr(route, "path"):
                full_path = base + route.path
                self._check_and_reserve(full_path, {"*"})
        self._app.include_router(router, prefix=prefix, **kwargs)

    def get(self, path: str, **kwargs):
        self._check_and_reserve(path, {"GET"})
        return self._app.get(path, **kwargs)

    def post(self, path: str, **kwargs):
        self._check_and_reserve(path, {"POST"})
        return self._app.post(path, **kwargs)

    def put(self, path: str, **kwargs):
        self._check_and_reserve(path, {"PUT"})
        return self._app.put(path, **kwargs)

    def delete(self, path: str, **kwargs):
        self._check_and_reserve(path, {"DELETE"})
        return self._app.delete(path, **kwargs)

    def patch(self, path: str, **kwargs):
        self._check_and_reserve(path, {"PATCH"})
        return self._app.patch(path, **kwargs)

    def on_event(self, event_type: str):
        return self._app.on_event(event_type)

    # Expose other delegates plugins might need (no route mutation)
    @property
    def openapi(self):
        return self._app.openapi

    def add_api_route(self, path: str, endpoint, **kwargs):
        methods = kwargs.get("methods", ["GET"])
        self._check_and_reserve(path, set(methods))
        return self._app.add_api_route(path, endpoint, **kwargs)


def load_plugin_routes(app: FastAPI) -> None:
    """Discover and register additional routers from enterprise plugins.

    Plugins register themselves via the ``langflow.plugins`` entry-point group.
    Each entry point must expose a callable with the signature::

        def register(app: FastAPI) -> None: ...

    """
    reserved = _get_route_keys(app)
    wrapper = _PluginAppWrapper(app, reserved)

    eps = entry_points(group="langflow.plugins")
    for ep in sorted(eps, key=lambda e: e.name):
        try:
            plugin_register = ep.load()
        except Exception:  # noqa: BLE001
            logger.error(
                "Failed to load plugin entry point '%s' (broken import or missing dependency)",
                ep.name,
                exc_info=True,
            )
            continue

        try:
            plugin_register(wrapper)
            logger.info(f"Loaded plugin: {ep.name}")
        except ValueError as e:
            logger.warning(
                "Plugin '%s' rejected (route conflict): %s",
                ep.name,
                e,
                exc_info=True,
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "Plugin '%s' failed during registration",
                ep.name,
                exc_info=True,
            )
