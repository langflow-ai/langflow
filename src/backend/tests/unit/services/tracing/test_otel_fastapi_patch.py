"""Regression tests for the OpenTelemetry FastAPI route-detail compatibility patch.

FastAPI 0.137 made ``include_router`` lazy, so ``app.routes`` now holds
``_IncludedRouter`` wrappers with no ``.path``. ``opentelemetry-instrumentation-fastapi``
reads ``route.path`` to name spans and crashed on a *partial* route match (e.g. a CORS
preflight / OPTIONS against a GET-only route). These tests pin the fix and are written to
pass on both eager (<=0.136) and lazy (>=0.137) inclusion.
"""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from lfx.observability_fastapi import (
    _safe_get_route_details,
    patch_otel_fastapi_route_details,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


def _build_app() -> FastAPI:
    sub = APIRouter()

    @sub.get("/version")
    def _version():
        return {"version": "test"}

    app = FastAPI()
    app.include_router(sub, prefix="/api/v1")
    return app


def test_patch_is_idempotent():
    """Applying the patch twice leaves a single guarded helper installed."""
    import opentelemetry.instrumentation.fastapi as otel_fastapi

    patch_otel_fastapi_route_details()
    first = otel_fastapi._get_route_details
    patch_otel_fastapi_route_details()
    second = otel_fastapi._get_route_details

    assert first is second
    assert first is _safe_get_route_details
    assert getattr(otel_fastapi, "_langflow_route_details_patched", False) is True


def test_safe_route_details_partial_match_does_not_raise():
    """A partial (method-mismatch) match against a lazily-included route returns a label.

    Pre-patch this raised ``AttributeError: '_IncludedRouter' object has no attribute 'path'``.
    """
    app = _build_app()
    # OPTIONS is not an accepted method for the GET route -> partial match on the path.
    scope = {
        "type": "http",
        "method": "OPTIONS",
        "path": "/api/v1/version",
        "headers": [],
        "app": app,
    }

    route = _safe_get_route_details(scope)

    # Either the include prefix (lazy >=0.137) or the full templated path (eager <=0.136);
    # the contract is "a non-crashing, request-relevant string".
    assert route in {"/api/v1", "/api/v1/version"}


def test_safe_route_details_full_match_returns_path():
    """A full match still yields a usable route label."""
    app = _build_app()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/version",
        "headers": [],
        "app": app,
    }

    route = _safe_get_route_details(scope)

    assert route == "/api/v1/version"


def test_instrumented_options_preflight_does_not_500():
    """End-to-end: an OPTIONS preflight through the instrumented app no longer crashes.

    This reproduces the production failure path (OTel ASGI middleware -> span route
    extraction) that turned a 405/preflight into a 500 under FastAPI >=0.137.
    """
    patch_otel_fastapi_route_details()
    app = _build_app()
    FastAPIInstrumentor.instrument_app(app)

    try:
        client = TestClient(app)
        response = client.options(
            "/api/v1/version",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # No CORS middleware here, so an OPTIONS to a GET-only route is a clean 405 -
        # the point is the request flowed through OTel instrumentation without erroring.
        assert response.status_code != 500
        assert response.status_code == 405

        # And a normal request still works end-to-end.
        ok = client.get("/api/v1/version")
        assert ok.status_code == 200
        assert ok.json() == {"version": "test"}
    finally:
        FastAPIInstrumentor.uninstrument_app(app)


@pytest.mark.parametrize("method", ["OPTIONS", "DELETE", "PUT"])
def test_instrumented_method_mismatch_does_not_500(method):
    """Any method-mismatch (partial match) on a lazily-included route stays a 405, not a 500."""
    patch_otel_fastapi_route_details()
    app = _build_app()
    FastAPIInstrumentor.instrument_app(app)

    try:
        client = TestClient(app)
        response = client.request(method, "/api/v1/version")
        assert response.status_code == 405
    finally:
        FastAPIInstrumentor.uninstrument_app(app)


def _build_app_with_path_params() -> FastAPI:
    """Mirror Langflow's shape: a router with path params, lazily included under /api/v1."""
    router = APIRouter(prefix="/v1")

    @router.get("/flows/{flow_id}")
    def read_flow(flow_id: str):
        return {"id": flow_id}

    api = APIRouter(prefix="/api")
    api.include_router(router)
    app = FastAPI()
    app.include_router(api)
    return app


FLOW_ID = "357ea329-0775-4204-8161-d182c8c4edf5"


def test_route_label_is_templated_not_the_raw_path():
    """The identifier must not survive into the route label.

    Under the stable HTTP semantic conventions this value becomes ``http.route``, which is a
    metric label. Returning the raw path would mint one metric series per flow id. Langflow
    mounts every API route under a lazily-included router, so this is the common path.
    """
    app = _build_app_with_path_params()
    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/api/v1/flows/{FLOW_ID}",
        "headers": [],
        "app": app,
    }

    route = _safe_get_route_details(scope)

    assert route == "/api/v1/flows/{flow_id}"
    assert FLOW_ID not in route


def test_route_label_cardinality_is_bounded_by_endpoint_count():
    """Many distinct ids must collapse onto one label, which is the whole point."""
    app = _build_app_with_path_params()
    labels = set()
    for i in range(50):
        scope = {
            "type": "http",
            "method": "GET",
            "path": f"/api/v1/flows/00000000-0000-0000-0000-{i:012d}",
            "headers": [],
            "app": app,
        }
        labels.add(_safe_get_route_details(scope))

    assert labels == {"/api/v1/flows/{flow_id}"}


def test_preflight_on_a_parameterised_route_is_also_templated():
    """A method mismatch still resolves the endpoint rather than falling back to the path."""
    app = _build_app_with_path_params()
    scope = {
        "type": "http",
        "method": "OPTIONS",
        "path": f"/api/v1/flows/{FLOW_ID}",
        "headers": [],
        "app": app,
    }

    route = _safe_get_route_details(scope)

    assert FLOW_ID not in (route or "")
    assert route in {"/api/v1/flows/{flow_id}", "/api/v1"}
