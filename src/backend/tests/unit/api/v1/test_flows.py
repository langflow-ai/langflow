import tempfile
import uuid

from fastapi import status
from httpx import AsyncClient


async def test_create_flow(client: AsyncClient, logged_in_headers):
    # Use relative path - absolute paths outside allowed directory are rejected
    flow_filename = f"{uuid.uuid4()}.json"
    basic_case = {
        "name": "string",
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "string",
        "tags": ["string"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "fs_path": flow_filename,
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "data" in result, "The result must have a 'data' key"
    assert "description" in result, "The result must have a 'description' key"
    assert "endpoint_name" in result, "The result must have a 'endpoint_name' key"
    assert "folder_id" in result, "The result must have a 'folder_id' key"
    assert "gradient" in result, "The result must have a 'gradient' key"
    assert "icon" in result, "The result must have a 'icon' key"
    assert "icon_bg_color" in result, "The result must have a 'icon_bg_color' key"
    assert "id" in result, "The result must have a 'id' key"
    assert "is_component" in result, "The result must have a 'is_component' key"
    assert "name" in result, "The result must have a 'name' key"
    assert "tags" in result, "The result must have a 'tags' key"
    assert "updated_at" in result, "The result must have a 'updated_at' key"
    assert "user_id" in result, "The result must have a 'user_id' key"
    assert "webhook" in result, "The result must have a 'webhook' key"


async def test_read_flows(client: AsyncClient, logged_in_headers):
    params = {
        "remove_example_flows": False,
        "components_only": False,
        "get_all": True,
        "header_flows": False,
        "page": 1,
        "size": 50,
    }
    response = await client.get("api/v1/flows/", params=params, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"


async def test_read_flow(client: AsyncClient, logged_in_headers):
    basic_case = {
        "name": "string",
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "string",
        "tags": ["string"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    response_ = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]
    response = await client.get(f"api/v1/flows/{id_}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "data" in result, "The result must have a 'data' key"
    assert "description" in result, "The result must have a 'description' key"
    assert "endpoint_name" in result, "The result must have a 'endpoint_name' key"
    assert "folder_id" in result, "The result must have a 'folder_id' key"
    assert "gradient" in result, "The result must have a 'gradient' key"
    assert "icon" in result, "The result must have a 'icon' key"
    assert "icon_bg_color" in result, "The result must have a 'icon_bg_color' key"
    assert "id" in result, "The result must have a 'id' key"
    assert "is_component" in result, "The result must have a 'is_component' key"
    assert "name" in result, "The result must have a 'name' key"
    assert "tags" in result, "The result must have a 'tags' key"
    assert "updated_at" in result, "The result must have a 'updated_at' key"
    assert "user_id" in result, "The result must have a 'user_id' key"
    assert "webhook" in result, "The result must have a 'webhook' key"


async def test_update_flow(client: AsyncClient, logged_in_headers):
    name = "first_name"
    updated_name = "second_name"
    basic_case = {
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "string",
        "tags": ["string"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    basic_case["name"] = name
    response_ = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    # Use relative path - absolute paths outside allowed directory are rejected
    flow_filename = f"{uuid.uuid4()!s}.json"
    basic_case["name"] = updated_name
    basic_case["fs_path"] = flow_filename

    response = await client.patch(f"api/v1/flows/{id_}", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert isinstance(result, dict), "The result must be a dictionary"
    assert "data" in result, "The result must have a 'data' key"
    assert "description" in result, "The result must have a 'description' key"
    assert "endpoint_name" in result, "The result must have a 'endpoint_name' key"
    assert "folder_id" in result, "The result must have a 'folder_id' key"
    assert "gradient" in result, "The result must have a 'gradient' key"
    assert "icon" in result, "The result must have a 'icon' key"
    assert "icon_bg_color" in result, "The result must have a 'icon_bg_color' key"
    assert "id" in result, "The result must have a 'id' key"
    assert "is_component" in result, "The result must have a 'is_component' key"
    assert "name" in result, "The result must have a 'name' key"
    assert "tags" in result, "The result must have a 'tags' key"
    assert "updated_at" in result, "The result must have a 'updated_at' key"
    assert "user_id" in result, "The result must have a 'user_id' key"
    assert "webhook" in result, "The result must have a 'webhook' key"
    assert result["name"] == updated_name, "The name must be updated"


async def test_create_flows(client: AsyncClient, logged_in_headers):
    amount_flows = 10
    basic_case = {
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "tags": ["string"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    cases = []
    for i in range(amount_flows):
        case = basic_case.copy()
        case["name"] = f"string_{i}"
        case["endpoint_name"] = f"string_{i}"
        cases.append(case)

    response = await client.post("api/v1/flows/batch/", json={"flows": cases}, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, list), "The result must be a list"
    assert len(result) == amount_flows, "The result must have the same amount of flows"


async def test_read_basic_examples(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/flows/basic_examples/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"
    assert len(result) > 0, "The result must have at least one flow"


async def test_read_flows_user_isolation(client: AsyncClient, logged_in_headers, active_user):
    """Test that read_flows returns only flows from the current user."""
    from uuid import uuid4

    from langflow.services.auth.utils import get_password_hash
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope

    # Create a second user
    other_user_id = uuid4()
    async with session_scope() as session:
        other_user = User(
            id=other_user_id,
            username="other_test_user",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

    # Login as the other user to get headers
    login_data = {"username": "other_test_user", "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    other_user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create flows for the first user (active_user)
    flow_user1_1 = {
        "name": "user1_flow_1",
        "description": "Flow 1 for user 1",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "user1_flow_1_endpoint",
        "tags": ["user1"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }

    flow_user1_2 = {
        "name": "user1_flow_2",
        "description": "Flow 2 for user 1",
        "icon": "string",
        "icon_bg_color": "#00ff00",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "user1_flow_2_endpoint",
        "tags": ["user1"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }

    # Create flows for the second user
    flow_user2_1 = {
        "name": "user2_flow_1",
        "description": "Flow 1 for user 2",
        "icon": "string",
        "icon_bg_color": "#0000ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "user2_flow_1_endpoint",
        "tags": ["user2"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }

    # Create flows using the appropriate user headers
    response1 = await client.post("api/v1/flows/", json=flow_user1_1, headers=logged_in_headers)
    assert response1.status_code == status.HTTP_201_CREATED

    response2 = await client.post("api/v1/flows/", json=flow_user1_2, headers=logged_in_headers)
    assert response2.status_code == status.HTTP_201_CREATED

    response3 = await client.post("api/v1/flows/", json=flow_user2_1, headers=other_user_headers)
    assert response3.status_code == status.HTTP_201_CREATED

    # Test read_flows for user 1 - should only return user 1's flows
    params = {
        "remove_example_flows": True,  # Exclude example flows to focus on our test flows
        "components_only": False,
        "get_all": True,
        "header_flows": False,
        "page": 1,
        "size": 50,
    }

    response_user1 = await client.get("api/v1/flows/", params=params, headers=logged_in_headers)
    result_user1 = response_user1.json()

    assert response_user1.status_code == status.HTTP_200_OK
    assert isinstance(result_user1, list), "The result must be a list"

    # Verify only user 1's flows are returned
    user1_flow_names = [flow["name"] for flow in result_user1]
    assert "user1_flow_1" in user1_flow_names, "User 1's first flow should be returned"
    assert "user1_flow_2" in user1_flow_names, "User 1's second flow should be returned"
    assert "user2_flow_1" not in user1_flow_names, "User 2's flow should not be returned for user 1"

    # Verify all returned flows belong to user 1
    for flow in result_user1:
        assert str(flow["user_id"]) == str(active_user.id), f"Flow {flow['name']} should belong to user 1"

    # Test read_flows for user 2 - should only return user 2's flows
    response_user2 = await client.get("api/v1/flows/", params=params, headers=other_user_headers)
    result_user2 = response_user2.json()

    assert response_user2.status_code == status.HTTP_200_OK
    assert isinstance(result_user2, list), "The result must be a list"

    # Verify only user 2's flows are returned
    user2_flow_names = [flow["name"] for flow in result_user2]
    assert "user2_flow_1" in user2_flow_names, "User 2's flow should be returned"
    assert "user1_flow_1" not in user2_flow_names, "User 1's first flow should not be returned for user 2"
    assert "user1_flow_2" not in user2_flow_names, "User 1's second flow should not be returned for user 2"

    # Verify all returned flows belong to user 2
    for flow in result_user2:
        assert str(flow["user_id"]) == str(other_user_id), f"Flow {flow['name']} should belong to user 2"

    # Cleanup: Delete the other user
    async with session_scope() as session:
        user = await session.get(User, other_user_id)
        if user:
            await session.delete(user)
            await session.commit()


async def test_create_flow_rejects_absolute_path_outside_allowed_directory(client: AsyncClient, logged_in_headers):
    """Test that absolute paths outside the allowed directory are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "/etc/passwd",  # Absolute path outside allowed directory should be rejected
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "within" in response.json()["detail"].lower() or "outside" in response.json()["detail"].lower()


async def test_create_flow_rejects_directory_traversal(client: AsyncClient, logged_in_headers):
    """Test that directory traversal sequences are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "../../etc/passwd",  # Directory traversal should be rejected
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "directory traversal" in response.json()["detail"].lower()
        or "absolute paths" in response.json()["detail"].lower()
    )


async def test_create_flow_rejects_null_bytes(client: AsyncClient, logged_in_headers):
    """Test that null bytes in paths are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "file\x00name.json",  # Null byte should be rejected
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "absolute paths" in response.json()["detail"].lower() or "null" in response.json()["detail"].lower()


async def test_create_flow_rejects_windows_absolute_path_outside_allowed_directory(
    client: AsyncClient, logged_in_headers
):
    """Test that Windows-style absolute paths outside the allowed directory are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "C:\\Windows\\System32\\config\\sam",  # Windows absolute path outside
        # allowed directory should be rejected
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "within" in response.json()["detail"].lower() or "outside" in response.json()["detail"].lower()


async def test_create_flow_accepts_relative_path(client: AsyncClient, logged_in_headers):
    """Test that valid relative paths are accepted."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "my_flow.json",  # Valid relative path
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED


async def test_create_flow_accepts_nested_relative_path(client: AsyncClient, logged_in_headers):
    """Test that nested relative paths are accepted."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "subfolder/my_flow.json",  # Valid nested relative path
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED


async def test_update_flow_rejects_absolute_path_outside_allowed_directory(client: AsyncClient, logged_in_headers):
    """Test that updating a flow with an absolute path outside allowed directory is rejected."""
    # First create a flow
    basic_case = {
        "name": "test_flow",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    # Try to update with absolute path outside allowed directory
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        update_case = {
            "fs_path": temp_file.name,
        }
    update_response = await client.patch(f"api/v1/flows/{flow_id}", json=update_case, headers=logged_in_headers)
    assert update_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "within" in update_response.json()["detail"].lower() or "outside" in update_response.json()["detail"].lower()


async def test_update_flow_accepts_relative_path(client: AsyncClient, logged_in_headers):
    """Test that updating a flow with a relative path is accepted."""
    # First create a flow
    basic_case = {
        "name": "test_flow",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    # Update with valid relative path
    update_case = {
        "fs_path": "updated_flow.json",
    }
    update_response = await client.patch(f"api/v1/flows/{flow_id}", json=update_case, headers=logged_in_headers)
    assert update_response.status_code == status.HTTP_200_OK


async def test_create_flow_rejects_empty_path(client: AsyncClient, logged_in_headers):
    """Test that empty fs_path is handled correctly (should be allowed as None).

    But empty string should fail validation.
    """
    # Empty string should fail validation if fs_path validation is called
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "",  # Empty string
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    # Empty string should be rejected by validation
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_create_flow_allows_none_path(client: AsyncClient, logged_in_headers):
    """Test that None/null fs_path is allowed (no file saving)."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        # fs_path not provided (None)
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED


async def test_create_flow_rejects_multiple_traversal(client: AsyncClient, logged_in_headers):
    """Test that multiple directory traversal sequences are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "../../../etc/passwd",  # Multiple traversals
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_create_flow_rejects_traversal_in_subpath(client: AsyncClient, logged_in_headers):
    """Test that directory traversal in subpaths is rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "subfolder/../../etc/passwd",  # Traversal in subpath
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_upload_flow_rejects_absolute_path(client: AsyncClient, logged_in_headers):
    """Test that uploading flows with absolute paths is rejected."""
    import json

    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        flow_data = {
            "name": "test_flow",
            "data": {},
            "fs_path": temp_file.name,  # Absolute path
        }
    # Create a JSON file content
    file_content = json.dumps({"flows": [flow_data]})

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
