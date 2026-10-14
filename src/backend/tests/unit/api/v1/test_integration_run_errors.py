"""Regression coverage across the simple-run wrapper and HTTP boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from langflow.api.v1 import endpoints
from langflow.api.v1.schemas import SimplifiedAPIRequest
from lfx.integrations.errors import ActionUnsupportedError, ConnectionNotAuthorizedError
from lfx.services.integration_policy import IntegrationPolicyError, IntegrationPolicyPurpose

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("owner", [False, True])
@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (
            IntegrationPolicyError(
                "qaprobe", IntegrationPolicyPurpose.USE, policy_key="integrations.qaprobe.doc.search"
            ),
            403,
        ),
        (ConnectionNotAuthorizedError(provider="qaprobe"), 403),
        (ActionUnsupportedError(provider="qaprobe", http_status=422), 422),
    ],
)
async def test_simple_run_keeps_typed_errors_through_the_http_boundary(monkeypatch, owner, error, status_code):
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    flow = SimpleNamespace(
        id=uuid4(),
        user_id=user.id if owner else uuid4(),
        name="probe",
        workspace_id=None,
        folder_id=None,
        data={"nodes": [], "edges": []},
    )
    graph = SimpleNamespace(vertices=[], set_run_id=Mock())
    wrapped = ValueError("Error running graph")
    wrapped.__cause__ = error
    monkeypatch.setattr(endpoints, "prepare_flow_build_for_user", AsyncMock(return_value=None))
    monkeypatch.setattr(endpoints, "try_warm_run_graph", AsyncMock(return_value=graph))
    monkeypatch.setattr(
        endpoints,
        "get_job_service",
        lambda: SimpleNamespace(create_job=AsyncMock(), execute_with_status=AsyncMock(side_effect=wrapped)),
    )
    monkeypatch.setattr(endpoints, "get_telemetry_service", lambda: SimpleNamespace(log_package_run=AsyncMock()))
    app = FastAPI()

    @app.post("/run")
    async def run():
        return await endpoints._run_flow_internal(
            background_tasks=BackgroundTasks(),
            flow=flow,
            input_request=SimplifiedAPIRequest(),
            stream=False,
            api_key_user=user,
            context=None,
            http_request=Request({"type": "http", "headers": []}),
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/run")

    assert response.status_code == status_code, response.text
    assert response.json()["detail"]["error_code"] == error.code
    if not owner:
        assert "integrations.qaprobe.doc.search" not in response.text
    assert "Traceback" not in response.text
