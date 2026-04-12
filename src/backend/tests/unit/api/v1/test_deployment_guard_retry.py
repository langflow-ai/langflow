from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.exceptions import parse_deployment_guard_error


class _AsyncNoopSavepoint:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_on_deployment_guard_succeeds_after_sync(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    db = MagicMock()
    db.begin_nested.return_value = _AsyncNoopSavepoint()
    flow_id = uuid4()
    operation = AsyncMock(
        side_effect=[
            RuntimeError("DEPLOYMENT_GUARD:FLOW_FOLDER_MOVE:Flow is deployed."),
            "ok",
        ]
    )

    result = await retry_flow_operation_on_deployment_guard(
        db=db,
        user_id=uuid4(),
        flow_ids=[flow_id],
        operation=operation,
    )

    assert result == "ok"
    assert operation.await_count == 2
    assert db.begin_nested.call_count == 2
    mock_sync_flow_deployment_state.assert_awaited_once()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_on_deployment_guard_propagates_second_guard(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    db = MagicMock()
    db.begin_nested.return_value = _AsyncNoopSavepoint()
    operation = AsyncMock(
        side_effect=[
            RuntimeError("DEPLOYMENT_GUARD:FLOW_FOLDER_MOVE:First guard."),
            RuntimeError("DEPLOYMENT_GUARD:FLOW_FOLDER_MOVE:Second guard."),
        ]
    )

    with pytest.raises(RuntimeError) as exc_info:
        await retry_flow_operation_on_deployment_guard(
            db=db,
            user_id=uuid4(),
            flow_ids=[uuid4()],
            operation=operation,
        )

    assert parse_deployment_guard_error(exc_info.value) is not None
    assert operation.await_count == 2
    mock_sync_flow_deployment_state.assert_awaited_once()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_project_deployments", new_callable=AsyncMock)
async def test_projects_retry_on_deployment_guard_uses_project_sync(mock_sync_project_deployments):
    from langflow.api.v1.mappers.deployments.sync import retry_project_operation_on_deployment_guard

    db = MagicMock()
    db.begin_nested.return_value = _AsyncNoopSavepoint()
    project_id = uuid4()
    operation = AsyncMock(
        side_effect=[
            RuntimeError("DEPLOYMENT_GUARD:PROJECT_DELETE:Project has deployments."),
            None,
        ]
    )

    await retry_project_operation_on_deployment_guard(
        db=db,
        user_id=uuid4(),
        project_id=project_id,
        operation=operation,
    )

    assert operation.await_count == 2
    mock_sync_project_deployments.assert_awaited_once()
