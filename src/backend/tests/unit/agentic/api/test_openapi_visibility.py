"""Bug 5 [P2] — agentic routers must be visible in /openapi.json.

PR-12575 hides most agentic endpoints from the OpenAPI schema by
setting ``include_in_schema=False`` on the API routers (router.py:39 and
files_router.py:49). External clients, SDK generators, and Swagger UI
therefore can't discover them.

Bug-fix scope: the assistant and files endpoints are GA-quality surfaces
(authenticated, documented in ``docs/features/langflow-assistant.md``,
covered by extensive tests). They must appear in the published schema so
clients can integrate without reading source code.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langflow.agentic.api.files_router import router as files_router
from langflow.agentic.api.router import router as assistant_router


def _build_schema() -> dict:
    """Mount the two agentic routers on a clean FastAPI app and return its OpenAPI schema."""
    app = FastAPI()
    app.include_router(assistant_router)
    app.include_router(files_router)
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


class TestAgenticRoutersAppearInOpenApi:
    """Bug 5 — every GA agentic endpoint must be discoverable via the OpenAPI schema."""

    def test_should_expose_assist_endpoint(self):
        """RED before fix: ``/agentic/assist`` is missing from the schema."""
        paths = _build_schema().get("paths", {})
        assert "/agentic/assist" in paths, f"Expected /agentic/assist to be in schema, got paths: {sorted(paths)}"

    def test_should_expose_assist_stream_endpoint(self):
        """RED before fix: ``/agentic/assist/stream`` is missing from the schema."""
        paths = _build_schema().get("paths", {})
        assert "/agentic/assist/stream" in paths, (
            f"Expected /agentic/assist/stream to be in schema, got paths: {sorted(paths)}"
        )

    def test_should_expose_check_config_endpoint(self):
        """RED before fix: ``/agentic/check-config`` is missing from the schema."""
        paths = _build_schema().get("paths", {})
        assert "/agentic/check-config" in paths, (
            f"Expected /agentic/check-config to be in schema, got paths: {sorted(paths)}"
        )

    def test_should_expose_files_endpoint(self):
        """RED before fix: ``/agentic/files`` is missing from the schema."""
        paths = _build_schema().get("paths", {})
        assert "/agentic/files" in paths, f"Expected /agentic/files to be in schema, got paths: {sorted(paths)}"

    def test_should_expose_execute_endpoint(self):
        """RED before fix: ``/agentic/execute/{flow_name}`` is missing from the schema."""
        paths = _build_schema().get("paths", {})
        assert "/agentic/execute/{flow_name}" in paths, (
            f"Expected /agentic/execute/{{flow_name}} to be in schema, got paths: {sorted(paths)}"
        )
