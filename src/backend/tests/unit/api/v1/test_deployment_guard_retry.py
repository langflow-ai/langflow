from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.deployment.exceptions import (
    DeploymentGuardError,
)


class _AsyncNoopSavepoint:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _OwnerResult:
    def __init__(self, rows: list[tuple[UUID, UUID]]):
        self._rows = rows

    def all(self):
        return self._rows


def _db_with_flow_owners(owner_rows: list[tuple[UUID, UUID]] | None = None) -> MagicMock:
    db = MagicMock()
    db.begin_nested.return_value = _AsyncNoopSavepoint()
    db.exec = AsyncMock(return_value=_OwnerResult(owner_rows or []))
    return db


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_syncs_in_flow_owner_namespace_not_actor(mock_sync_flow_deployment_state):
    """Shared actors must sync against the flow owner's deployment namespace."""
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    owner_id = uuid4()
    flow_id = uuid4()
    db = _db_with_flow_owners([(flow_id, owner_id)])
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="FLOW_HAS_DEPLOYED_VERSIONS",
                technical_detail="Flow is deployed.",
                detail="Flow is deployed.",
            ),
            "ok",
        ]
    )

    result = await retry_flow_operation_on_deployment_guard(
        db=db,
        flow_ids=[flow_id],
        operation=operation,
    )

    assert result == "ok"
    mock_sync_flow_deployment_state.assert_awaited_once_with(
        db=db,
        flow_ids=[flow_id],
        user_id=owner_id,
    )


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_on_deployment_guard_succeeds_after_sync(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    flow_id = uuid4()
    owner_id = uuid4()
    db = _db_with_flow_owners([(flow_id, owner_id)])
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="FLOW_FOLDER_MOVE",
                technical_detail="Flow is deployed.",
                detail="Flow is deployed.",
            ),
            "ok",
        ]
    )

    result = await retry_flow_operation_on_deployment_guard(
        db=db,
        flow_ids=[flow_id],
        operation=operation,
    )

    assert result == "ok"
    assert operation.await_count == 2
    assert db.begin_nested.call_count == 2
    mock_sync_flow_deployment_state.assert_awaited_once_with(
        db=db,
        flow_ids=[flow_id],
        user_id=owner_id,
    )


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_on_deployment_guard_error_instance_succeeds_after_sync(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    flow_id = uuid4()
    owner_id = uuid4()
    db = _db_with_flow_owners([(flow_id, owner_id)])
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="FLOW_FOLDER_MOVE",
                technical_detail="Flow is deployed.",
                detail="Flow is deployed.",
            ),
            "ok",
        ]
    )

    result = await retry_flow_operation_on_deployment_guard(
        db=db,
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

    flow_id = uuid4()
    db = _db_with_flow_owners([(flow_id, uuid4())])
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="FLOW_FOLDER_MOVE",
                technical_detail="First guard.",
                detail="First guard.",
            ),
            DeploymentGuardError(
                code="FLOW_FOLDER_MOVE",
                technical_detail="Second guard.",
                detail="Second guard.",
            ),
        ]
    )

    with pytest.raises(DeploymentGuardError) as exc_info:
        await retry_flow_operation_on_deployment_guard(
            db=db,
            flow_ids=[flow_id],
            operation=operation,
        )

    assert exc_info.value.technical_detail == "Second guard."
    assert operation.await_count == 2
    mock_sync_flow_deployment_state.assert_awaited_once()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_success_on_first_attempt_skips_sync(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    db = _db_with_flow_owners()
    operation = AsyncMock(return_value="ok")

    result = await retry_flow_operation_on_deployment_guard(
        db=db,
        flow_ids=[uuid4()],
        operation=operation,
    )

    assert result == "ok"
    assert operation.await_count == 1
    assert db.begin_nested.call_count == 1
    mock_sync_flow_deployment_state.assert_not_awaited()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_non_guard_error_propagates_without_sync(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    db = _db_with_flow_owners()
    operation = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await retry_flow_operation_on_deployment_guard(
            db=db,
            flow_ids=[uuid4()],
            operation=operation,
        )

    assert operation.await_count == 1
    assert db.begin_nested.call_count == 1
    mock_sync_flow_deployment_state.assert_not_awaited()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_guard_with_none_flow_ids_skips_sync(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    db = _db_with_flow_owners()
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="FLOW_FOLDER_MOVE",
                technical_detail="Flow is deployed.",
                detail="Flow is deployed.",
            ),
            "ok",
        ]
    )

    result = await retry_flow_operation_on_deployment_guard(
        db=db,
        flow_ids=None,
        operation=operation,
    )

    assert result == "ok"
    assert operation.await_count == 2
    mock_sync_flow_deployment_state.assert_not_awaited()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_guard_with_empty_flow_ids_skips_sync(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    db = _db_with_flow_owners()
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="FLOW_FOLDER_MOVE",
                technical_detail="Flow is deployed.",
                detail="Flow is deployed.",
            ),
            "ok",
        ]
    )

    result = await retry_flow_operation_on_deployment_guard(
        db=db,
        flow_ids=[],
        operation=operation,
    )

    assert result == "ok"
    assert operation.await_count == 2
    mock_sync_flow_deployment_state.assert_not_awaited()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", new_callable=AsyncMock)
async def test_flows_retry_propagates_sync_failure(mock_sync_flow_deployment_state):
    from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard

    flow_id = uuid4()
    db = _db_with_flow_owners([(flow_id, uuid4())])
    mock_sync_flow_deployment_state.side_effect = RuntimeError("sync failed")
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="FLOW_FOLDER_MOVE",
                technical_detail="Flow is deployed.",
                detail="Flow is deployed.",
            ),
            "ok",
        ]
    )

    with pytest.raises(RuntimeError, match="sync failed"):
        await retry_flow_operation_on_deployment_guard(
            db=db,
            flow_ids=[flow_id],
            operation=operation,
        )

    # Second attempt should not happen when sync raises.
    assert operation.await_count == 1
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
            DeploymentGuardError(
                code="PROJECT_DELETE",
                technical_detail="Project has deployments.",
                detail="Project has deployments.",
            ),
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


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_project_deployments", new_callable=AsyncMock)
async def test_projects_retry_on_deployment_guard_error_instance_uses_project_sync(mock_sync_project_deployments):
    from langflow.api.v1.mappers.deployments.sync import retry_project_operation_on_deployment_guard

    db = MagicMock()
    db.begin_nested.return_value = _AsyncNoopSavepoint()
    project_id = uuid4()
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="PROJECT_DELETE",
                technical_detail="Project has deployments.",
                detail="Project has deployments.",
            ),
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


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_project_deployments", new_callable=AsyncMock)
async def test_projects_retry_success_on_first_attempt_skips_sync(mock_sync_project_deployments):
    from langflow.api.v1.mappers.deployments.sync import retry_project_operation_on_deployment_guard

    db = MagicMock()
    db.begin_nested.return_value = _AsyncNoopSavepoint()
    operation = AsyncMock(return_value=None)

    await retry_project_operation_on_deployment_guard(
        db=db,
        user_id=uuid4(),
        project_id=uuid4(),
        operation=operation,
    )

    assert operation.await_count == 1
    assert db.begin_nested.call_count == 1
    mock_sync_project_deployments.assert_not_awaited()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_project_deployments", new_callable=AsyncMock)
async def test_projects_retry_non_guard_error_propagates_without_sync(mock_sync_project_deployments):
    from langflow.api.v1.mappers.deployments.sync import retry_project_operation_on_deployment_guard

    db = MagicMock()
    db.begin_nested.return_value = _AsyncNoopSavepoint()
    operation = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await retry_project_operation_on_deployment_guard(
            db=db,
            user_id=uuid4(),
            project_id=uuid4(),
            operation=operation,
        )

    assert operation.await_count == 1
    assert db.begin_nested.call_count == 1
    mock_sync_project_deployments.assert_not_awaited()


@pytest.mark.asyncio
@patch("langflow.api.v1.mappers.deployments.sync.sync_project_deployments", new_callable=AsyncMock)
async def test_projects_retry_propagates_sync_failure(mock_sync_project_deployments):
    from langflow.api.v1.mappers.deployments.sync import retry_project_operation_on_deployment_guard

    db = MagicMock()
    db.begin_nested.return_value = _AsyncNoopSavepoint()
    mock_sync_project_deployments.side_effect = RuntimeError("sync failed")
    operation = AsyncMock(
        side_effect=[
            DeploymentGuardError(
                code="PROJECT_DELETE",
                technical_detail="Project has deployments.",
                detail="Project has deployments.",
            ),
            None,
        ]
    )

    with pytest.raises(RuntimeError, match="sync failed"):
        await retry_project_operation_on_deployment_guard(
            db=db,
            user_id=uuid4(),
            project_id=uuid4(),
            operation=operation,
        )

    assert operation.await_count == 1
    mock_sync_project_deployments.assert_awaited_once()
