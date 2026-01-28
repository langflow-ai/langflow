"""Tests for folder utility functions.

These tests verify the utility functions used to ensure flows always have a valid folder.
"""

import uuid

import pytest
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.utils import (
    create_default_folder_if_it_doesnt_exist,
    get_default_folder_id,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select


@pytest.fixture
async def test_user_for_folder_utils(client):
    """Create a test user specifically for folder utility tests."""
    user_id = uuid.uuid4()
    async with session_scope() as session:
        user = User(
            id=user_id,
            username=f"folder_utils_test_user_{user_id}",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    yield user

    # Cleanup
    async with session_scope() as session:
        # Delete user's folders first
        stmt = select(Folder).where(Folder.user_id == user_id)
        folders = (await session.exec(stmt)).all()
        for folder in folders:
            await session.delete(folder)

        # Delete user
        user_to_delete = await session.get(User, user_id)
        if user_to_delete:
            await session.delete(user_to_delete)


async def test_get_default_folder_id_returns_existing_default_folder(
    client,
    test_user_for_folder_utils,
):
    """Test that get_default_folder_id returns existing default folder's ID."""
    user_id = test_user_for_folder_utils.id

    # Create a default folder for the user
    async with session_scope() as session:
        folder = Folder(
            name=DEFAULT_FOLDER_NAME,
            user_id=user_id,
            description="Test default folder",
        )
        session.add(folder)
        await session.flush()
        await session.refresh(folder)
        expected_folder_id = folder.id

    # Call get_default_folder_id
    async with session_scope() as session:
        result_id = await get_default_folder_id(session, user_id)

    assert result_id == expected_folder_id


async def test_get_default_folder_id_creates_folder_when_none_exist(
    client,
    test_user_for_folder_utils,
):
    """Test that get_default_folder_id creates a default folder when none exist."""
    user_id = test_user_for_folder_utils.id

    # Ensure no folders exist for this user
    async with session_scope() as session:
        stmt = select(Folder).where(Folder.user_id == user_id)
        folders = (await session.exec(stmt)).all()
        for folder in folders:
            await session.delete(folder)
        await session.commit()

    # Verify no folders exist
    async with session_scope() as session:
        stmt = select(Folder).where(Folder.user_id == user_id)
        folders = (await session.exec(stmt)).all()
        assert len(folders) == 0

    # Call get_default_folder_id - should create a folder
    async with session_scope() as session:
        result_id = await get_default_folder_id(session, user_id)

    # Verify the folder was created
    async with session_scope() as session:
        folder = await session.get(Folder, result_id)
        assert folder is not None
        assert folder.user_id == user_id
        assert folder.name == DEFAULT_FOLDER_NAME


async def test_create_default_folder_if_it_doesnt_exist_creates_folder(
    client,
    test_user_for_folder_utils,
):
    """Test that create_default_folder_if_it_doesnt_exist creates a folder when none exist."""
    user_id = test_user_for_folder_utils.id

    # Ensure no folders exist for this user
    async with session_scope() as session:
        stmt = select(Folder).where(Folder.user_id == user_id)
        folders = (await session.exec(stmt)).all()
        for folder in folders:
            await session.delete(folder)
        await session.commit()

    # Call create_default_folder_if_it_doesnt_exist
    async with session_scope() as session:
        folder = await create_default_folder_if_it_doesnt_exist(session, user_id)
        await session.commit()

    assert folder is not None
    assert folder.user_id == user_id
    assert folder.name == DEFAULT_FOLDER_NAME


async def test_create_default_folder_if_it_doesnt_exist_returns_existing(
    client,
    test_user_for_folder_utils,
):
    """Test that create_default_folder_if_it_doesnt_exist returns existing folder."""
    user_id = test_user_for_folder_utils.id

    # Create a folder first
    async with session_scope() as session:
        existing_folder = Folder(
            name="Some Existing Folder",
            user_id=user_id,
            description="Existing folder",
        )
        session.add(existing_folder)
        await session.flush()
        await session.refresh(existing_folder)
        existing_folder_id = existing_folder.id

    # Call create_default_folder_if_it_doesnt_exist - should return the existing folder
    async with session_scope() as session:
        folder = await create_default_folder_if_it_doesnt_exist(session, user_id)

    # Should return the existing folder (any folder, not necessarily DEFAULT_FOLDER_NAME)
    assert folder is not None
    assert folder.id == existing_folder_id


async def test_get_default_folder_id_creates_named_default_folder(
    client,
    test_user_for_folder_utils,
):
    """Test that get_default_folder_id creates a folder with DEFAULT_FOLDER_NAME."""
    user_id = test_user_for_folder_utils.id

    # Create a folder with a different name (not DEFAULT_FOLDER_NAME)
    async with session_scope() as session:
        non_default_folder = Folder(
            name="Custom Folder Name",
            user_id=user_id,
            description="Not the default folder",
        )
        session.add(non_default_folder)
        await session.commit()

    # Call get_default_folder_id - should create a new folder with DEFAULT_FOLDER_NAME
    # because the existing folder doesn't have that name
    async with session_scope() as session:
        result_id = await get_default_folder_id(session, user_id)
        await session.commit()

    # Verify a folder with DEFAULT_FOLDER_NAME now exists
    async with session_scope() as session:
        folder = await session.get(Folder, result_id)
        assert folder is not None
        assert folder.name == DEFAULT_FOLDER_NAME


async def test_get_default_folder_id_is_idempotent(
    client,
    test_user_for_folder_utils,
):
    """Test that calling get_default_folder_id multiple times returns the same folder."""
    user_id = test_user_for_folder_utils.id

    # Ensure no default folder exists
    async with session_scope() as session:
        stmt = select(Folder).where(Folder.user_id == user_id, Folder.name == DEFAULT_FOLDER_NAME)
        default_folders = (await session.exec(stmt)).all()
        for folder in default_folders:
            await session.delete(folder)
        await session.commit()

    # Call get_default_folder_id multiple times
    async with session_scope() as session:
        first_result = await get_default_folder_id(session, user_id)
        await session.commit()

    async with session_scope() as session:
        second_result = await get_default_folder_id(session, user_id)
        await session.commit()

    async with session_scope() as session:
        third_result = await get_default_folder_id(session, user_id)
        await session.commit()

    # All calls should return the same folder ID
    assert first_result == second_result == third_result

    # Verify only one default folder exists
    async with session_scope() as session:
        stmt = select(Folder).where(Folder.user_id == user_id, Folder.name == DEFAULT_FOLDER_NAME)
        default_folders = (await session.exec(stmt)).all()
        assert len(default_folders) == 1
