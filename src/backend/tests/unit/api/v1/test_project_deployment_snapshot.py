from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response, status
from langflow.api.v1 import projects
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deployment_artifacts import (
    ProjectArtifactError,
    ProjectArtifactLimitError,
    ProjectArtifactNotFoundError,
    ProjectDeploymentSnapshot,
    ProjectDeploymentSnapshotFlow,
    build_project_deployment_snapshot,
)


def _snapshot_session(project: Folder, flow: Flow) -> AsyncMock:
    ordered = [(flow.id, flow.user_id, flow.updated_at)]
    revision_result = MagicMock()
    revision_result.all.return_value = ordered
    flow_result = MagicMock()
    flow_result.all.return_value = [flow]
    final_revision_result = MagicMock()
    final_revision_result.all.return_value = ordered
    project_result = MagicMock()
    project_result.first.return_value = (project.id, project.name, project.description)
    session = AsyncMock()
    session.exec.side_effect = [revision_result, flow_result, final_revision_result, project_result]
    return session


@pytest.mark.asyncio
async def test_snapshot_builder_returns_complete_consistent_content_without_writes() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="support-automation", description="Captured", user_id=actor_id)
    flow = Flow(
        id=uuid4(),
        name="Triage",
        description="Route a request",
        user_id=actor_id,
        folder_id=project_id,
        data={
            "nodes": [
                {
                    "id": "node-1",
                    "positionAbsolute": {"x": 8, "y": 13},
                    "dragging": True,
                    "selected": False,
                }
            ],
            "edges": [],
        },
    )
    session = _snapshot_session(project, flow)
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with (
        patch(
            "langflow.services.deployment_artifacts.builder.authorized_or_owner_scoped",
            new_callable=AsyncMock,
            return_value=project,
        ),
        patch("langflow.services.deployment_artifacts.builder.ensure_project_permission", new_callable=AsyncMock),
        patch("langflow.services.deployment_artifacts.builder.ensure_flows_permission", new_callable=AsyncMock),
    ):
        snapshot = await build_project_deployment_snapshot(session, user, project_id)

    assert snapshot.project_id == project_id
    assert snapshot.project_name == project.name
    assert snapshot.project_description == project.description
    assert snapshot.flows == (
        ProjectDeploymentSnapshotFlow(
            flow_id=flow.id,
            name=flow.name,
            description=flow.description,
            data={
                "nodes": [
                    {
                        "id": "node-1",
                        "positionAbsolute": {"x": 8, "y": 13},
                        "dragging": True,
                        "selected": False,
                    }
                ],
                "edges": [],
            },
        ),
    )
    assert snapshot.dependencies == {}
    assert snapshot.required_variables == ()
    session.commit.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_route_always_returns_required_containers_and_no_store() -> None:
    project_id = uuid4()
    flow_id = uuid4()
    snapshot = ProjectDeploymentSnapshot(
        project_id=project_id,
        project_name="support-automation",
        project_description=None,
        flows=(ProjectDeploymentSnapshotFlow(flow_id, "Triage", None, {"nodes": [], "edges": []}),),
        dependencies={},
        required_variables=(),
    )
    response = Response()
    session = AsyncMock()
    user = SimpleNamespace(id=uuid4())

    with (
        patch.object(projects, "_begin_deployment_snapshot_transaction", new_callable=AsyncMock),
        patch.object(
            projects,
            "build_project_deployment_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ) as capture,
    ):
        result = await projects.read_project_deployment_snapshot(
            session=session,
            project_id=project_id,
            current_user=user,
            response=response,
        )

    assert result.project.id == project_id
    assert result.project.description is None
    assert result.flows[0].id == flow_id
    assert result.dependencies == {}
    assert result.required_variables == []
    assert response.headers["cache-control"] == "no-store"
    capture.assert_awaited_once_with(session, user, project_id)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_route_masks_auth_denial_and_does_not_expose_capture_details() -> None:
    session = AsyncMock()
    response = Response()
    secret = "literal-secret-must-not-escape"  # noqa: S105  # pragma: allowlist secret

    with (
        patch.object(projects, "_begin_deployment_snapshot_transaction", new_callable=AsyncMock),
        patch.object(
            projects,
            "build_project_deployment_snapshot",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=secret),
        ),
        pytest.raises(HTTPException) as raised,
    ):
        await projects.read_project_deployment_snapshot(
            session=session,
            project_id=uuid4(),
            current_user=SimpleNamespace(id=uuid4()),
            response=response,
        )

    assert raised.value.status_code == status.HTTP_404_NOT_FOUND
    assert raised.value.detail == "Project not found"
    assert secret not in str(raised.value.detail)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_route_refuses_unsafe_capture_without_raw_error() -> None:
    session = AsyncMock()
    response = Response()
    secret = "literal-secret-must-not-escape"  # noqa: S105  # pragma: allowlist secret

    with (
        patch.object(projects, "_begin_deployment_snapshot_transaction", new_callable=AsyncMock),
        patch.object(
            projects,
            "build_project_deployment_snapshot",
            new_callable=AsyncMock,
            side_effect=ProjectArtifactError(secret),
        ),
        pytest.raises(HTTPException) as raised,
    ):
        await projects.read_project_deployment_snapshot(
            session=session,
            project_id=uuid4(),
            current_user=SimpleNamespace(id=uuid4()),
            response=response,
        )

    assert raised.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert raised.value.detail == "Project snapshot could not be captured safely"
    assert secret not in str(raised.value.detail)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (ProjectArtifactLimitError("snapshot too large"), status.HTTP_413_CONTENT_TOO_LARGE),
        (ProjectArtifactNotFoundError("Project not found"), status.HTTP_404_NOT_FOUND),
    ],
)
async def test_snapshot_route_maps_bounded_capture_failures(failure, expected_status) -> None:
    session = AsyncMock()
    response = Response()

    with (
        patch.object(projects, "_begin_deployment_snapshot_transaction", new_callable=AsyncMock),
        patch.object(projects, "build_project_deployment_snapshot", new_callable=AsyncMock, side_effect=failure),
        pytest.raises(HTTPException) as raised,
    ):
        await projects.read_project_deployment_snapshot(
            session=session,
            project_id=uuid4(),
            current_user=SimpleNamespace(id=uuid4()),
            response=response,
        )

    assert raised.value.status_code == expected_status
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_transaction_starts_before_first_sqlite_read() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    session.rollback = AsyncMock()
    session.begin = AsyncMock()
    session.in_transaction.return_value = False
    session.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    await projects._begin_deployment_snapshot_transaction(session)

    session.execute.assert_awaited_once()
    assert str(session.execute.await_args.args[0]) == "BEGIN"


@pytest.mark.asyncio
async def test_snapshot_transaction_uses_repeatable_read_only_postgres() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    session.rollback = AsyncMock()
    session.begin = AsyncMock()
    session.in_transaction.return_value = False
    session.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    await projects._begin_deployment_snapshot_transaction(session)

    session.execute.assert_awaited_once()
    assert str(session.execute.await_args.args[0]) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
