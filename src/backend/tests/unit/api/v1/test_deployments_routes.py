"""Route matching tests for deployment endpoints.

These tests guard against route-order regressions where static routes could be
captured by the dynamic `/{deployment_id}` route.
"""

from uuid import uuid4

import langflow.api.router as api_router_module
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from langflow.api.v1.deployments import router
from starlette.routing import Match


@pytest.fixture
def deployment_routes() -> list[APIRoute]:
    app = FastAPI()
    app.include_router(router)
    return [route for route in app.router.routes if isinstance(route, APIRoute)]


def _resolve_endpoint_name(routes: list[APIRoute], *, path: str, method: str = "GET") -> str:
    scope = {"type": "http", "path": path, "method": method}
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route.endpoint.__name__
    msg = f"No matching route for {method} {path}"
    raise AssertionError(msg)


def test_configs_path_matches_configs_endpoint(deployment_routes: list[APIRoute]) -> None:
    assert _resolve_endpoint_name(deployment_routes, path="/deployments/configs") == "list_deployment_configs"


def test_types_path_matches_types_endpoint(deployment_routes: list[APIRoute]) -> None:
    assert _resolve_endpoint_name(deployment_routes, path="/deployments/types") == "list_deployment_types"


def test_deployment_status_path_matches_status_endpoint(deployment_routes: list[APIRoute]) -> None:
    deployment_id = uuid4()
    assert (
        _resolve_endpoint_name(
            deployment_routes,
            path=f"/deployments/{deployment_id}/status",
        )
        == "get_deployment_status"
    )


def test_include_deployment_router_skips_routes_when_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_router_module.FEATURE_FLAGS, "wxo_deployments", False)

    router_v1 = APIRouter(prefix="/v1")
    api_router_module.include_deployment_router(router_v1)

    assert all("/deployments" not in route.path for route in router_v1.routes)


def test_include_deployment_router_adds_routes_when_feature_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_router_module.FEATURE_FLAGS, "wxo_deployments", True)

    router_v1 = APIRouter(prefix="/v1")
    api_router_module.include_deployment_router(router_v1)

    assert any("/deployments" in route.path for route in router_v1.routes)
