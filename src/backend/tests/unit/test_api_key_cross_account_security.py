"""Test for API Key Cross-Account Security Issue #10202.

This test reproduces the security vulnerability where an API key from one account
can be used to execute flows from another account.
"""

import pytest
from httpx import AsyncClient
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key import ApiKeyCreate
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_db_service
from sqlmodel import select


@pytest.fixture
async def second_user(client):  # noqa: ARG001
    """Create a second user for cross-account testing."""
    db_manager = get_db_service()
    async with db_manager.with_session() as session:
        user = User(
            username="seconduser",
            password=get_password_hash("testpassword2"),
            is_active=True,
            is_superuser=False,
        )
        stmt = select(User).where(User.username == user.username)
        if existing_user := (await session.exec(stmt)).first():
            user = existing_user
        else:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        user = UserRead.model_validate(user, from_attributes=True)
    yield user
    # Clean up
    try:
        async with db_manager.with_session() as session:
            user_to_delete = await session.get(User, user.id)
            if user_to_delete:
                await session.delete(user_to_delete)
                await session.commit()
    except Exception:  # noqa: S110
        pass  # Cleanup failures are not critical for tests


@pytest.fixture
async def second_user_logged_in_headers(client, second_user):
    """Get authentication headers for second user."""
    login_data = {"username": second_user.username, "password": "testpassword2"}  # pragma: allowlist secret
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}


@pytest.fixture
async def first_user_api_key(client: AsyncClient, logged_in_headers, active_user):  # noqa: ARG001
    """Create an API key for the first user."""
    api_key_data = ApiKeyCreate(name="first-user-api-key")
    response = await client.post(
        "api/v1/api_key/",
        json=api_key_data.model_dump(mode="json"),
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["api_key"]  # Return the unmasked API key  # pragma: allowlist secret


@pytest.fixture
async def second_user_flow(client: AsyncClient, second_user_logged_in_headers, second_user):  # noqa: ARG001
    """Create a flow owned by the second user."""
    # Create a simple flow
    flow_data = {
        "name": "Second User Flow",
        "description": "A flow belonging to the second user",
        "data": {"nodes": [], "edges": []},
    }

    response = await client.post("api/v1/flows/", json=flow_data, headers=second_user_logged_in_headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.api_key_required
async def test_cross_account_api_key_should_not_run_flow(
    client: AsyncClient,
    first_user_api_key: str,
    second_user_flow: dict,
    active_user,
    second_user,
):
    """Test that reproduces the security vulnerability.

    - User 1 creates an API key
    - User 2 creates a flow
    - User 1's API key should NOT be able to execute User 2's flow.

    EXPECTED BEHAVIOR: This should fail with a 403 or 404 error
    CURRENT BEHAVIOR: This succeeds (security vulnerability)
    """
    # Get the flow ID from second user
    flow_id = second_user_flow["id"]

    # Try to run second user's flow with first user's API key
    headers = {"x-api-key": first_user_api_key}
    payload = {
        "input_value": "test message",
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": {},
        "stream": False,
    }

    response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)

    # This SHOULD fail with 403 (Forbidden) or 404 (Not Found)
    # But currently it will succeed (status 200), which is the security issue
    assert response.status_code in [403, 404], (
        f"Security Issue: User 1's API key was able to execute User 2's flow! "
        f"Expected 403 or 404, got {response.status_code}. "
        f"User 1 ID: {active_user.id}, User 2 ID: {second_user.id}, Flow ID: {flow_id}"
    )


@pytest.mark.api_key_required
async def test_same_account_api_key_should_run_own_flow(
    client: AsyncClient,
    first_user_api_key: str,
    starter_project: dict,
):
    """Test that a user's API key CAN execute their own flows (legitimate use case).

    This should continue to work after the security fix.
    """
    # Get the flow ID from the first user's starter project
    flow_id = starter_project["id"]

    # Try to run first user's flow with first user's API key
    headers = {"x-api-key": first_user_api_key}
    payload = {
        "input_value": "test message",
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": {},
        "stream": False,
    }

    response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)

    # This SHOULD succeed
    assert response.status_code == 200, (
        f"Legitimate use case failed: User should be able to run their own flow with their API key. "
        f"Got status {response.status_code}"
    )


@pytest.mark.api_key_required
async def test_cross_account_get_flow_should_not_work(
    client: AsyncClient,
    first_user_api_key: str,
    second_user_flow: dict,
):
    """Test that a user cannot retrieve another user's flow details using their API key."""
    flow_id = second_user_flow["id"]
    headers = {"x-api-key": first_user_api_key}

    response = await client.get(f"/api/v1/flows/{flow_id}", headers=headers)

    # This should fail with 403 or 404
    assert response.status_code in [403, 404], (
        f"Security Issue: User 1's API key was able to retrieve User 2's flow details! "
        f"Expected 403 or 404, got {response.status_code}"
    )
