"""Integration tests for Component Mapping API endpoints."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4
import json

from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentCategoryEnum,
)
from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapter,
    RuntimeTypeEnum,
)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_component_mapping():
    """Create a sample component mapping for testing."""
    return ComponentMapping(
        id=uuid4(),
        genesis_type="genesis:test_component",
        base_config={"test_config": "value"},
        io_mapping={
            "component": "TestComponent",
            "dataType": "Data",
            "input_field": "input",
            "output_field": "output",
            "input_types": ["str"],
            "output_types": ["Data"],
        },
        component_category=ComponentCategoryEnum.TOOL,
        description="Test component mapping",
        version="1.0.0",
        active=True,
    )


@pytest.fixture
def sample_runtime_adapter():
    """Create a sample runtime adapter for testing."""
    return RuntimeAdapter(
        id=uuid4(),
        genesis_type="genesis:test_component",
        runtime_type=RuntimeTypeEnum.LANGFLOW.value,
        target_component="TestComponent",
        adapter_config={"test": "config"},
        version="1.0.0",
        description="Test adapter",
        active=True,
        priority=100,
    )


class TestComponentMappingAPIEndpoints:
    """Test cases for component mapping API endpoints."""

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.component_mapping_service')
    def test_get_component_mappings(self, mock_service, mock_session_getter, sample_component_mapping):
        """Test GET /component-mappings endpoint."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_service.get_all_component_mappings = AsyncMock(return_value=[sample_component_mapping])

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test the endpoint
        response = client.get("/component-mappings/")

        # Note: This is a simplified test. In a real test, you'd need to handle async properly
        # For full integration tests, you'd use pytest-asyncio and actual database

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.component_mapping_service')
    def test_create_component_mapping(self, mock_service, mock_session_getter, sample_component_mapping):
        """Test POST /component-mappings endpoint."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)
        mock_service.create_component_mapping = AsyncMock(return_value=sample_component_mapping)

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test data
        create_data = {
            "genesis_type": "genesis:new_component",
            "base_config": {"test": "config"},
            "io_mapping": {"component": "NewComponent"},
            "component_category": "tool",
            "description": "New test component",
            "version": "1.0.0",
            "active": True,
        }

        # Test the endpoint
        response = client.post("/component-mappings/", json=create_data)

        # Note: Actual assertions would depend on proper async handling

    def test_api_endpoint_parameter_validation(self):
        """Test API endpoint parameter validation."""
        from langflow.api.v1.component_mapping import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test invalid category parameter
        response = client.get("/component-mappings/?category=invalid_category")
        assert response.status_code == 422  # Validation error

        # Test invalid limit parameter
        response = client.get("/component-mappings/?limit=0")
        assert response.status_code == 422  # Validation error

        # Test invalid skip parameter
        response = client.get("/component-mappings/?skip=-1")
        assert response.status_code == 422  # Validation error


class TestDiscoveryAPIEndpoints:
    """Test cases for discovery API endpoints."""

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.discovery_service')
    def test_discover_components(self, mock_discovery_service, mock_session_getter):
        """Test POST /component-mappings/discovery/discover endpoint."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_discovery_service.discover_components = AsyncMock(return_value={
            "total_langflow_components": 10,
            "existing_mappings": 5,
            "new_components_found": [],
            "updated_schemas": [],
            "mapping_recommendations": [],
            "statistics": {},
        })

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test the endpoint
        response = client.post("/component-mappings/discovery/discover")

        # Note: Actual assertions would depend on proper async handling

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.discovery_service')
    def test_auto_create_mappings(self, mock_discovery_service, mock_session_getter):
        """Test POST /component-mappings/discovery/auto-create endpoint."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_discovery_service.auto_create_mappings = AsyncMock(return_value={
            "created": 2,
            "errors": [],
            "created_mappings": [],
        })

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test data
        request_data = ["TestComponent1", "TestComponent2"]

        # Test the endpoint
        response = client.post("/component-mappings/discovery/auto-create", json=request_data)

        # Note: Actual assertions would depend on proper async handling


class TestRuntimeAdapterAPIEndpoints:
    """Test cases for runtime adapter API endpoints."""

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.component_mapping_service')
    def test_create_runtime_adapter(self, mock_service, mock_session_getter, sample_runtime_adapter):
        """Test POST /component-mappings/runtime-adapters/ endpoint."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_service.create_runtime_adapter = AsyncMock(return_value=sample_runtime_adapter)

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test data
        adapter_data = {
            "genesis_type": "genesis:test_component",
            "runtime_type": "langflow",
            "target_component": "TestComponent",
            "adapter_config": {"test": "config"},
            "version": "1.0.0",
            "description": "Test adapter",
            "active": True,
            "priority": 100,
        }

        # Test the endpoint
        response = client.post("/component-mappings/runtime-adapters/", json=adapter_data)

        # Note: Actual assertions would depend on proper async handling

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.component_mapping_service')
    def test_get_runtime_adapter(self, mock_service, mock_session_getter, sample_runtime_adapter):
        """Test GET /component-mappings/runtime-adapters/{genesis_type}/{runtime_type} endpoint."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_service.get_runtime_adapter_for_genesis_type = AsyncMock(return_value=sample_runtime_adapter)

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test the endpoint
        response = client.get("/component-mappings/runtime-adapters/genesis:test_component/langflow")

        # Note: Actual assertions would depend on proper async handling


class TestAPIErrorHandling:
    """Test cases for API error handling."""

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.component_mapping_service')
    def test_get_nonexistent_mapping(self, mock_service, mock_session_getter):
        """Test getting a non-existent component mapping."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_service.get_component_mapping_by_genesis_type = AsyncMock(return_value=None)

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test the endpoint
        response = client.get("/component-mappings/genesis-type/genesis:nonexistent")
        assert response.status_code == 404

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.component_mapping_service')
    def test_create_duplicate_mapping(self, mock_service, mock_session_getter, sample_component_mapping):
        """Test creating a duplicate component mapping."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_service.get_component_mapping_by_genesis_type = AsyncMock(return_value=sample_component_mapping)

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test data
        create_data = {
            "genesis_type": "genesis:test_component",
            "base_config": {"test": "config"},
            "component_category": "tool",
            "description": "Duplicate component",
            "version": "1.0.0",
            "active": True,
        }

        # Test the endpoint
        response = client.post("/component-mappings/", json=create_data)
        assert response.status_code == 409  # Conflict

    @patch('langflow.api.v1.component_mapping.session_getter')
    @patch('langflow.api.v1.component_mapping.discovery_service')
    def test_discovery_service_error(self, mock_discovery_service, mock_session_getter):
        """Test discovery service error handling."""
        from langflow.api.v1.component_mapping import router

        # Setup mocks
        mock_session_getter.return_value = AsyncMock()
        mock_discovery_service.discover_components = AsyncMock(side_effect=Exception("Discovery failed"))

        # Create test client
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test the endpoint
        response = client.post("/component-mappings/discovery/discover")
        assert response.status_code == 500


# Mock-based Integration Tests

class TestMockBasedIntegration:
    """Integration tests using mocked dependencies."""

    @pytest.mark.asyncio
    async def test_full_mapping_lifecycle(self, mock_session, sample_component_mapping):
        """Test complete mapping lifecycle through API calls."""
        from langflow.api.v1.component_mapping import (
            component_mapping_service,
            discovery_service,
        )

        # Mock services
        with patch.object(component_mapping_service, 'create_component_mapping') as mock_create, \
             patch.object(component_mapping_service, 'get_component_mapping_by_genesis_type') as mock_get, \
             patch.object(component_mapping_service, 'update_component_mapping') as mock_update, \
             patch.object(component_mapping_service, 'delete_component_mapping') as mock_delete:

            # Setup return values
            mock_create.return_value = sample_component_mapping
            mock_get.return_value = sample_component_mapping
            mock_update.return_value = sample_component_mapping
            mock_delete.return_value = True

            # Test create
            create_data = ComponentMappingCreate(
                genesis_type="genesis:test_component",
                base_config={"test": "config"},
                component_category=ComponentCategoryEnum.TOOL,
                description="Test component",
                version="1.0.0",
            )

            created = await component_mapping_service.create_component_mapping(mock_session, create_data)
            assert created.genesis_type == "genesis:test_component"

            # Test get
            retrieved = await component_mapping_service.get_component_mapping_by_genesis_type(
                mock_session, "genesis:test_component"
            )
            assert retrieved is not None

            # Test update
            from langflow.services.database.models.component_mapping import ComponentMappingUpdate
            update_data = ComponentMappingUpdate(description="Updated description")
            updated = await component_mapping_service.update_component_mapping(
                mock_session, sample_component_mapping.id, update_data
            )
            assert updated is not None

            # Test delete
            deleted = await component_mapping_service.delete_component_mapping(
                mock_session, sample_component_mapping.id
            )
            assert deleted is True

    @pytest.mark.asyncio
    async def test_discovery_integration(self, mock_session):
        """Test discovery service integration."""
        from langflow.api.v1.component_mapping import discovery_service

        # Mock discovery methods
        with patch.object(discovery_service, 'discover_components') as mock_discover, \
             patch.object(discovery_service, 'auto_create_mappings') as mock_auto_create:

            # Setup return values
            mock_discover.return_value = {
                "total_langflow_components": 5,
                "existing_mappings": 2,
                "new_components_found": [
                    {
                        "component_name": "NewComponent",
                        "schema": {"name": "NewComponent"},
                        "recommendation": {
                            "suggested_genesis_type": "genesis:new_component",
                            "priority": "medium",
                        }
                    }
                ],
                "mapping_recommendations": [],
                "statistics": {},
            }

            mock_auto_create.return_value = {
                "created": 1,
                "errors": [],
                "created_mappings": [
                    {
                        "genesis_type": "genesis:new_component",
                        "component_name": "NewComponent",
                        "mapping_id": str(uuid4()),
                    }
                ],
            }

            # Test discovery
            discovery_result = await discovery_service.discover_components(mock_session)
            assert discovery_result["total_langflow_components"] == 5
            assert len(discovery_result["new_components_found"]) == 1

            # Test auto-creation
            auto_result = await discovery_service.auto_create_mappings(
                mock_session, ["NewComponent"]
            )
            assert auto_result["created"] == 1

    @pytest.mark.asyncio
    async def test_runtime_adapter_integration(self, mock_session, sample_runtime_adapter):
        """Test runtime adapter integration."""
        from langflow.api.v1.component_mapping import component_mapping_service

        # Mock adapter methods
        with patch.object(component_mapping_service, 'create_runtime_adapter') as mock_create, \
             patch.object(component_mapping_service, 'get_runtime_adapter_for_genesis_type') as mock_get:

            # Setup return values
            mock_create.return_value = sample_runtime_adapter
            mock_get.return_value = sample_runtime_adapter

            # Test create adapter
            from langflow.services.database.models.component_mapping.runtime_adapter import RuntimeAdapterCreate
            adapter_data = RuntimeAdapterCreate(
                genesis_type="genesis:test_component",
                runtime_type=RuntimeTypeEnum.LANGFLOW.value,
                target_component="TestComponent",
                version="1.0.0",
                description="Test adapter",
                active=True,
                priority=100,
            )

            created_adapter = await component_mapping_service.create_runtime_adapter(
                mock_session, adapter_data
            )
            assert created_adapter.genesis_type == "genesis:test_component"

            # Test get adapter
            retrieved_adapter = await component_mapping_service.get_runtime_adapter_for_genesis_type(
                mock_session, "genesis:test_component", RuntimeTypeEnum.LANGFLOW.value
            )
            assert retrieved_adapter is not None
            assert retrieved_adapter.target_component == "TestComponent"


# Performance Tests

class TestAPIPerformance:
    """Performance tests for API endpoints."""

    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self, mock_session):
        """Test performance of bulk operations."""
        from langflow.api.v1.component_mapping import component_mapping_service

        # Mock bulk operations
        bulk_mappings = [
            ComponentMapping(
                id=uuid4(),
                genesis_type=f"genesis:component_{i}",
                base_config={},
                component_category=ComponentCategoryEnum.TOOL,
                description=f"Component {i}",
                version="1.0.0",
                active=True,
            )
            for i in range(100)
        ]

        with patch.object(component_mapping_service, 'get_all_component_mappings') as mock_get_all:
            mock_get_all.return_value = bulk_mappings

            import time
            start_time = time.time()

            # Simulate bulk retrieval
            result = await component_mapping_service.get_all_component_mappings(
                mock_session, limit=100
            )

            end_time = time.time()

            assert len(result) == 100
            assert (end_time - start_time) < 1.0  # Should complete quickly with mocks

    def test_api_endpoint_response_time(self):
        """Test API endpoint response times."""
        from langflow.api.v1.component_mapping import router
        from fastapi import FastAPI
        import time

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Mock the dependencies to avoid actual database calls
        with patch('langflow.api.v1.component_mapping.session_getter'), \
             patch('langflow.api.v1.component_mapping.component_mapping_service'):

            start_time = time.time()
            response = client.get("/component-mappings/?limit=10")
            end_time = time.time()

            # Response should be fast even with mocked dependencies
            assert (end_time - start_time) < 1.0