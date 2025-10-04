import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.api.v1.schemas import (
    BulkOperationResponse,
    ConversionResultResponse,
    FlowWithSpecification,
    SpecificationSummary,
)


@pytest.fixture
def sample_flow_data():
    """Sample flow data for testing."""
    return {
        "name": "Test Flow",
        "description": "A test flow for specification testing",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {
            "nodes": [
                {
                    "id": "node1",
                    "type": "ChatInput",
                    "data": {"input_value": "Hello"}
                }
            ],
            "edges": []
        },
        "is_component": False,
        "webhook": False,
        "endpoint_name": "test_flow_endpoint",
        "tags": ["test"],
        "folder_id": None,
    }


@pytest.fixture
def sample_specification_data():
    """Sample specification data for testing."""
    return {
        "id": "urn:agent:genesis:test_agent:1",
        "name": "Test Agent",
        "description": "A test agent specification",
        "version": "1.0.0",
        "domain": "healthcare",
        "subdomain": "diagnostics",
        "owner": "test@example.com",
        "goal": "Test agent goal",
        "kind": "Single Agent",
        "target_user": "internal",
        "value_generation": "ProcessAutomation",
        "interaction_mode": "RequestResponse",
        "run_mode": "RealTime",
        "agency_level": "StaticWorkflow",
        "uses_tools": True,
        "learning_capability": "None",
        "components": [],
        "tags": ["test", "healthcare"],
        "status": "ACTIVE"
    }


@pytest.mark.asyncio
async def test_get_flow_specification_not_found(client: AsyncClient, logged_in_headers):
    """Test getting specification for a flow that doesn't exist."""
    flow_id = str(uuid.uuid4())
    response = await client.get(f"api/v1/flows/{flow_id}/specification", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_flow_specification_no_spec(client: AsyncClient, logged_in_headers, sample_flow_data):
    """Test getting specification for a flow that has no specification."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    try:
        # Try to get specification
        response = await client.get(f"api/v1/flows/{flow_id}/specification", headers=logged_in_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "No specification found" in response.json()["detail"]
    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.asyncio
@patch('langflow.services.specification.service.SpecificationStorageService')
async def test_get_flow_specification_success(
    mock_storage_service, client: AsyncClient, logged_in_headers, sample_flow_data, sample_specification_data
):
    """Test successfully getting specification for a flow."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    # Mock the specification service
    mock_service_instance = AsyncMock()
    mock_service_instance.get_specification_by_flow_id.return_value = sample_specification_data
    mock_storage_service.return_value = mock_service_instance

    try:
        # Get specification
        response = await client.get(f"api/v1/flows/{flow_id}/specification", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK

        result = response.json()
        assert result["name"] == sample_specification_data["name"]
        assert result["domain"] == sample_specification_data["domain"]

        # Verify service was called
        mock_service_instance.get_specification_by_flow_id.assert_called_once_with(uuid.UUID(flow_id))
    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.asyncio
@patch('langflow.services.specification.service.FlowSpecificationConverter')
@patch('langflow.services.specification.service.SpecificationStorageService')
async def test_create_specification_from_flow_success(
    mock_storage_service, mock_converter, client: AsyncClient, logged_in_headers, sample_flow_data, sample_specification_data
):
    """Test successfully creating a specification from a flow."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    # Mock the converter
    mock_converter_instance = AsyncMock()
    mock_conversion_result = MagicMock()
    mock_conversion_result.success = True
    mock_conversion_result.specification = MagicMock()
    mock_conversion_result.specification.model_dump.return_value = sample_specification_data
    mock_conversion_result.warnings = []
    mock_conversion_result.errors = []
    mock_converter_instance.convert_flow_to_specification.return_value = mock_conversion_result
    mock_converter.return_value = mock_converter_instance

    # Mock the storage service
    mock_service_instance = AsyncMock()
    mock_service_instance.store_specification.return_value = str(uuid.uuid4())
    mock_storage_service.return_value = mock_service_instance

    try:
        # Create specification
        response = await client.post(f"api/v1/flows/{flow_id}/specification", headers=logged_in_headers)
        assert response.status_code == status.HTTP_201_CREATED

        result = response.json()
        assert result["success"] is True
        assert "specification_id" in result
        assert result["specification"]["name"] == sample_specification_data["name"]

        # Verify services were called
        mock_converter_instance.convert_flow_to_specification.assert_called_once()
        mock_service_instance.store_specification.assert_called_once()
    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.asyncio
@patch('langflow.services.specification.service.FlowSpecificationConverter')
async def test_create_specification_from_flow_conversion_failure(
    mock_converter, client: AsyncClient, logged_in_headers, sample_flow_data
):
    """Test creating specification when conversion fails."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    # Mock the converter to return failure
    mock_converter_instance = AsyncMock()
    mock_conversion_result = MagicMock()
    mock_conversion_result.success = False
    mock_conversion_result.errors = ["Conversion failed due to invalid flow structure"]
    mock_conversion_result.warnings = ["Some components could not be mapped"]
    mock_converter_instance.convert_flow_to_specification.return_value = mock_conversion_result
    mock_converter.return_value = mock_converter_instance

    try:
        # Try to create specification
        response = await client.post(f"api/v1/flows/{flow_id}/specification", headers=logged_in_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        result = response.json()
        assert "Failed to convert flow to specification" in result["detail"]
    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.asyncio
@patch('langflow.services.specification.service.SpecificationStorageService')
async def test_create_specification_with_metadata_override(
    mock_storage_service, client: AsyncClient, logged_in_headers, sample_flow_data, sample_specification_data
):
    """Test creating specification with metadata override."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    # Mock services
    with patch('langflow.services.specification.service.FlowSpecificationConverter') as mock_converter:
        mock_converter_instance = AsyncMock()
        mock_conversion_result = MagicMock()
        mock_conversion_result.success = True
        mock_conversion_result.specification = MagicMock()
        mock_conversion_result.specification.model_dump.return_value = sample_specification_data.copy()
        mock_conversion_result.warnings = []
        mock_conversion_result.errors = []
        mock_converter_instance.convert_flow_to_specification.return_value = mock_conversion_result
        mock_converter.return_value = mock_converter_instance

        mock_service_instance = AsyncMock()
        mock_service_instance.store_specification.return_value = str(uuid.uuid4())
        mock_storage_service.return_value = mock_service_instance

        # Override metadata
        spec_override = {
            "domain": "finance",
            "description": "Custom description for finance domain"
        }

        try:
            # Create specification with override
            response = await client.post(
                f"api/v1/flows/{flow_id}/specification",
                headers=logged_in_headers,
                json=spec_override
            )
            assert response.status_code == status.HTTP_201_CREATED

            result = response.json()
            assert result["success"] is True
            # The actual verification of the override would happen in the service layer
        finally:
            # Clean up
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.asyncio
@patch('langflow.services.specification.service.SpecificationStorageService')
async def test_update_flow_specification_link(
    mock_storage_service, client: AsyncClient, logged_in_headers, sample_flow_data
):
    """Test updating the specification link for a flow."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    # Mock the storage service
    mock_service_instance = AsyncMock()
    mock_service_instance.link_flow_to_specification.return_value = True
    mock_storage_service.return_value = mock_service_instance

    specification_id = str(uuid.uuid4())

    try:
        # Update specification link
        response = await client.put(
            f"api/v1/flows/{flow_id}/specification",
            headers=logged_in_headers,
            json={"specification_id": specification_id}
        )
        assert response.status_code == status.HTTP_200_OK

        result = response.json()
        assert result["message"] == "Flow-specification link updated successfully"

        # Verify service was called
        mock_service_instance.link_flow_to_specification.assert_called_once_with(
            uuid.UUID(flow_id), uuid.UUID(specification_id)
        )
    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.asyncio
@patch('langflow.services.specification.service.SpecificationStorageService')
async def test_remove_flow_specification_link_only(
    mock_storage_service, client: AsyncClient, logged_in_headers, sample_flow_data
):
    """Test removing only the specification link from a flow (keeping specification)."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    # Mock the storage service
    mock_service_instance = AsyncMock()
    mock_service_instance.unlink_flow_from_specification.return_value = True
    mock_storage_service.return_value = mock_service_instance

    try:
        # Remove specification link (but keep specification)
        response = await client.delete(
            f"api/v1/flows/{flow_id}/specification",
            headers=logged_in_headers,
            params={"delete_specification": False}
        )
        assert response.status_code == status.HTTP_200_OK

        result = response.json()
        assert result["message"] == "Flow-specification link removed successfully"
        assert result["specification_deleted"] is False

        # Verify service was called
        mock_service_instance.unlink_flow_from_specification.assert_called_once_with(uuid.UUID(flow_id))
    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.asyncio
@patch('langflow.services.specification.service.SpecificationStorageService')
async def test_remove_flow_specification_link_and_delete(
    mock_storage_service, client: AsyncClient, logged_in_headers, sample_flow_data
):
    """Test removing specification link and deleting the specification."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    # Mock the storage service
    mock_service_instance = AsyncMock()
    mock_service_instance.get_specification_by_flow_id.return_value = {"id": str(uuid.uuid4())}
    mock_service_instance.unlink_flow_from_specification.return_value = True
    mock_service_instance.delete_specification.return_value = True
    mock_storage_service.return_value = mock_service_instance

    try:
        # Remove specification link and delete specification
        response = await client.delete(
            f"api/v1/flows/{flow_id}/specification",
            headers=logged_in_headers,
            params={"delete_specification": True}
        )
        assert response.status_code == status.HTTP_200_OK

        result = response.json()
        assert result["message"] == "Flow-specification link removed and specification deleted successfully"
        assert result["specification_deleted"] is True

        # Verify services were called
        mock_service_instance.get_specification_by_flow_id.assert_called_once_with(uuid.UUID(flow_id))
        mock_service_instance.unlink_flow_from_specification.assert_called_once_with(uuid.UUID(flow_id))
        mock_service_instance.delete_specification.assert_called_once()
    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.asyncio
async def test_flow_specification_endpoints_unauthorized(client: AsyncClient, sample_flow_data):
    """Test that all specification endpoints require authentication."""
    # Create a flow without auth headers first (this should fail too)
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data)
    assert flow_response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    flow_id = str(uuid.uuid4())

    # Test all specification endpoints without auth
    endpoints = [
        ("GET", f"api/v1/flows/{flow_id}/specification"),
        ("POST", f"api/v1/flows/{flow_id}/specification"),
        ("PUT", f"api/v1/flows/{flow_id}/specification"),
        ("DELETE", f"api/v1/flows/{flow_id}/specification"),
    ]

    for method, endpoint in endpoints:
        if method == "GET":
            response = await client.get(endpoint)
        elif method == "POST":
            response = await client.post(endpoint)
        elif method == "PUT":
            response = await client.put(endpoint, json={"specification_id": str(uuid.uuid4())})
        elif method == "DELETE":
            response = await client.delete(endpoint)

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.asyncio
async def test_specification_endpoints_invalid_flow_id(client: AsyncClient, logged_in_headers):
    """Test specification endpoints with invalid flow IDs."""
    invalid_flow_id = "invalid-uuid"

    endpoints = [
        ("GET", f"api/v1/flows/{invalid_flow_id}/specification"),
        ("POST", f"api/v1/flows/{invalid_flow_id}/specification"),
        ("PUT", f"api/v1/flows/{invalid_flow_id}/specification"),
        ("DELETE", f"api/v1/flows/{invalid_flow_id}/specification"),
    ]

    for method, endpoint in endpoints:
        if method == "GET":
            response = await client.get(endpoint, headers=logged_in_headers)
        elif method == "POST":
            response = await client.post(endpoint, headers=logged_in_headers)
        elif method == "PUT":
            response = await client.put(
                endpoint,
                json={"specification_id": str(uuid.uuid4())},
                headers=logged_in_headers
            )
        elif method == "DELETE":
            response = await client.delete(endpoint, headers=logged_in_headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_specification_endpoints_user_isolation(
    client: AsyncClient, logged_in_headers, sample_flow_data
):
    """Test that users can only access their own flow specifications."""
    from uuid import uuid4
    from langflow.services.auth.utils import get_password_hash
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope

    # Create a second user
    other_user_id = uuid4()
    async with session_scope() as session:
        other_user = User(
            id=other_user_id,
            username="other_spec_test_user",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

    # Login as the other user
    login_data = {"username": "other_spec_test_user", "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    other_user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create a flow with the other user
    other_flow_data = sample_flow_data.copy()
    other_flow_data["name"] = "Other User Flow"
    other_flow_data["endpoint_name"] = "other_user_flow_endpoint"

    flow_response = await client.post(
        "api/v1/flows/",
        json=other_flow_data,
        headers=other_user_headers
    )
    assert flow_response.status_code == status.HTTP_201_CREATED
    other_flow_id = flow_response.json()["id"]

    try:
        # Try to access other user's flow specification with first user's headers
        response = await client.get(
            f"api/v1/flows/{other_flow_id}/specification",
            headers=logged_in_headers
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Try to create specification for other user's flow
        response = await client.post(
            f"api/v1/flows/{other_flow_id}/specification",
            headers=logged_in_headers
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{other_flow_id}", headers=other_user_headers)

        # Delete the other user
        async with session_scope() as session:
            user = await session.get(User, other_user_id)
            if user:
                await session.delete(user)
                await session.commit()


@pytest.mark.asyncio
async def test_specification_error_handling(client: AsyncClient, logged_in_headers, sample_flow_data):
    """Test error handling in specification endpoints."""
    # Create a flow first
    flow_response = await client.post("api/v1/flows/", json=sample_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    try:
        # Test with various service failures
        with patch('langflow.services.specification.service.SpecificationStorageService') as mock_storage:
            # Mock service to raise exception
            mock_service_instance = AsyncMock()
            mock_service_instance.get_specification_by_flow_id.side_effect = Exception("Database error")
            mock_storage.return_value = mock_service_instance

            response = await client.get(f"api/v1/flows/{flow_id}/specification", headers=logged_in_headers)
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to get flow specification" in response.json()["detail"]

    finally:
        # Clean up
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)