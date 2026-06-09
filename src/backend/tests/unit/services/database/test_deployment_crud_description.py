from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import create_deployment, update_deployment
from langflow.services.database.models.deployment.model import Deployment
from lfx.services.adapters.deployment.schema import DEPLOYMENT_DESCRIPTION_MAX_LENGTH, DeploymentType


def _fake_db():
    return SimpleNamespace(
        add=Mock(),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )


@pytest.mark.anyio
async def test_create_deployment_rejects_description_over_max_length():
    db = _fake_db()

    with pytest.raises(ValueError, match="at most"):
        await create_deployment(
            db,
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            resource_key="rk-1",
            name="deployment",
            deployment_type=DeploymentType.AGENT,
            description="x" * (DEPLOYMENT_DESCRIPTION_MAX_LENGTH + 1),
        )

    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.anyio
async def test_update_deployment_rejects_description_over_max_length():
    db = _fake_db()
    deployment = Deployment(
        resource_key="rk-1",
        user_id=uuid4(),
        project_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        name="deployment",
        deployment_type=DeploymentType.AGENT,
    )

    with pytest.raises(ValueError, match="at most"):
        await update_deployment(
            db,
            deployment=deployment,
            description="x" * (DEPLOYMENT_DESCRIPTION_MAX_LENGTH + 1),
        )

    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.anyio
async def test_create_deployment_accepts_description_at_max_length():
    db = _fake_db()
    description = "x" * DEPLOYMENT_DESCRIPTION_MAX_LENGTH

    row = await create_deployment(
        db,
        user_id=uuid4(),
        project_id=uuid4(),
        deployment_provider_account_id=uuid4(),
        resource_key="rk-1",
        name="deployment",
        deployment_type=DeploymentType.AGENT,
        description=description,
    )

    assert row.description == description
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once()
