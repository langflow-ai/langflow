import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.api.v1.schemas import (
    BulkOperationResponse,
    SpecificationExportResponse,
    SpecificationImportResponse,
    SpecificationTemplateResponse,
)


@pytest.fixture
def sample_specifications_data():
    """Sample specifications data for bulk operations."""
    return [
        {
            "id": "urn:agent:genesis:healthcare_agent:1",
            "name": "Healthcare Diagnostic Agent",
            "description": "Agent for healthcare diagnostics",
            "version": "1.0.0",
            "domain": "healthcare",
            "subdomain": "diagnostics",
            "owner": "healthcare@example.com",
            "goal": "Assist in medical diagnostics",
            "kind": "Single Agent",
            "target_user": "internal",
            "value_generation": "ProcessAutomation",
            "interaction_mode": "RequestResponse",
            "run_mode": "RealTime",
            "agency_level": "StaticWorkflow",
            "uses_tools": True,
            "learning_capability": "None",
            "components": [],
            "tags": ["healthcare", "diagnostics"],
            "status": "ACTIVE"
        },
        {
            "id": "urn:agent:genesis:finance_agent:1",
            "name": "Finance Analysis Agent",
            "description": "Agent for financial analysis",
            "version": "1.0.0",
            "domain": "finance",
            "subdomain": "analysis",
            "owner": "finance@example.com",
            "goal": "Perform financial analysis",
            "kind": "Single Agent",
            "target_user": "internal",
            "value_generation": "InsightGeneration",
            "interaction_mode": "RequestResponse",
            "run_mode": "RealTime",
            "agency_level": "StaticWorkflow",
            "uses_tools": True,
            "learning_capability": "None",
            "components": [],
            "tags": ["finance", "analysis"],
            "status": "ACTIVE"
        }
    ]


class TestBulkCreateSpecifications:
    """Test bulk create specifications endpoint."""

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_bulk_create_specifications_success(
        self, mock_storage_service, client: AsyncClient, logged_in_headers, sample_specifications_data
    ):
        """Test successful bulk creation of specifications."""
        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_create_specifications.return_value = BulkOperationResponse(
            successful=[uuid.uuid4(), uuid.uuid4()],
            failed=[],
            total_processed=2
        )
        mock_storage_service.return_value = mock_service_instance

        request_data = {"specifications": sample_specifications_data}

        response = await client.post(
            "api/v1/specifications/bulk/create",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert len(result["successful"]) == 2
        assert len(result["failed"]) == 0
        assert result["total_processed"] == 2

        # Verify service was called
        mock_service_instance.bulk_create_specifications.assert_called_once()

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_bulk_create_specifications_partial_failure(
        self, mock_storage_service, client: AsyncClient, logged_in_headers, sample_specifications_data
    ):
        """Test bulk creation with partial failures."""
        # Mock the storage service to return partial failures
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_create_specifications.return_value = BulkOperationResponse(
            successful=[uuid.uuid4()],
            failed=[{"id": "urn:agent:genesis:finance_agent:1", "error": "Validation error"}],
            total_processed=2
        )
        mock_storage_service.return_value = mock_service_instance

        request_data = {"specifications": sample_specifications_data}

        response = await client.post(
            "api/v1/specifications/bulk/create",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert len(result["successful"]) == 1
        assert len(result["failed"]) == 1
        assert result["failed"][0]["error"] == "Validation error"
        assert result["total_processed"] == 2

    @pytest.mark.asyncio
    async def test_bulk_create_specifications_unauthorized(
        self, client: AsyncClient, sample_specifications_data
    ):
        """Test bulk creation without authentication."""
        request_data = {"specifications": sample_specifications_data}

        response = await client.post("api/v1/specifications/bulk/create", json=request_data)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_bulk_create_specifications_invalid_data(self, client: AsyncClient, logged_in_headers):
        """Test bulk creation with invalid data."""
        invalid_data = {"specifications": ["invalid", "data"]}

        response = await client.post(
            "api/v1/specifications/bulk/create",
            json=invalid_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_bulk_create_specifications_service_error(
        self, mock_storage_service, client: AsyncClient, logged_in_headers, sample_specifications_data
    ):
        """Test bulk creation with service error."""
        # Mock the storage service to raise an exception
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_create_specifications.side_effect = Exception("Database error")
        mock_storage_service.return_value = mock_service_instance

        request_data = {"specifications": sample_specifications_data}

        response = await client.post(
            "api/v1/specifications/bulk/create",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to bulk create specifications" in response.json()["detail"]


class TestBulkUpdateSpecifications:
    """Test bulk update specifications endpoint."""

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_bulk_update_specifications_success(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test successful bulk update of specifications."""
        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_update_specifications.return_value = BulkOperationResponse(
            successful=[uuid.uuid4(), uuid.uuid4()],
            failed=[],
            total_processed=2
        )
        mock_storage_service.return_value = mock_service_instance

        updates = [
            {"id": str(uuid.uuid4()), "data": {"name": "Updated Agent 1"}},
            {"id": str(uuid.uuid4()), "data": {"description": "Updated description"}}
        ]
        request_data = {"updates": updates}

        response = await client.put(
            "api/v1/specifications/bulk/update",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["successful"]) == 2
        assert len(result["failed"]) == 0
        assert result["total_processed"] == 2

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_bulk_update_specifications_not_found(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test bulk update with some specifications not found."""
        # Mock the storage service to return partial failures
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_update_specifications.return_value = BulkOperationResponse(
            successful=[uuid.uuid4()],
            failed=[{"id": str(uuid.uuid4()), "error": "Specification not found"}],
            total_processed=2
        )
        mock_storage_service.return_value = mock_service_instance

        updates = [
            {"id": str(uuid.uuid4()), "data": {"name": "Updated Agent 1"}},
            {"id": str(uuid.uuid4()), "data": {"description": "Updated description"}}
        ]
        request_data = {"updates": updates}

        response = await client.put(
            "api/v1/specifications/bulk/update",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["successful"]) == 1
        assert len(result["failed"]) == 1
        assert "not found" in result["failed"][0]["error"]


class TestBulkDeleteSpecifications:
    """Test bulk delete specifications endpoint."""

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_bulk_delete_specifications_success(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test successful bulk deletion of specifications."""
        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_delete_specifications.return_value = BulkOperationResponse(
            successful=[uuid.uuid4(), uuid.uuid4(), uuid.uuid4()],
            failed=[],
            total_processed=3
        )
        mock_storage_service.return_value = mock_service_instance

        spec_ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]
        request_data = {"specification_ids": spec_ids}

        response = await client.request(
            "DELETE",
            "api/v1/specifications/bulk/delete",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["successful"]) == 3
        assert len(result["failed"]) == 0
        assert result["total_processed"] == 3

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_bulk_delete_specifications_partial_failure(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test bulk deletion with partial failures."""
        # Mock the storage service to return partial failures
        failed_id = str(uuid.uuid4())
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_delete_specifications.return_value = BulkOperationResponse(
            successful=[uuid.uuid4(), uuid.uuid4()],
            failed=[{"id": failed_id, "error": "Specification is linked to active flows"}],
            total_processed=3
        )
        mock_storage_service.return_value = mock_service_instance

        spec_ids = [str(uuid.uuid4()), str(uuid.uuid4()), failed_id]
        request_data = {"specification_ids": spec_ids}

        response = await client.request(
            "DELETE",
            "api/v1/specifications/bulk/delete",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["successful"]) == 2
        assert len(result["failed"]) == 1
        assert "linked to active flows" in result["failed"][0]["error"]


class TestSpecificationExport:
    """Test specification export endpoint."""

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_export_specifications_yaml(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test exporting specifications in YAML format."""
        yaml_content = """
specifications:
  - id: urn:agent:genesis:test:1
    name: Test Agent
    description: A test agent
    version: 1.0.0
    domain: healthcare
"""

        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.export_specifications.return_value = SpecificationExportResponse(
            format="yaml",
            filename="specifications_export.yaml",
            content=yaml_content,
            size=len(yaml_content.encode())
        )
        mock_storage_service.return_value = mock_service_instance

        response = await client.get(
            "api/v1/specifications/export",
            params={"format": "yaml"},
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["format"] == "yaml"
        assert result["filename"] == "specifications_export.yaml"
        assert "Test Agent" in result["content"]
        assert result["size"] > 0

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_export_specifications_json(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test exporting specifications in JSON format."""
        json_content = json.dumps({
            "specifications": [
                {
                    "id": "urn:agent:genesis:test:1",
                    "name": "Test Agent",
                    "description": "A test agent",
                    "version": "1.0.0",
                    "domain": "healthcare"
                }
            ]
        }, indent=2)

        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.export_specifications.return_value = SpecificationExportResponse(
            format="json",
            filename="specifications_export.json",
            content=json_content,
            size=len(json_content.encode())
        )
        mock_storage_service.return_value = mock_service_instance

        response = await client.get(
            "api/v1/specifications/export",
            params={"format": "json"},
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["format"] == "json"
        assert result["filename"] == "specifications_export.json"
        assert "Test Agent" in result["content"]

    @pytest.mark.asyncio
    async def test_export_specifications_invalid_format(self, client: AsyncClient, logged_in_headers):
        """Test exporting with invalid format."""
        response = await client.get(
            "api/v1/specifications/export",
            params={"format": "xml"},
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_export_specifications_with_filters(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test exporting specifications with domain filter."""
        yaml_content = """
specifications:
  - id: urn:agent:genesis:healthcare:1
    name: Healthcare Agent
    domain: healthcare
"""

        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.export_specifications.return_value = SpecificationExportResponse(
            format="yaml",
            filename="healthcare_specifications_export.yaml",
            content=yaml_content,
            size=len(yaml_content.encode())
        )
        mock_storage_service.return_value = mock_service_instance

        response = await client.get(
            "api/v1/specifications/export",
            params={"format": "yaml", "domain": "healthcare"},
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["format"] == "yaml"
        assert "healthcare" in result["filename"]


class TestSpecificationImport:
    """Test specification import endpoint."""

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_import_specifications_yaml(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test importing specifications from YAML."""
        yaml_content = """
specifications:
  - id: urn:agent:genesis:test:1
    name: Test Agent
    description: A test agent
    version: 1.0.0
    domain: healthcare
  - id: urn:agent:genesis:test:2
    name: Test Agent 2
    description: Another test agent
    version: 1.0.0
    domain: finance
"""

        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.import_specifications.return_value = SpecificationImportResponse(
            imported_count=2,
            skipped_count=0,
            failed_count=0,
            errors=[]
        )
        mock_storage_service.return_value = mock_service_instance

        request_data = {
            "format": "yaml",
            "content": yaml_content,
            "overwrite_existing": False
        }

        response = await client.post(
            "api/v1/specifications/import",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["imported_count"] == 2
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 0
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_import_specifications_json_with_errors(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test importing specifications with some errors."""
        json_content = json.dumps({
            "specifications": [
                {
                    "id": "urn:agent:genesis:test:1",
                    "name": "Valid Agent",
                    "description": "A valid agent",
                    "version": "1.0.0",
                    "domain": "healthcare"
                },
                {
                    "id": "invalid-id",
                    "name": "Invalid Agent",
                    # Missing required fields
                }
            ]
        })

        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.import_specifications.return_value = SpecificationImportResponse(
            imported_count=1,
            skipped_count=0,
            failed_count=1,
            errors=["Invalid specification ID format for item 2"]
        )
        mock_storage_service.return_value = mock_service_instance

        request_data = {
            "format": "json",
            "content": json_content,
            "overwrite_existing": True
        }

        response = await client.post(
            "api/v1/specifications/import",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["imported_count"] == 1
        assert result["failed_count"] == 1
        assert len(result["errors"]) == 1
        assert "Invalid specification ID" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_import_specifications_invalid_format(self, client: AsyncClient, logged_in_headers):
        """Test importing with invalid format."""
        request_data = {
            "format": "xml",
            "content": "<xml>content</xml>",
            "overwrite_existing": False
        }

        response = await client.post(
            "api/v1/specifications/import",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_import_specifications_invalid_content(self, client: AsyncClient, logged_in_headers):
        """Test importing with invalid content."""
        request_data = {
            "format": "yaml",
            "content": "invalid: yaml: content: [",
            "overwrite_existing": False
        }

        response = await client.post(
            "api/v1/specifications/import",
            json=request_data,
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestSpecificationTemplates:
    """Test specification templates endpoint."""

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_get_specification_templates(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test getting specification templates."""
        templates = [
            {
                "name": "Healthcare Agent Template",
                "description": "Template for healthcare diagnostic agents",
                "domain": "healthcare",
                "components": ["ChatInput", "LLMChain", "TextOutput"],
                "default_config": {
                    "goal": "Assist in medical diagnostics",
                    "target_user": "internal",
                    "value_generation": "ProcessAutomation"
                }
            },
            {
                "name": "Finance Agent Template",
                "description": "Template for financial analysis agents",
                "domain": "finance",
                "components": ["APICall", "DataProcessor", "ReportGenerator"],
                "default_config": {
                    "goal": "Perform financial analysis",
                    "target_user": "internal",
                    "value_generation": "InsightGeneration"
                }
            }
        ]

        categories = ["healthcare", "finance", "general", "automation"]

        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.get_specification_templates.return_value = SpecificationTemplateResponse(
            templates=templates,
            categories=categories
        )
        mock_storage_service.return_value = mock_service_instance

        response = await client.get("api/v1/specifications/templates", headers=logged_in_headers)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["templates"]) == 2
        assert len(result["categories"]) == 4

        # Check template structure
        healthcare_template = next(t for t in result["templates"] if t["domain"] == "healthcare")
        assert healthcare_template["name"] == "Healthcare Agent Template"
        assert "ChatInput" in healthcare_template["components"]
        assert healthcare_template["default_config"]["goal"] == "Assist in medical diagnostics"

        # Check categories
        assert "healthcare" in result["categories"]
        assert "finance" in result["categories"]

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_get_specification_templates_by_domain(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test getting specification templates filtered by domain."""
        templates = [
            {
                "name": "Healthcare Agent Template",
                "description": "Template for healthcare diagnostic agents",
                "domain": "healthcare",
                "components": ["ChatInput", "LLMChain", "TextOutput"]
            }
        ]

        categories = ["healthcare"]

        # Mock the storage service
        mock_service_instance = AsyncMock()
        mock_service_instance.get_specification_templates.return_value = SpecificationTemplateResponse(
            templates=templates,
            categories=categories
        )
        mock_storage_service.return_value = mock_service_instance

        response = await client.get(
            "api/v1/specifications/templates",
            params={"domain": "healthcare"},
            headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["templates"]) == 1
        assert result["templates"][0]["domain"] == "healthcare"

    @pytest.mark.asyncio
    async def test_get_specification_templates_unauthorized(self, client: AsyncClient):
        """Test getting templates without authentication."""
        response = await client.get("api/v1/specifications/templates")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


class TestBulkOperationErrorHandling:
    """Test error handling for bulk operations."""

    @pytest.mark.asyncio
    async def test_bulk_operations_without_auth(self, client: AsyncClient, sample_specifications_data):
        """Test that all bulk operations require authentication."""
        endpoints = [
            ("POST", "api/v1/specifications/bulk/create", {"specifications": sample_specifications_data}),
            ("PUT", "api/v1/specifications/bulk/update", {"updates": []}),
            ("DELETE", "api/v1/specifications/bulk/delete", {"specification_ids": []}),
            ("GET", "api/v1/specifications/export", None),
            ("POST", "api/v1/specifications/import", {"format": "yaml", "content": "test"}),
            ("GET", "api/v1/specifications/templates", None),
        ]

        for method, endpoint, data in endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "POST":
                response = await client.post(endpoint, json=data)
            elif method == "PUT":
                response = await client.put(endpoint, json=data)
            elif method == "DELETE":
                response = await client.request("DELETE", endpoint, json=data)

            assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    @patch('langflow.services.specification.service.SpecificationStorageService')
    async def test_bulk_operations_service_errors(
        self, mock_storage_service, client: AsyncClient, logged_in_headers
    ):
        """Test bulk operations when service raises exceptions."""
        # Mock service to raise exceptions
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_create_specifications.side_effect = Exception("Service error")
        mock_service_instance.bulk_update_specifications.side_effect = Exception("Service error")
        mock_service_instance.bulk_delete_specifications.side_effect = Exception("Service error")
        mock_service_instance.export_specifications.side_effect = Exception("Service error")
        mock_service_instance.import_specifications.side_effect = Exception("Service error")
        mock_service_instance.get_specification_templates.side_effect = Exception("Service error")
        mock_storage_service.return_value = mock_service_instance

        # Test each endpoint
        endpoints_and_data = [
            ("POST", "api/v1/specifications/bulk/create", {"specifications": []}),
            ("PUT", "api/v1/specifications/bulk/update", {"updates": []}),
            ("DELETE", "api/v1/specifications/bulk/delete", {"specification_ids": []}),
            ("GET", "api/v1/specifications/export?format=yaml", None),
            ("POST", "api/v1/specifications/import", {"format": "yaml", "content": "test"}),
            ("GET", "api/v1/specifications/templates", None),
        ]

        for method, endpoint, data in endpoints_and_data:
            if method == "GET":
                response = await client.get(endpoint, headers=logged_in_headers)
            elif method == "POST":
                response = await client.post(endpoint, json=data, headers=logged_in_headers)
            elif method == "PUT":
                response = await client.put(endpoint, json=data, headers=logged_in_headers)
            elif method == "DELETE":
                response = await client.request("DELETE", endpoint, json=data, headers=logged_in_headers)

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Service error" in response.json()["detail"] or "Failed to" in response.json()["detail"]