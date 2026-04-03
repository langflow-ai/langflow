"""Focused unit tests for flow helper branches that are hard to force via HTTP."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anyio
import pytest
from fastapi import HTTPException
from langflow.api.v1.flows_helpers import _new_flow, _save_flow_to_fs
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.user.model import User
from langflow.services.storage.service import StorageService


@pytest.fixture
def storage_service(tmp_path):
    """Create a mock storage service with a temporary data directory."""
    service = MagicMock(spec=StorageService)
    service.data_dir = anyio.Path(tmp_path)
    return service


@pytest.fixture
async def current_user(async_session):
    """Create a user that can own flows in helper-level tests."""
    password = f"password-{uuid4()}"
    user = User(
        username=f"flow-helper-{uuid4()}",
        password=password,
        is_active=True,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_new_flow_with_validate_folder_rejects_unknown_folder(async_session, current_user, storage_service):
    """Test that validate_folder rejects a folder that does not belong to the user."""
    flow = FlowCreate(
        name="flow-with-bad-folder",
        data={},
        folder_id=uuid4(),
    )

    with (
        patch("langflow.api.v1.flows_helpers.get_default_folder_id", new=AsyncMock()) as mock_default_folder_id,
        pytest.raises(HTTPException) as exc_info,
    ):
        await _new_flow(
            session=async_session,
            flow=flow,
            user_id=current_user.id,
            storage_service=storage_service,
            validate_folder=True,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Folder not found"
    mock_default_folder_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_flow_to_fs_returns_500_on_os_error(current_user, storage_service):
    """Test that filesystem write errors surface as an HTTP 500."""
    flow = Flow(
        name="flow-write-error",
        data={},
        user_id=current_user.id,
        fs_path="nested/flow.json",
    )

    with (
        patch("langflow.api.v1.flows_helpers.async_open", side_effect=OSError("disk full")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await _save_flow_to_fs(flow, current_user.id, storage_service)

    assert exc_info.value.status_code == 500
    assert "disk full" in exc_info.value.detail
