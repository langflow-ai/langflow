"""Compatibility shim for OpenTelemetry FastAPI instrumentation under FastAPI >=0.137.

FastAPI 0.137 changed ``include_router`` to *lazy* inclusion: instead of eagerly
flattening a sub-router's routes onto the parent, the top-level ``app.routes`` now
contains ``_IncludedRouter`` wrappers. Those wrappers are matchable ``BaseRoute``
objects but intentionally carry no ``.path`` attribute.

``opentelemetry-instrumentation-fastapi`` names every request span by walking
``app.routes`` and reading ``route.path`` (see ``_get_route_details``). Its
``Match.FULL`` branch already guards the missing-``path`` case, but the
``Match.PARTIAL`` branch does not -- so a request that only partially matches a
lazily-included route (for example an OPTIONS/CORS preflight against a GET-only
route) raises ``AttributeError`` mid-request and turns into a 500.

We replace the module-level ``_get_route_details`` helper with a guarded copy.
``_get_default_span_details`` resolves it as a module global on every call, so the
reassignment takes effect without re-instrumenting. The patch is idempotent and a
safe no-op on FastAPI <=0.136 or if the OTel internals ever change shape.
"""

from lfx.log.logger import logger
from starlette.routing import Match, Route

_PATCH_FLAG = "_langflow_route_details_patched"


def _safe_get_route_details(scope):
    """Drop-in replacement for OTel's ``_get_route_details`` that tolerates lazy includes.

    Mirrors the upstream loop but guards the ``Match.PARTIAL`` ``route.path`` access the
    same way upstream already guards the ``Match.FULL`` access. When the matched route is
    a FastAPI ``_IncludedRouter`` (no ``.path``), it falls back to the include-time prefix
    if available, otherwise to the raw request path.
    """
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
                route = scope.get("path")
            break
        if match == Match.PARTIAL:
            try:
                route = starlette_route.path
            except AttributeError:
                # FastAPI >=0.137 lazy include: the matched route is an
                # `_IncludedRouter` wrapper with no `.path`. Prefer the include
                # prefix (e.g. "/api/v1"); fall back to the request path.
                include_context = getattr(starlette_route, "include_context", None)
                route = getattr(include_context, "prefix", None) or scope.get("path")
    return route


def patch_otel_fastapi_route_details() -> None:
    """Install the guarded ``_get_route_details`` on the OTel FastAPI instrumentation.

    Idempotent. No-op when ``opentelemetry-instrumentation-fastapi`` is absent or when
    its internals no longer expose ``_get_route_details``.
    """
    try:
        from opentelemetry.instrumentation import fastapi as otel_fastapi
    except ImportError:
        return

    if getattr(otel_fastapi, _PATCH_FLAG, False):
        return
    if not hasattr(otel_fastapi, "_get_route_details"):
        # OTel internals changed; nothing to patch. Leave a breadcrumb so this is
        # noticed if FastAPI route spans start failing again.
        logger.debug("opentelemetry-instrumentation-fastapi has no _get_route_details; skipping compat patch")
        return

    otel_fastapi._get_route_details = _safe_get_route_details
    setattr(otel_fastapi, _PATCH_FLAG, True)
    logger.debug("Patched opentelemetry-instrumentation-fastapi._get_route_details for FastAPI >=0.137 lazy includes")
