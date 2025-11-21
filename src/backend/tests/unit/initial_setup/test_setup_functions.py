import asyncio
from uuid import uuid4

import pytest
from langflow.initial_setup.setup import get_or_create_default_folder, session_scope
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import FolderRead


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_creation() -> None:
    """Test that a default project is created for a new user.

    This test verifies that when no default project exists for a given user,
    get_or_create_default_folder creates one with the expected name and assigns it an ID.
    """
    test_user_id = uuid4()
    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, test_user_id)
        assert folder.name == DEFAULT_FOLDER_NAME, "The project name should match the default."
        assert hasattr(folder, "id"), "The project should have an 'id' attribute after creation."


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_idempotency() -> None:
    """Test that subsequent calls to get_or_create_default_folder return the same project.

    The function should be idempotent such that if a default project already exists,
    calling the function again does not create a new one.
    """
    test_user_id = uuid4()
    async with session_scope() as session:
        folder_first = await get_or_create_default_folder(session, test_user_id)
        folder_second = await get_or_create_default_folder(session, test_user_id)
        assert folder_first.id == folder_second.id, "Both calls should return the same folder instance."


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_concurrent_calls() -> None:
    """Test concurrent invocations of get_or_create_default_folder.

    This test ensures that when multiple concurrent calls are made for the same user,
    only one default project is created, demonstrating idempotency under concurrent access.
    """
    test_user_id = uuid4()

    async def get_folder() -> FolderRead:
        async with session_scope() as session:
            return await get_or_create_default_folder(session, test_user_id)

    results = await asyncio.gather(get_folder(), get_folder(), get_folder())
    folder_ids = {folder.id for folder in results}
    assert len(folder_ids) == 1, "Concurrent calls must return a single, consistent folder instance."
