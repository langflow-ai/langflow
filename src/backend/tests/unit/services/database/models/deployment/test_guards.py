from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.exceptions import DeploymentGuardError
from langflow.services.database.models.deployment.guards import (
    check_flow_has_deployed_versions,
    check_project_has_deployments,
)


class _ExecResult:
    def __init__(self, value, rowcount: int = 0):
        self._value = value
        self.rowcount = rowcount

    def first(self):
        return self._value

    def all(self):
        return self._value


@pytest.mark.asyncio
async def test_check_flow_has_deployed_versions_allows_when_no_attachments() -> None:
    db = AsyncMock()
    db.exec = AsyncMock(
        side_effect=[
            _ExecResult(None, rowcount=0),  # prune orphan attachments (no-op)
            _ExecResult(None),  # live deployment attachment lookup
        ]
    )

    await check_flow_has_deployed_versions(db, flow_id=uuid4())

    assert db.exec.await_count == 2


@pytest.mark.asyncio
async def test_check_flow_has_deployed_versions_raises_guard_when_attached() -> None:
    db = AsyncMock()
    db.exec = AsyncMock(
        side_effect=[
            _ExecResult(None, rowcount=0),  # prune orphan attachments (no-op)
            _ExecResult(uuid4()),  # live deployment attachment lookup
        ]
    )

    with pytest.raises(DeploymentGuardError) as exc_info:
        await check_flow_has_deployed_versions(db, flow_id=uuid4())

    assert exc_info.value.code == "FLOW_HAS_DEPLOYED_VERSIONS"
    assert (
        exc_info.value.detail == "This flow cannot be deleted because it has deployed versions. "
        "Please remove its versions from deployments first."
    )


@pytest.mark.asyncio
async def test_check_flow_has_deployed_versions_prunes_orphan_attachments() -> None:
    db = AsyncMock()
    db.exec = AsyncMock(
        side_effect=[
            _ExecResult(None, rowcount=1),  # prune orphan attachments (one row pruned)
            _ExecResult(None),  # live deployment attachment lookup
        ]
    )

    await check_flow_has_deployed_versions(db, flow_id=uuid4())

    assert db.exec.await_count == 2


@pytest.mark.asyncio
async def test_check_flow_has_deployed_versions_prunes_orphans_even_when_attached() -> None:
    """Prune step must run before the live-attachment check.

    This ensures flows with both orphan and live attachments still get their orphans cleaned up.
    """
    db = AsyncMock()
    db.exec = AsyncMock(
        side_effect=[
            _ExecResult(None, rowcount=2),  # prune orphan attachments
            _ExecResult(uuid4()),  # live deployment attachment lookup -> raises
        ]
    )

    with pytest.raises(DeploymentGuardError):
        await check_flow_has_deployed_versions(db, flow_id=uuid4())

    assert db.exec.await_count == 2


@pytest.mark.asyncio
async def test_check_project_has_deployments_allows_when_empty() -> None:
    db = AsyncMock()
    db.exec = AsyncMock(return_value=_ExecResult(None))

    await check_project_has_deployments(db, project_id=uuid4())


@pytest.mark.asyncio
async def test_check_project_has_deployments_raises_guard_when_present() -> None:
    db = AsyncMock()
    db.exec = AsyncMock(return_value=_ExecResult(uuid4()))

    with pytest.raises(DeploymentGuardError) as exc_info:
        await check_project_has_deployments(db, project_id=uuid4())

    assert exc_info.value.code == "PROJECT_HAS_DEPLOYMENTS"
    assert (
        exc_info.value.detail
        == "This project cannot be deleted because it has deployments. Please delete its deployments first."
    )
