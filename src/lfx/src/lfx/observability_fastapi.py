"""Compatibility shim for OpenTelemetry FastAPI instrumentation under FastAPI >=0.137.

FastAPI 0.137 changed ``include_router`` to *lazy* inclusion: instead of eagerly flattening a
sub-router's routes onto the parent, the top-level ``app.routes`` now contains
``_IncludedRouter`` wrappers. Those wrappers are matchable ``BaseRoute`` objects but
intentionally carry no ``.path`` attribute.

``opentelemetry-instrumentation-fastapi`` names every request span by walking ``app.routes``
and reading ``route.path``. Its ``Match.FULL`` branch already guards the missing-``path`` case,
but the ``Match.PARTIAL`` branch does not, so a request that only partially matches a lazily
included route (an OPTIONS/CORS preflight against a GET-only route) raises ``AttributeError``
mid-request and turns into a 500.

Recovering the template is not cosmetic: under the stable HTTP semantic conventions this value
becomes ``http.route``, which is a *metric label*, so returning the raw request path would put
every flow id, file id and session id into the metric store as its own series. Everything
mounts under ``/api``, so on FastAPI >=0.137 that is every API request, not an edge case.

Lives beside :mod:`lfx.observability` (which calls it from ``instrument_fastapi_app``) rather
than inside it, so the provider-bootstrap surface stays small.
"""

import weakref

from fastapi.routing import APIRoute
from starlette._utils import get_route_path
from starlette.routing import Match, Route

from lfx.log.logger import logger

_PATCH_FLAG = "_langflow_route_details_patched"
# Include nesting is two deep (/api -> /v1 -> router). The bound is only here so a cycle in
# FastAPI internals cannot hang a request.
_MAX_INCLUDE_DEPTH = 10
# The route index groups routes by their first literal path segments (/api/v2/flows).
_KEY_SEGMENTS = 3
# Request paths pick the group, so an id in the first segments could add a group per request.
_MAX_INDEX_KEYS = 1024

_route_indexes: "weakref.WeakKeyDictionary[object, _RouteIndex]" = weakref.WeakKeyDictionary()


class _RouteIndex:
    """The app's routes as one ordered list, grouped by leading literal path segments.

    Naming a span walks every route of every included router, and each FastAPI >=0.137
    ``effective_candidates()`` call first walks the router tree for its version. With
    Langflow's few hundred routes, that is repeated work on every request. The
    index is built once per routes version. A request then tests only the routes whose
    leading literal segments agree with its path, in the original route order.

    Entries are ``(literals, regex, methods, path, opaque)``. A route with a compiled
    ``path_regex`` is matched here the way FastAPI matches it; any other route is
    ``opaque`` and keeps its own ``matches``.
    """

    __slots__ = ("__weakref__", "by_key", "entries", "version")

    def __init__(self, app, version) -> None:
        self.version = version
        self.entries = []
        self.by_key = {}
        leaves = []
        _collect_leaves(app.routes, leaves, 0)
        for leaf in leaves:
            path = getattr(leaf, "path", None)
            if hasattr(leaf, "original_route"):
                # An included route: its context carries the prefixed regex and methods.
                indexable = isinstance(leaf.original_route, APIRoute)
            else:
                indexable = isinstance(leaf, Route)
            regex = getattr(leaf, "path_regex", None)
            if indexable and regex is not None and isinstance(path, str):
                self.entries.append((_literal_prefix(path), regex, getattr(leaf, "methods", None), path, None))
            else:
                self.entries.append(((), None, None, path, leaf))

    def candidates(self, route_path):
        key = tuple(route_path.split("/", _KEY_SEGMENTS + 1)[1 : _KEY_SEGMENTS + 1])
        found = self.by_key.get(key)
        if found is None:
            found = [entry for entry in self.entries if _prefix_agrees(entry[0], key)]
            if len(self.by_key) < _MAX_INDEX_KEYS:
                self.by_key[key] = found
        return found


def _collect_leaves(routes, out, depth) -> None:
    """Flatten lazily-included routers into their leaf routes, in FastAPI's match order."""
    if depth > _MAX_INCLUDE_DEPTH:
        msg = "route include nesting is too deep"
        raise ValueError(msg)
    for route in routes:
        effective_candidates = getattr(route, "effective_candidates", None)
        if effective_candidates is not None:
            _collect_leaves(effective_candidates(), out, depth + 1)
        else:
            out.append(route)


def _literal_prefix(path):
    """The leading literal segments of a route template, up to the first parameter."""
    literals = []
    for segment in path.split("/", _KEY_SEGMENTS + 1)[1 : _KEY_SEGMENTS + 1]:
        if "{" in segment:
            break
        literals.append(segment)
    return tuple(literals)


def _prefix_agrees(literals, key):
    # Conservative: the regex decides, so a route stays a candidate unless a literal differs.
    return all(a == b for a, b in zip(literals, key, strict=False))


def _routes_version(app):
    get_version = getattr(app.router, "_get_routes_version", None)
    return get_version() if get_version is not None else len(app.routes)


def _indexed_route_details(scope):
    """The templated path from the route index, or None when the slow scan must decide."""
    app = scope["app"]
    version = _routes_version(app)
    index = _route_indexes.get(app)
    if index is None or index.version != version:
        index = _RouteIndex(app, version)
        _route_indexes[app] = index
    route_path = get_route_path(scope)
    method = scope.get("method")
    partial = None
    for _literals, regex, methods, path, opaque in index.candidates(route_path):
        if opaque is None:
            if not regex.match(route_path):
                continue
            match = Match.PARTIAL if methods and method not in methods else Match.FULL
        else:
            try:
                match, _ = opaque.matches(scope)
            except Exception:  # noqa: BLE001, S112 - one odd route must not fail the request
                continue
            if match == Match.NONE or path is None:
                continue
        if match == Match.FULL:
            return path
        partial = partial or path
    return partial


def _resolve_included_route(included_router, scope, depth=0):
    """Find the templated path of the route inside a lazily-included router.

    ``_IncludedRouter.effective_candidates()`` returns the router's children with their
    prefixes already applied: leaves carry ``.path`` (``/api/v1/flows/{flow_id}``) and nested
    includes are more ``_IncludedRouter`` wrappers, so this recurses. Returns None when
    nothing matches, which leaves the caller on its existing fallback.
    """
    if depth > _MAX_INCLUDE_DEPTH:
        return None
    try:
        candidates = included_router.effective_candidates()
    except Exception:  # noqa: BLE001 - private FastAPI internals; never fail a request over a span name
        return None

    partial = None
    for candidate in candidates:
        try:
            match, _ = candidate.matches(scope)
        except Exception:  # noqa: BLE001, S112 - one odd candidate must not fail the request
            continue
        if match == Match.NONE:
            continue
        path = getattr(candidate, "path", None)
        if path is None:
            path = _resolve_included_route(candidate, scope, depth + 1)
        if path is None:
            continue
        if match == Match.FULL:
            return path
        # A method mismatch (CORS preflight, 405) still identifies the endpoint. Keep it,
        # but let a later full match win.
        partial = partial or path
    return partial


def _safe_get_route_details(scope):
    """Drop-in replacement for OTel's ``_get_route_details`` that tolerates lazy includes.

    Mirrors the upstream loop but guards the ``Match.PARTIAL`` ``route.path`` access the same
    way upstream already guards the ``Match.FULL`` access. When the matched route is a FastAPI
    ``_IncludedRouter`` (no ``.path``), it descends into the router to recover the templated
    path. The raw request path remains the last resort, since a wrong-but-bounded span name
    beats failing the request.

    HTTP requests first use the route index (see ``_RouteIndex``). The full scan below
    decides only when the index finds no route or cannot be built.
    """
    if scope.get("type") == "http":
        try:
            route = _indexed_route_details(scope)
        except Exception:  # noqa: BLE001 - private FastAPI internals; never fail a request over a span name
            route = None
        if route is not None:
            return route

    app = scope["app"]
    route = None

    for starlette_route in app.routes:
        match, _ = (
            Route.matches(starlette_route, scope)
            if isinstance(starlette_route, Route)
            else starlette_route.matches(scope)
        )
        if match == Match.FULL:
            try:
                route = starlette_route.path
            except AttributeError:
                route = _resolve_included_route(starlette_route, scope) or scope.get("path")
            break
        if match == Match.PARTIAL:
            try:
                route = starlette_route.path
            except AttributeError:
                # FastAPI >=0.137 lazy include: the matched route is an
                # `_IncludedRouter` wrapper with no `.path`.
                include_context = getattr(starlette_route, "include_context", None)
                route = (
                    _resolve_included_route(starlette_route, scope)
                    or getattr(include_context, "prefix", None)
                    or scope.get("path")
                )
    return route


def patch_otel_fastapi_route_details() -> None:
    """Install the guarded ``_get_route_details`` on the OTel FastAPI instrumentation.

    Idempotent. No-op when ``opentelemetry-instrumentation-fastapi`` is absent or when its
    internals no longer expose ``_get_route_details``.
    """
    try:
        from opentelemetry.instrumentation import fastapi as otel_fastapi
    except ImportError:
        return

    if getattr(otel_fastapi, _PATCH_FLAG, False):
        return
    if not hasattr(otel_fastapi, "_get_route_details"):
        # OTel internals changed; nothing to patch. Leave a breadcrumb so this is noticed if
        # FastAPI route spans start failing again.
        logger.debug("opentelemetry-instrumentation-fastapi has no _get_route_details; skipping compat patch")
        return

    otel_fastapi._get_route_details = _safe_get_route_details  # noqa: SLF001
    setattr(otel_fastapi, _PATCH_FLAG, True)
    logger.debug("Patched opentelemetry-instrumentation-fastapi._get_route_details for FastAPI >=0.137 lazy includes")
