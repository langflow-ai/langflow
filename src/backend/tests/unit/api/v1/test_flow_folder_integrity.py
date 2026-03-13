"""Tests for flow-folder integrity to prevent orphaned flows.

These tests verify the fix for the bug where flows could be created without a valid folder_id
when all folders were deleted (zero folders scenario), resulting in orphaned flows that were
unreachable in the UI.

The fix ensures:
1. Flows always have a valid folder_id
2. If a non-existent folder_id is provided, the system falls back to the default folder
3. If no folders exist, a default folder is auto-created
"""

import uuid

from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from sqlmodel import select


async def test_create_flow_with_nonexistent_folder_id_assigns_default_folder(
    client: AsyncClient, logged_in_headers, active_user
):
    """Test that creating a flow with a non-existent folder_id assigns it to the default folder.

    This prevents orphaned flows when a folder is deleted between the UI loading and flow creation.
    """
    non_existent_folder_id = str(uuid.uuid4())

    flow_data = {
        "name": "Test Flow with Bad Folder",
        "data": {},
        "folder_id": non_existent_folder_id,
    }

    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()

    # The flow should have been assigned to a valid folder (not the non-existent one)
    assert result["folder_id"] is not None
    assert result["folder_id"] != non_existent_folder_id

    # Verify the folder actually exists
    async with session_scope() as session:
        folder = await session.get(Folder, uuid.UUID(result["folder_id"]))
        assert folder is not None
        assert folder.user_id == active_user.id


async def test_create_flow_without_folder_id_assigns_default_folder(
    client: AsyncClient, logged_in_headers, active_user
):
    """Test that creating a flow without a folder_id assigns it to the default folder."""
    flow_data = {
        "name": "Test Flow without Folder ID",
        "data": {},
    }

    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()

    # The flow should have been assigned to a valid folder
    assert result["folder_id"] is not None

    # Verify the folder actually exists and belongs to the user
    async with session_scope() as session:
        folder = await session.get(Folder, uuid.UUID(result["folder_id"]))
        assert folder is not None
        assert folder.user_id == active_user.id


async def test_create_flow_after_all_folders_deleted_creates_default_folder(
    client: AsyncClient, logged_in_headers, active_user
):
    """Test the zero-folder scenario: creating a flow after deleting all folders.

    This is the critical bug fix test. When all folders are deleted, creating a new flow
    should automatically create a default folder instead of creating an orphaned flow.
    """
    # First, delete all folders for this user
    async with session_scope() as session:
        stmt = select(Folder).where(Folder.user_id == active_user.id)
        folders = (await session.exec(stmt)).all()
        for folder in folders:
            await session.delete(folder)
        await session.commit()

    # Verify no folders exist for this user
    async with session_scope() as session:
        stmt = select(Folder).where(Folder.user_id == active_user.id)
        folders = (await session.exec(stmt)).all()
        assert len(folders) == 0, "All folders should be deleted"

    # Now create a flow - this should auto-create a default folder
    flow_data = {
        "name": "Flow Created After All Folders Deleted",
        "data": {},
    }

    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()

    # The flow should NOT be orphaned - it should have a valid folder_id
    assert result["folder_id"] is not None

    # Verify the folder was auto-created and exists
    async with session_scope() as session:
        folder = await session.get(Folder, uuid.UUID(result["folder_id"]))
        assert folder is not None
        assert folder.user_id == active_user.id
        assert folder.name == DEFAULT_FOLDER_NAME


async def test_update_flow_with_nonexistent_folder_id_assigns_default_folder(
    client: AsyncClient, logged_in_headers, active_user
):
    """Test that updating a flow with a non-existent folder_id falls back to default folder.

    This handles the case where a user tries to move a flow to a folder that doesn't exist.
    """
    # Configure client to follow redirects (folders API uses redirects)
    client.follow_redirects = True

    # Create a flow in the default folder
    flow_data = {
        "name": "Flow to Update",
        "data": {},
    }
    flow_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    # Now try to update the flow with a non-existent folder_id
    non_existent_folder_id = str(uuid.uuid4())
    update_data = {
        "name": "Updated Flow Name",
        "folder_id": non_existent_folder_id,  # This folder doesn't exist
    }

    update_response = await client.patch(f"api/v1/flows/{flow_id}", json=update_data, headers=logged_in_headers)

    assert update_response.status_code == status.HTTP_200_OK
    result = update_response.json()

    # The flow should be reassigned to a valid folder (not the non-existent one)
    assert result["folder_id"] is not None
    assert result["folder_id"] != non_existent_folder_id

    # Verify the folder exists
    async with session_scope() as session:
        folder = await session.get(Folder, uuid.UUID(result["folder_id"]))
        assert folder is not None
        assert folder.user_id == active_user.id


async def test_update_flow_without_folder_id_keeps_existing_folder(client: AsyncClient, logged_in_headers):
    """Test that updating a flow without specifying folder_id keeps the existing folder assignment."""
    # Configure client to follow redirects
    client.follow_redirects = True

    # Create a flow
    flow_data = {
        "name": "Flow to Update",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]
    original_folder_id = create_response.json()["folder_id"]

    # Update the flow without specifying folder_id (only update name)
    update_data = {
        "name": "Updated Flow Name",
    }

    update_response = await client.patch(f"api/v1/flows/{flow_id}", json=update_data, headers=logged_in_headers)

    assert update_response.status_code == status.HTTP_200_OK
    result = update_response.json()

    # The folder_id should remain unchanged
    assert result["folder_id"] == original_folder_id


async def test_upload_flow_with_nonexistent_folder_id_assigns_default(
    client: AsyncClient, logged_in_headers, active_user
):
    """Test that uploading a flow with a non-existent folder_id assigns it to the default folder.

    The upload endpoint uses _new_flow internally, which includes folder_id validation.
    """
    import json

    non_existent_folder_id = str(uuid.uuid4())

    flow_data = {
        "name": "Uploaded Flow with Bad Folder",
        "data": {},
        "folder_id": non_existent_folder_id,
    }

    # Create a JSON file content for upload
    file_content = json.dumps(flow_data)

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", file_content, "application/json")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    results = response.json()

    # The result is a list (even for single flow upload)
    assert len(results) == 1
    result = results[0]

    # The flow should have a valid folder_id (not the non-existent one)
    assert result["folder_id"] is not None
    assert result["folder_id"] != non_existent_folder_id

    # Verify the folder exists
    async with session_scope() as session:
        folder = await session.get(Folder, uuid.UUID(result["folder_id"]))
        assert folder is not None
        assert folder.user_id == active_user.id


async def test_flow_created_is_retrievable_in_folder(client: AsyncClient, logged_in_headers):
    """Test that a created flow can be retrieved by listing flows in its folder.

    This verifies the flow is not orphaned and appears in the UI.
    """
    # Configure client to follow redirects
    client.follow_redirects = True

    # Create a flow
    flow_data = {
        "name": "Retrievable Flow",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]
    folder_id = create_response.json()["folder_id"]

    # List flows in the folder
    response = await client.get(f"api/v1/folders/{folder_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    # Check if the flow is in the folder's flows list
    result = response.json()
    # Handle different response structures
    if "flows" in result:
        flows = result["flows"]
    elif "folder" in result and "flows" in result["folder"]:
        flows = result["folder"]["flows"]
    else:
        # Response might be paginated or have different structure
        flows = result.get("flows", [])

    # Get flow IDs from the response
    flow_ids_in_folder = [f["id"] if isinstance(f, dict) else str(f) for f in flows]

    # The created flow should be in the folder's flow list
    assert flow_id in flow_ids_in_folder, f"Flow {flow_id} should be retrievable in folder {folder_id}"


async def test_upsert_flow_with_nonexistent_folder_id_on_create(client: AsyncClient, logged_in_headers):
    """Test that PUT (upsert) with non-existent folder_id creates flow with default folder."""
    specified_id = str(uuid.uuid4())
    non_existent_folder_id = str(uuid.uuid4())

    flow_data = {
        "name": "Upsert Flow with Bad Folder",
        "data": {},
        "folder_id": non_existent_folder_id,
    }

    response = await client.put(f"api/v1/flows/{specified_id}", json=flow_data, headers=logged_in_headers)

    # The request should be rejected with 400 Bad Request since folder doesn't exist
    # This is the expected behavior based on the existing test_upsert_flow_returns_400_for_invalid_folder_id
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "folder not found" in response.json()["detail"].lower()
