from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import create_deployment, update_deployment
from langflow.services.database.models.deployment.model import Deployment
from lfx.services.adapters.deployment.schema import DeploymentType


def _fake_db():
    return SimpleNamespace(
        add=Mock(),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )


@pytest.mark.anyio
async def test_create_deployment_accepts_long_description():
    db = _fake_db()
    description = "x" * 501

    row = await create_deployment(
        db,
        user_id=uuid4(),
        project_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        resource_key="rk-1",
        display_name="deployment",
        deployment_type=DeploymentType.AGENT,
        description=description,
    )

    assert row.description == description
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once()


@pytest.mark.anyio
async def test_update_deployment_accepts_long_description():
    db = _fake_db()
    description = "x" * 501
    deployment = Deployment(
        resource_key="rk-1",
        user_id=uuid4(),
        project_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        display_name="deployment",
        deployment_type=DeploymentType.AGENT,
    )

    row = await update_deployment(
        db,
        deployment=deployment,
        description=description,
    )

    assert row.description == description
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once()
