"""Privileged /authz routes must refuse an unauthorised caller before reading their body.

Regression cover for LE-1905 finding 7: a caller with no role assignments used
to receive the same 422 field names and enum values a superuser would, and only
learned of the 403 once the payload was well-formed — enough to map the request
contract of a route they cannot invoke.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langflow.api.v1 import authz_role_assignments, authz_roles, authz_teams
from langflow.services.database.models.user.model import User

_UUID = "11111111-1111-1111-1111-111111111111"

# Every superuser-gated route that takes a body, with a payload that fails
# schema validation. Each must answer the denial before describing the schema.
# (router module, HTTP method, path, malformed body)
MALFORMED_BODY_ROUTES = [
    (authz_roles, "post", "/authz/roles", {"bogus": 1}),
    (authz_roles, "patch", f"/authz/roles/{_UUID}", {"permissions": "not-a-list"}),
    (authz_teams, "post", "/authz/teams", {"bogus": 1}),
    (authz_teams, "patch", f"/authz/teams/{_UUID}", {"is_active": "not-a-bool"}),
    (authz_teams, "post", f"/authz/teams/{_UUID}/members", {"bogus": 1}),
    (authz_role_assignments, "post", "/authz/role-assignments", {"bogus": 1}),
]


def _client(module, *, is_superuser: bool) -> TestClient:
    """Mount one authz router with the current user stubbed out."""
    from langflow.services.auth.utils import get_current_active_user

    app = FastAPI()
    app.include_router(module.router)

    def _user() -> User:
        return User(username="probe", password="x", is_superuser=is_superuser)  # noqa: S106

    app.dependency_overrides[get_current_active_user] = _user
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(("module", "method", "path", "body"), MALFORMED_BODY_ROUTES)
def test_malformed_body_from_non_superuser_is_403_not_422(module, method, path, body):
    """The denial comes first, so the schema is never described to the caller."""
    with _client(module, is_superuser=False) as client:
        response = getattr(client, method)(path, json=body)

    assert response.status_code == 403, response.text
    # No field names, no accepted literals.
    assert "detail" in response.json()
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize(("module", "method", "path", "body"), MALFORMED_BODY_ROUTES)
def test_malformed_body_from_superuser_still_reports_schema_errors(module, method, path, body):
    """The gate moved earlier; it did not swallow validation for callers who pass it."""
    with _client(module, is_superuser=True) as client:
        response = getattr(client, method)(path, json=body)

    assert response.status_code == 422, response.text


def test_every_superuser_gated_body_route_is_covered():
    """A new gated route with a body must be added to the matrix above.

    Without this the matrix silently stops tracking the surface it exists to
    protect: the property is "every privileged body route authorizes first",
    not "these six do".
    """
    covered = {(method.upper(), path) for _module, method, path, _body in MALFORMED_BODY_ROUTES}

    gated: set[tuple[str, str]] = set()
    for module in (authz_roles, authz_teams, authz_role_assignments):
        for route in module.router.routes:
            takes_body = any(
                dependant.body_params for dependant in [route.dependant] if hasattr(dependant, "body_params")
            )
            is_gated = any(
                dep.call is module._require_superuser_dependency
                for dep in route.dependant.dependencies
                if dep.call is not None
            )
            if takes_body and is_gated:
                for method in route.methods - {"HEAD", "OPTIONS"}:
                    # Routers are mounted with and without a trailing slash.
                    gated.add((method, route.path.rstrip("/") or route.path))

    normalized_covered = {(method, path.replace(_UUID, "{id}")) for method, path in covered}
    normalized_gated = {
        (method, path.replace("{role_id}", "{id}").replace("{team_id}", "{id}").replace("{user_id}", "{id}"))
        for method, path in gated
    }
    assert normalized_gated - normalized_covered == set(), (
        f"superuser-gated body routes missing from MALFORMED_BODY_ROUTES: {normalized_gated - normalized_covered}"
    )
