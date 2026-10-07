"""Agentic routers must stay hidden from /openapi.json.

The assistant and files HTTP surfaces are internal. They are mounted with
``include_in_schema=False`` so they do not appear in the published OpenAPI
spec, Swagger UI, or generated SDKs.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langflow.agentic.api.files_router import router as files_router
from langflow.agentic.api.router import router as assistant_router

HIDDEN_AGENTIC_PATHS = (
    "/agentic/assist",
    "/agentic/assist/stream",
    "/agentic/check-config",
    "/agentic/files",
    "/agentic/execute/{flow_name}",
)


def _build_schema() -> dict:
    """Mount the two agentic routers on a clean FastAPI app and return its OpenAPI schema."""
    app = FastAPI()
    app.include_router(assistant_router)
    app.include_router(files_router)
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


class TestAgenticRoutersHiddenFromOpenApi:
    """Agentic endpoints are internal and must not appear in the OpenAPI schema."""

    def test_should_hide_assist_endpoint(self):
        paths = _build_schema().get("paths", {})
        assert "/agentic/assist" not in paths, f"Expected /agentic/assist to be hidden, got paths: {sorted(paths)}"

    def test_should_hide_assist_stream_endpoint(self):
        paths = _build_schema().get("paths", {})
        assert "/agentic/assist/stream" not in paths, (
            f"Expected /agentic/assist/stream to be hidden, got paths: {sorted(paths)}"
        )

    def test_should_hide_check_config_endpoint(self):
        paths = _build_schema().get("paths", {})
        assert "/agentic/check-config" not in paths, (
            f"Expected /agentic/check-config to be hidden, got paths: {sorted(paths)}"
        )

    def test_should_hide_files_endpoint(self):
        paths = _build_schema().get("paths", {})
        assert "/agentic/files" not in paths, f"Expected /agentic/files to be hidden, got paths: {sorted(paths)}"

    def test_should_hide_execute_endpoint(self):
        paths = _build_schema().get("paths", {})
        assert "/agentic/execute/{flow_name}" not in paths, (
            f"Expected /agentic/execute/{{flow_name}} to be hidden, got paths: {sorted(paths)}"
        )

    def test_schema_contains_no_agentic_paths(self):
        paths = _build_schema().get("paths", {})
        leaked = [path for path in HIDDEN_AGENTIC_PATHS if path in paths]
        assert leaked == [], f"Agentic endpoints leaked into OpenAPI: {leaked}"
        assert paths == {}, f"Agentic routers must be hidden from OpenAPI, got paths: {sorted(paths)}"
