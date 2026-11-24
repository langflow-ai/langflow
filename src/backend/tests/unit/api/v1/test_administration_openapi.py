"""The supported administration API must be discoverable by OpenAPI clients."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langflow.api.router import router


@pytest.fixture(scope="module")
def openapi_schema():
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    ("path", "method", "status_code", "response_model", "is_list"),
    [
        ("teams", "get", "200", "TeamRead", True),
        ("teams", "post", "201", "TeamRead", False),
        ("teams/{team_id}", "get", "200", "TeamRead", False),
        ("teams/{team_id}", "patch", "200", "TeamRead", False),
        ("teams/{team_id}", "delete", "204", None, False),
        ("teams/{team_id}/members", "get", "200", "TeamMemberRead", True),
        ("teams/{team_id}/members", "post", "201", "TeamMemberRead", False),
        ("teams/{team_id}/members/{user_id}", "delete", "204", None, False),
        ("roles", "get", "200", "RoleRead", True),
        ("roles", "post", "201", "RoleRead", False),
        ("roles/{role_id}", "get", "200", "RoleRead", False),
        ("roles/{role_id}", "patch", "200", "RoleRead", False),
        ("roles/{role_id}", "delete", "204", None, False),
        ("role-assignments", "get", "200", "RoleAssignmentRead", True),
        ("role-assignments", "post", "201", "RoleAssignmentRead", False),
        ("role-assignments/{assignment_id}", "delete", "204", None, False),
    ],
)
def test_administration_operations_document_responses(
    openapi_schema, path, method, status_code, response_model, is_list
):
    operation = openapi_schema["paths"][f"/api/v1/authz/{path}"][method]
    response = operation["responses"][status_code]
    assert operation["security"]
    if response_model is None:
        assert "content" not in response
        return
    schema = response["content"]["application/json"]["schema"]
    if is_list:
        assert schema["type"] == "array"
        schema = schema["items"]
    assert schema["$ref"] == f"#/components/schemas/{response_model}"
    assert response_model in openapi_schema["components"]["schemas"]


@pytest.mark.parametrize(
    ("path", "method", "request_model"),
    [
        ("teams", "post", "TeamCreate"),
        ("teams/{team_id}", "patch", "TeamUpdate"),
        ("teams/{team_id}/members", "post", "TeamMemberCreate"),
        ("roles", "post", "RoleCreate"),
        ("roles/{role_id}", "patch", "RoleUpdate"),
        ("role-assignments", "post", "RoleAssignmentCreate"),
    ],
)
def test_administration_operations_document_request_bodies(openapi_schema, path, method, request_model):
    body = openapi_schema["paths"][f"/api/v1/authz/{path}"][method]["requestBody"]
    assert body["required"] is True
    assert body["content"]["application/json"]["schema"]["$ref"] == f"#/components/schemas/{request_model}"
    assert request_model in openapi_schema["components"]["schemas"]


def test_administration_aliases_do_not_duplicate_operations(openapi_schema):
    operations = []
    for name in ("teams", "roles", "role-assignments"):
        prefix = f"/api/v1/authz/{name}"
        assert prefix in openapi_schema["paths"]
        assert f"{prefix}/" not in openapi_schema["paths"]
        for path, methods in openapi_schema["paths"].items():
            if path == prefix or path.startswith(f"{prefix}/"):
                operations.extend(operation["operationId"] for operation in methods.values())
    assert len(operations) == len(set(operations))
