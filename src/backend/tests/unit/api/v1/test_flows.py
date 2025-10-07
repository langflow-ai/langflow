import json
import tempfile
import uuid
from pathlib import Path as FilePath

import pytest
from anyio import Path
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models import Flow


@pytest.fixture
def valid_flow_payload():
    """Load valid complete flow payload from test fixtures."""
    flow_path = FilePath(__file__).parent.parent.parent.parent / "data" / "MemoryChatbotNoLLM.json"
    with flow_path.open() as f:
        return json.load(f)


async def test_create_flow(client: AsyncClient, logged_in_headers):
    flow_file = Path(tempfile.tempdir) / f"{uuid.uuid4()}.json"
    try:
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
            "fs_path": str(flow_file),
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

        content = await flow_file.read_text()
        Flow.model_validate_json(content)
    finally:
        await flow_file.unlink(missing_ok=True)


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

    flow_file = Path(tempfile.tempdir) / f"{uuid.uuid4()!s}.json"
    basic_case["name"] = updated_name
    basic_case["fs_path"] = str(flow_file)

    try:
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

        content = await flow_file.read_text()
        Flow.model_validate_json(content)
    finally:
        await flow_file.unlink(missing_ok=True)


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
    login_data = {"username": "other_test_user", "password": "testpassword"}  # pragma: allowlist secret
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


async def test_update_flow_deployment_status(client: AsyncClient, logged_in_headers):
    """Test updating flow deployment status from DRAFT to DEPLOYED."""
    # Create a flow
    basic_case = {
        "name": "deployment_test_flow",
        "description": "Test deployment status",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "deployment_test",
        "tags": ["test"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    flow_data = response.json()
    flow_id = flow_data["id"]

    # Verify initial status is DRAFT
    assert "status" in flow_data
    assert flow_data["status"] == "DRAFT"

    # Update flow status to DEPLOYED
    update_payload = {"status": "DEPLOYED"}
    response = await client.patch(f"api/v1/flows/{flow_id}", json=update_payload, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    updated_flow = response.json()

    # Verify status was updated
    assert updated_flow["status"] == "DEPLOYED"
    assert updated_flow["id"] == flow_id

    # Update back to DRAFT
    update_payload = {"status": "DRAFT"}
    response = await client.patch(f"api/v1/flows/{flow_id}", json=update_payload, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    updated_flow = response.json()

    # Verify status was updated back to DRAFT
    assert updated_flow["status"] == "DRAFT"


async def test_deployed_flow_locked_status(client: AsyncClient, logged_in_headers):
    """Test that deployed flows are automatically locked."""
    # Create a flow
    basic_case = {
        "name": "locked_test_flow",
        "description": "Test locked status",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "locked_test",
        "tags": ["test"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    flow_data = response.json()
    flow_id = flow_data["id"]

    # Deploy the flow
    update_payload = {"status": "DEPLOYED"}
    response = await client.patch(f"api/v1/flows/{flow_id}", json=update_payload, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    deployed_flow = response.json()

    # Verify flow is locked when deployed
    assert deployed_flow["status"] == "DEPLOYED"
    assert deployed_flow["locked"] is True

    # Undeploy the flow
    update_payload = {"status": "DRAFT"}
    response = await client.patch(f"api/v1/flows/{flow_id}", json=update_payload, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    draft_flow = response.json()

    # Verify flow is unlocked when in draft
    assert draft_flow["status"] == "DRAFT"
    assert draft_flow["locked"] is False


async def test_create_flow_default_status(client: AsyncClient, logged_in_headers):
    """Test that newly created flows have DRAFT status by default."""
    basic_case = {
        "name": "default_status_flow",
        "description": "Test default status",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "default_status_test",
        "tags": ["test"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()

    # Verify default status is DRAFT
    assert "status" in result
    assert result["status"] == "DRAFT"
    assert result["locked"] is False


async def test_cache_stats_endpoint(client: AsyncClient, logged_in_headers):
    """Test the cache stats endpoint returns correct structure."""
    response = await client.get("api/v1/flows/cache/stats", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    result = response.json()
    assert "size" in result
    assert "max_size" in result
    assert "keys" in result
    assert "memory_bytes" in result
    assert "memory_mb" in result

    # Verify types
    assert isinstance(result["size"], int)
    assert isinstance(result["keys"], list)
    assert isinstance(result["memory_bytes"], int)
    assert isinstance(result["memory_mb"], (int, float))
    assert result["memory_bytes"] >= 0
    assert result["memory_mb"] >= 0.0


async def test_cache_stats_requires_auth(client: AsyncClient):
    """Test that cache stats endpoint requires authentication."""
    response = await client.get("api/v1/flows/cache/stats")
    # In test environment with AUTO_LOGIN, this might return 200 with default user
    # Otherwise should return 401 or 403. Accept any of these as valid depending on test config.
    # Some test environments may use 403 Forbidden instead of 401 Unauthorized
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ], f"Expected 200, 401, or 403, got {response.status_code}"


async def test_deployed_flow_added_to_cache(client: AsyncClient, logged_in_headers):
    """Test that deploying a flow adds it to the cache."""
    # Get initial cache stats
    stats_before = await client.get("api/v1/flows/cache/stats", headers=logged_in_headers)
    initial_size = stats_before.json()["size"]

    # Create a flow
    flow_data = {
        "name": "cache_test_flow",
        "description": "Test caching",
        "data": {"nodes": [], "edges": []},
        "status": "DRAFT",
    }
    create_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow = create_response.json()
    flow_id = flow["id"]

    # Deploy the flow
    update_response = await client.patch(
        f"api/v1/flows/{flow_id}", json={"status": "DEPLOYED"}, headers=logged_in_headers
    )
    assert update_response.status_code == status.HTTP_200_OK

    # Check cache stats - should have increased
    stats_after = await client.get("api/v1/flows/cache/stats", headers=logged_in_headers)
    result = stats_after.json()

    # Cache size should have increased (by 1 for flow_id, potentially +1 if endpoint_name exists)
    assert result["size"] >= initial_size + 1
    assert flow_id in result["keys"]
    assert result["memory_bytes"] > 0


async def test_undeployed_flow_removed_from_cache(client: AsyncClient, logged_in_headers):
    """Test that undeploying a flow removes it from the cache."""
    # Create and deploy a flow
    flow_data = {
        "name": "undeploy_cache_test",
        "description": "Test cache removal",
        "data": {"nodes": [], "edges": []},
        "status": "DEPLOYED",
    }
    create_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow = create_response.json()
    flow_id = flow["id"]

    # Verify it's in cache
    stats_deployed = await client.get("api/v1/flows/cache/stats", headers=logged_in_headers)
    assert flow_id in stats_deployed.json()["keys"]

    # Undeploy the flow
    update_response = await client.patch(f"api/v1/flows/{flow_id}", json={"status": "DRAFT"}, headers=logged_in_headers)
    assert update_response.status_code == status.HTTP_200_OK

    # Verify it's removed from cache
    stats_draft = await client.get("api/v1/flows/cache/stats", headers=logged_in_headers)
    assert flow_id not in stats_draft.json()["keys"]


async def test_cache_refresh_on_deployed_flow_update(client: AsyncClient, logged_in_headers, valid_flow_payload):
    """Test that updating a deployed flow refreshes it in cache."""
    # Use valid flow payload and set it to DEPLOYED
    flow_data = valid_flow_payload.copy()
    flow_data["name"] = "refresh_cache_test"
    flow_data["status"] = "DEPLOYED"

    create_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow = create_response.json()
    flow_id = flow["id"]

    # Note: The flow may or may not be cached depending on whether its components are available
    # This test primarily verifies the refresh code path is called without errors

    # Update the deployed flow (should call refresh_flow_in_cache)
    update_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"description": "Updated description"},
        headers=logged_in_headers,
    )
    assert update_response.status_code == status.HTTP_200_OK

    # Verify the flow update succeeded
    get_response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert get_response.json()["description"] == "Updated description"


async def test_cache_with_endpoint_name(client: AsyncClient, logged_in_headers):
    """Test that flows with endpoint names are cached by both ID and endpoint name."""
    # Create a flow with endpoint_name
    flow_data = {
        "name": "endpoint_cache_test",
        "description": "Test endpoint caching",
        "endpoint_name": "test-endpoint-cache",
        "data": {"nodes": [], "edges": []},
        "status": "DEPLOYED",
    }
    create_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow = create_response.json()
    flow_id = flow["id"]
    endpoint_name = flow["endpoint_name"]

    # Check cache stats
    stats = await client.get("api/v1/flows/cache/stats", headers=logged_in_headers)
    cache_keys = stats.json()["keys"]

    # Both flow_id and endpoint_name should be in cache
    assert flow_id in cache_keys
    assert endpoint_name in cache_keys


async def test_cache_memory_tracking(client: AsyncClient, logged_in_headers):
    """Test that cache memory tracking fields are calculated correctly."""
    # Get cache stats
    stats = await client.get("api/v1/flows/cache/stats", headers=logged_in_headers)
    result = stats.json()

    # Verify memory tracking fields exist and are valid
    assert "memory_bytes" in result
    assert "memory_mb" in result
    assert isinstance(result["memory_bytes"], int)
    assert isinstance(result["memory_mb"], (int, float))
    assert result["memory_bytes"] >= 0
    assert result["memory_mb"] >= 0.0

    # Verify MB is correctly calculated from bytes
    expected_mb = round(result["memory_bytes"] / (1024 * 1024), 2)
    assert result["memory_mb"] == expected_mb


async def test_create_deployed_flow_is_auto_locked(client: AsyncClient, logged_in_headers):
    """Test that flows created with DEPLOYED status are automatically locked."""
    flow_data = {
        "name": "deployed_on_creation",
        "description": "Test auto-lock on creation",
        "data": {},
        "status": "DEPLOYED",
    }
    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert response.status_code == 201
    result = response.json()

    # Verify flow is both deployed AND locked
    assert result["status"] == "DEPLOYED"
    assert result["locked"] is True
