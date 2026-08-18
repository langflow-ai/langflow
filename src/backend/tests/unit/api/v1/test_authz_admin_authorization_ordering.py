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

# (router module, path, a body that fails schema validation)
MALFORMED_BODY_ROUTES = [
    (authz_roles, "/authz/roles", {"bogus": 1}),
    (authz_teams, "/authz/teams", {"bogus": 1}),
    (authz_role_assignments, "/authz/role-assignments", {"bogus": 1}),
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


@pytest.mark.parametrize(("module", "path", "body"), MALFORMED_BODY_ROUTES)
def test_malformed_body_from_non_superuser_is_403_not_422(module, path, body):
    """The denial comes first, so the schema is never described to the caller."""
    with _client(module, is_superuser=False) as client:
        response = client.post(path, json=body)

    assert response.status_code == 403, response.text
    # No field names, no accepted literals.
    assert "detail" in response.json()
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize(("module", "path", "body"), MALFORMED_BODY_ROUTES)
def test_malformed_body_from_superuser_still_reports_schema_errors(module, path, body):
    """The gate moved earlier; it did not swallow validation for callers who pass it."""
    with _client(module, is_superuser=True) as client:
        response = client.post(path, json=body)

    assert response.status_code == 422, response.text
