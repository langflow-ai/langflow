"""Route matching tests for deployment endpoints.

These tests guard against route-order regressions where static routes could be
captured by the dynamic `/{deployment_id}` route.
"""

from collections.abc import Iterator
from uuid import uuid4

import langflow.api.router as api_router_module
import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from langflow.api.v1.deployments import router
from starlette.routing import Match


def _flatten_api_routes(router: APIRouter) -> Iterator[APIRoute]:
    """Yield every ``APIRoute`` reachable from ``router``.

    FastAPI >=0.137 includes sub-routers lazily: ``include_router`` stores an
    internal ``_IncludedRouter`` wrapper instead of eagerly copying the child
    ``APIRoute`` objects into ``router.routes``. Descend through that wrapper via
    its public ``original_router`` reference so these tests work on both the
    eager (<=0.136) and lazy (>=0.137) inclusion behaviours.
    """
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield route
        else:
            original = getattr(route, "original_router", None)
            if original is not None:
                yield from _flatten_api_routes(original)


@pytest.fixture
def deployment_routes() -> list[APIRoute]:
    return list(_flatten_api_routes(router))


def _resolve_endpoint_name(routes: list[APIRoute], *, path: str, method: str = "GET") -> str:
    scope = {"type": "http", "path": path, "method": method}
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route.endpoint.__name__
    msg = f"No matching route for {method} {path}"
    raise AssertionError(msg)


def _resolve_route(routes: list[APIRoute], *, path: str, method: str = "GET") -> APIRoute:
    scope = {"type": "http", "path": path, "method": method}
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
    msg = f"No matching route for {method} {path}"
    raise AssertionError(msg)


def test_configs_path_matches_configs_endpoint(deployment_routes: list[APIRoute]) -> None:
    assert _resolve_endpoint_name(deployment_routes, path="/deployments/configs") == "list_deployment_configs"


def test_types_path_matches_types_endpoint(deployment_routes: list[APIRoute]) -> None:
    assert _resolve_endpoint_name(deployment_routes, path="/deployments/types") == "list_deployment_types"


def test_llms_path_matches_llms_endpoint(deployment_routes: list[APIRoute]) -> None:
    assert _resolve_endpoint_name(deployment_routes, path="/deployments/llms") == "list_deployment_llms"


def test_snapshots_path_matches_snapshots_endpoint(deployment_routes: list[APIRoute]) -> None:
    assert _resolve_endpoint_name(deployment_routes, path="/deployments/snapshots") == "list_deployment_snapshots"


def test_configs_route_excludes_none_fields_in_response_model(deployment_routes: list[APIRoute]) -> None:
    route = _resolve_route(deployment_routes, path="/deployments/configs")
    assert route.response_model_exclude_none is True


def test_snapshots_route_excludes_none_fields_in_response_model(deployment_routes: list[APIRoute]) -> None:
    route = _resolve_route(deployment_routes, path="/deployments/snapshots")
    assert route.response_model_exclude_none is True


def test_snapshot_patch_path_matches_update_endpoint(deployment_routes: list[APIRoute]) -> None:
    assert (
        _resolve_endpoint_name(
            deployment_routes,
            path="/deployments/snapshots/tool-123",
            method="PATCH",
        )
        == "update_snapshot"
    )


def test_deployment_status_path_is_not_registered(deployment_routes: list[APIRoute]) -> None:
    deployment_id = uuid4()
    with pytest.raises(AssertionError, match="No matching route"):
        _resolve_endpoint_name(
            deployment_routes,
            path=f"/deployments/{deployment_id}/status",
        )


def test_deployment_flows_path_matches_flow_versions_endpoint(deployment_routes: list[APIRoute]) -> None:
    deployment_id = uuid4()
    assert (
        _resolve_endpoint_name(
            deployment_routes,
            path=f"/deployments/{deployment_id}/flows",
        )
        == "list_deployment_flow_versions"
    )


def test_include_deployment_router_skips_routes_when_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_router_module.FEATURE_FLAGS, "wxo_deployments", False)

    router_v1 = APIRouter(prefix="/v1")
    api_router_module.include_deployment_router(router_v1)

    assert all("/deployments" not in route.path for route in _flatten_api_routes(router_v1))


def test_include_deployment_router_adds_routes_when_feature_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_router_module.FEATURE_FLAGS, "wxo_deployments", True)

    router_v1 = APIRouter(prefix="/v1")
    api_router_module.include_deployment_router(router_v1)

    assert any("/deployments" in route.path for route in _flatten_api_routes(router_v1))
