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
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


@pytest.mark.asyncio
async def test_check_flow_has_deployed_versions_allows_when_no_attachments() -> None:
    db = AsyncMock()
    db.exec = AsyncMock(return_value=_ExecResult(None))

    await check_flow_has_deployed_versions(db, flow_id=uuid4())


@pytest.mark.asyncio
async def test_check_flow_has_deployed_versions_raises_guard_when_attached() -> None:
    db = AsyncMock()
    db.exec = AsyncMock(return_value=_ExecResult(uuid4()))

    with pytest.raises(DeploymentGuardError) as exc_info:
        await check_flow_has_deployed_versions(db, flow_id=uuid4())

    assert exc_info.value.code == "FLOW_HAS_DEPLOYED_VERSIONS"
    assert (
        exc_info.value.detail == "This flow cannot be deleted because it has deployed versions. "
        "Please remove its versions from deployments first."
    )


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
