import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from langflow.api.v1.schemas import (
    BulkOperationResponse,
    ConversionResultResponse,
    FlowWithSpecification,
    SpecificationSummary,
    SpecificationListResponse,
    BulkCreateSpecificationRequest,
    BulkUpdateSpecificationRequest,
    BulkDeleteSpecificationRequest,
    SpecificationExportResponse,
    SpecificationImportRequest,
    SpecificationImportResponse,
    SpecificationTemplateResponse,
    FlowSpecificationMetadata,
)
from langflow.services.database.models.flow.model import FlowRead


class TestSpecificationSummary:
    """Test SpecificationSummary schema."""

    def test_specification_summary_creation(self):
        """Test creating a SpecificationSummary instance."""
        spec_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        summary = SpecificationSummary(
            id=spec_id,
            name="Test Agent",
            version="1.0.0",
            status="ACTIVE",
            domain="healthcare",
            subdomain="diagnostics",
            kind="Single Agent",
            target_user="internal",
            description="A test agent specification",
            tags=["test", "healthcare"],
            reusability_score=0.85,
            complexity_score=0.6,
            created_at=created_at,
            updated_at=updated_at,
            owner_email="test@example.com",
            flow_id=uuid4()
        )

        assert summary.id == spec_id
        assert summary.name == "Test Agent"
        assert summary.version == "1.0.0"
        assert summary.status == "ACTIVE"
        assert summary.domain == "healthcare"
        assert summary.subdomain == "diagnostics"
        assert summary.kind == "Single Agent"
        assert summary.target_user == "internal"
        assert summary.description == "A test agent specification"
        assert summary.tags == ["test", "healthcare"]
        assert summary.reusability_score == 0.85
        assert summary.complexity_score == 0.6
        assert summary.created_at == created_at
        assert summary.updated_at == updated_at
        assert summary.owner_email == "test@example.com"
        assert isinstance(summary.flow_id, UUID)

    def test_specification_summary_optional_fields(self):
        """Test SpecificationSummary with optional fields as None."""
        spec_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        summary = SpecificationSummary(
            id=spec_id,
            name="Test Agent",
            version="1.0.0",
            status="ACTIVE",
            domain="healthcare",
            subdomain=None,
            kind="Single Agent",
            target_user="internal",
            description=None,
            tags=None,
            reusability_score=None,
            complexity_score=None,
            created_at=created_at,
            updated_at=updated_at,
            owner_email="test@example.com",
            flow_id=None
        )

        assert summary.subdomain is None
        assert summary.description is None
        assert summary.tags is None
        assert summary.reusability_score is None
        assert summary.complexity_score is None
        assert summary.flow_id is None

    def test_specification_summary_serialization(self):
        """Test SpecificationSummary serialization."""
        spec_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        summary = SpecificationSummary(
            id=spec_id,
            name="Test Agent",
            version="1.0.0",
            status="ACTIVE",
            domain="healthcare",
            subdomain="diagnostics",
            kind="Single Agent",
            target_user="internal",
            description="A test agent specification",
            tags=["test", "healthcare"],
            reusability_score=0.85,
            complexity_score=0.6,
            created_at=created_at,
            updated_at=updated_at,
            owner_email="test@example.com",
            flow_id=uuid4()
        )

        serialized = summary.model_dump()
        assert isinstance(serialized["id"], UUID)
        assert serialized["name"] == "Test Agent"
        assert serialized["tags"] == ["test", "healthcare"]
        assert serialized["reusability_score"] == 0.85


class TestFlowWithSpecification:
    """Test FlowWithSpecification schema."""

    def test_flow_with_specification_creation(self):
        """Test creating a FlowWithSpecification instance."""
        flow_id = uuid4()
        user_id = uuid4()
        spec_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        specification = SpecificationSummary(
            id=spec_id,
            name="Test Agent",
            version="1.0.0",
            status="ACTIVE",
            domain="healthcare",
            subdomain="diagnostics",
            kind="Single Agent",
            target_user="internal",
            description="A test agent specification",
            tags=["test", "healthcare"],
            reusability_score=0.85,
            complexity_score=0.6,
            created_at=created_at,
            updated_at=updated_at,
            owner_email="test@example.com",
            flow_id=flow_id
        )

        flow_with_spec = FlowWithSpecification(
            id=flow_id,
            name="Test Flow",
            description="A test flow",
            icon="test-icon",
            icon_bg_color="#ff00ff",
            gradient="linear-gradient(...)",
            data={"nodes": [], "edges": []},
            is_component=False,
            updated_at=updated_at,
            webhook=False,
            endpoint_name="test_endpoint",
            tags=["test"],
            locked=False,
            mcp_enabled=False,
            action_name="test_action",
            action_description="Test action description",
            access_type="PRIVATE",
            user_id=user_id,
            folder_id=None,
            specification_id=spec_id,
            has_specification=True,
            specification_status="ACTIVE",
            specification=specification
        )

        assert flow_with_spec.id == flow_id
        assert flow_with_spec.name == "Test Flow"
        assert flow_with_spec.specification is not None
        assert flow_with_spec.specification.id == spec_id
        assert flow_with_spec.specification_id == spec_id
        assert flow_with_spec.has_specification is True
        assert flow_with_spec.specification_status == "ACTIVE"

    def test_flow_with_specification_no_spec(self):
        """Test FlowWithSpecification without specification."""
        flow_id = uuid4()
        user_id = uuid4()
        updated_at = datetime.now(timezone.utc)

        flow_with_spec = FlowWithSpecification(
            id=flow_id,
            name="Test Flow",
            description="A test flow",
            icon="test-icon",
            icon_bg_color="#ff00ff",
            gradient="linear-gradient(...)",
            data={"nodes": [], "edges": []},
            is_component=False,
            updated_at=updated_at,
            webhook=False,
            endpoint_name="test_endpoint",
            tags=["test"],
            locked=False,
            mcp_enabled=False,
            action_name="test_action",
            action_description="Test action description",
            access_type="PRIVATE",
            user_id=user_id,
            folder_id=None,
            specification_id=None,
            has_specification=False,
            specification_status=None,
            specification=None
        )

        assert flow_with_spec.specification is None
        assert flow_with_spec.specification_id is None
        assert flow_with_spec.has_specification is False
        assert flow_with_spec.specification_status is None


class TestBulkOperationResponse:
    """Test BulkOperationResponse schema."""

    def test_bulk_operation_response_success(self):
        """Test BulkOperationResponse with successful operations."""
        successful_ids = [uuid4(), uuid4(), uuid4()]
        failed_operations = [
            {"id": uuid4(), "error": "Validation error"},
            {"id": uuid4(), "error": "Database constraint violation"}
        ]

        response = BulkOperationResponse(
            successful=successful_ids,
            failed=failed_operations,
            total_processed=5
        )

        assert len(response.successful) == 3
        assert len(response.failed) == 2
        assert response.total_processed == 5
        assert all(isinstance(id, UUID) for id in response.successful)
        assert all("error" in failure for failure in response.failed)

    def test_bulk_operation_response_all_success(self):
        """Test BulkOperationResponse with all successful operations."""
        successful_ids = [uuid4(), uuid4(), uuid4()]

        response = BulkOperationResponse(
            successful=successful_ids,
            failed=[],
            total_processed=3
        )

        assert len(response.successful) == 3
        assert len(response.failed) == 0
        assert response.total_processed == 3

    def test_bulk_operation_response_all_failed(self):
        """Test BulkOperationResponse with all failed operations."""
        failed_operations = [
            {"id": uuid4(), "error": "Error 1"},
            {"id": uuid4(), "error": "Error 2"},
            {"id": uuid4(), "error": "Error 3"}
        ]

        response = BulkOperationResponse(
            successful=[],
            failed=failed_operations,
            total_processed=3
        )

        assert len(response.successful) == 0
        assert len(response.failed) == 3
        assert response.total_processed == 3


class TestSpecificationListResponse:
    """Test SpecificationListResponse schema."""

    def test_specification_list_response(self):
        """Test creating a SpecificationListResponse."""
        specs = []
        for i in range(3):
            specs.append(SpecificationSummary(
                id=uuid4(),
                name=f"Test Agent {i}",
                version="1.0.0",
                status="ACTIVE",
                domain="healthcare",
                subdomain="diagnostics",
                kind="Single Agent",
                target_user="internal",
                description=f"Test agent {i}",
                tags=["test"],
                reusability_score=0.8,
                complexity_score=0.5,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                owner_email="test@example.com",
                flow_id=uuid4()
            ))

        response = SpecificationListResponse(
            items=specs,
            total=10,
            page=1,
            page_size=3,
            has_more=True
        )

        assert len(response.items) == 3
        assert response.total == 10
        assert response.page == 1
        assert response.page_size == 3
        assert response.has_more is True

    def test_specification_list_response_last_page(self):
        """Test SpecificationListResponse for last page."""
        response = SpecificationListResponse(
            items=[],
            total=0,
            page=1,
            page_size=10,
            has_more=False
        )

        assert len(response.items) == 0
        assert response.total == 0
        assert response.has_more is False


class TestBulkRequestSchemas:
    """Test bulk request schemas."""

    def test_bulk_create_specification_request(self):
        """Test BulkCreateSpecificationRequest."""
        specifications = [
            {
                "name": "Agent 1",
                "description": "Description 1",
                "domain": "healthcare",
                "goal": "Goal 1"
            },
            {
                "name": "Agent 2",
                "description": "Description 2",
                "domain": "finance",
                "goal": "Goal 2"
            }
        ]

        request = BulkCreateSpecificationRequest(specifications=specifications)
        assert len(request.specifications) == 2
        assert request.specifications[0]["name"] == "Agent 1"

    def test_bulk_update_specification_request(self):
        """Test BulkUpdateSpecificationRequest."""
        updates = [
            {"id": uuid4(), "data": {"name": "Updated Agent 1"}},
            {"id": uuid4(), "data": {"description": "Updated description"}}
        ]

        request = BulkUpdateSpecificationRequest(updates=updates)
        assert len(request.updates) == 2
        assert "id" in request.updates[0]
        assert "data" in request.updates[0]

    def test_bulk_delete_specification_request(self):
        """Test BulkDeleteSpecificationRequest."""
        spec_ids = [uuid4(), uuid4(), uuid4()]

        request = BulkDeleteSpecificationRequest(specification_ids=spec_ids)
        assert len(request.specification_ids) == 3
        assert all(isinstance(id, UUID) for id in request.specification_ids)


class TestImportExportSchemas:
    """Test import/export schemas."""

    def test_specification_export_response(self):
        """Test SpecificationExportResponse."""
        content = """
id: urn:agent:genesis:test:1
name: Test Agent
description: A test agent
version: 1.0.0
"""

        response = SpecificationExportResponse(
            format="yaml",
            filename="specifications_export.yaml",
            content=content,
            size=len(content.encode())
        )

        assert response.format == "yaml"
        assert response.filename == "specifications_export.yaml"
        assert response.content == content
        assert response.size == len(content.encode())

    def test_specification_import_request(self):
        """Test SpecificationImportRequest."""
        content = """
[
  {
    "id": "urn:agent:genesis:test:1",
    "name": "Test Agent",
    "description": "A test agent"
  }
]
"""

        request = SpecificationImportRequest(
            format="json",
            content=content,
            overwrite_existing=True
        )

        assert request.format == "json"
        assert request.content == content
        assert request.overwrite_existing is True

    def test_specification_import_response(self):
        """Test SpecificationImportResponse."""
        response = SpecificationImportResponse(
            imported_count=5,
            skipped_count=2,
            failed_count=1,
            errors=["Invalid specification format for item 8"]
        )

        assert response.imported_count == 5
        assert response.skipped_count == 2
        assert response.failed_count == 1
        assert len(response.errors) == 1


class TestConversionResultResponse:
    """Test ConversionResultResponse schema."""

    def test_conversion_result_success(self):
        """Test successful conversion result."""
        spec_id = uuid4()
        specification = {
            "id": "urn:agent:genesis:test:1",
            "name": "Test Agent",
            "description": "A test agent"
        }

        response = ConversionResultResponse(
            success=True,
            specification_id=spec_id,
            specification=specification,
            warnings=["Some components could not be automatically mapped"],
            errors=[]
        )

        assert response.success is True
        assert response.specification_id == spec_id
        assert response.specification["name"] == "Test Agent"
        assert len(response.warnings) == 1
        assert len(response.errors) == 0

    def test_conversion_result_failure(self):
        """Test failed conversion result."""
        response = ConversionResultResponse(
            success=False,
            specification_id=None,
            specification=None,
            warnings=[],
            errors=["Invalid flow structure", "Missing required components"]
        )

        assert response.success is False
        assert response.specification_id is None
        assert response.specification is None
        assert len(response.warnings) == 0
        assert len(response.errors) == 2


class TestSpecificationTemplateResponse:
    """Test SpecificationTemplateResponse schema."""

    def test_specification_template_response(self):
        """Test SpecificationTemplateResponse."""
        templates = [
            {
                "name": "Healthcare Agent Template",
                "description": "Template for healthcare agents",
                "domain": "healthcare",
                "components": ["ChatInput", "LLMChain", "TextOutput"]
            },
            {
                "name": "Finance Agent Template",
                "description": "Template for finance agents",
                "domain": "finance",
                "components": ["APICall", "DataProcessor", "Report"]
            }
        ]

        categories = ["healthcare", "finance", "general"]

        response = SpecificationTemplateResponse(
            templates=templates,
            categories=categories
        )

        assert len(response.templates) == 2
        assert len(response.categories) == 3
        assert response.templates[0]["name"] == "Healthcare Agent Template"
        assert "healthcare" in response.categories


class TestFlowSpecificationMetadata:
    """Test FlowSpecificationMetadata schema."""

    def test_flow_specification_metadata(self):
        """Test FlowSpecificationMetadata."""
        flow_id = uuid4()
        spec_id = uuid4()
        last_sync = datetime.now(timezone.utc)

        metadata = FlowSpecificationMetadata(
            flow_id=flow_id,
            specification_id=spec_id,
            has_specification=True,
            specification_status="ACTIVE",
            last_sync_at=last_sync,
            sync_required=False
        )

        assert metadata.flow_id == flow_id
        assert metadata.specification_id == spec_id
        assert metadata.has_specification is True
        assert metadata.specification_status == "ACTIVE"
        assert metadata.last_sync_at == last_sync
        assert metadata.sync_required is False

    def test_flow_specification_metadata_no_spec(self):
        """Test FlowSpecificationMetadata without specification."""
        flow_id = uuid4()

        metadata = FlowSpecificationMetadata(
            flow_id=flow_id,
            specification_id=None,
            has_specification=False,
            specification_status=None,
            last_sync_at=None,
            sync_required=False
        )

        assert metadata.flow_id == flow_id
        assert metadata.specification_id is None
        assert metadata.has_specification is False
        assert metadata.specification_status is None
        assert metadata.last_sync_at is None
        assert metadata.sync_required is False


class TestSchemaValidation:
    """Test schema validation edge cases."""

    def test_invalid_uuid_validation(self):
        """Test validation with invalid UUIDs."""
        with pytest.raises(ValueError):
            SpecificationSummary(
                id="invalid-uuid",
                name="Test",
                version="1.0.0",
                status="ACTIVE",
                domain="test",
                kind="Single Agent",
                target_user="internal",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                owner_email="test@example.com"
            )

    def test_schema_serialization_with_none_values(self):
        """Test schema serialization handling of None values."""
        spec_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        summary = SpecificationSummary(
            id=spec_id,
            name="Test Agent",
            version="1.0.0",
            status="ACTIVE",
            domain="healthcare",
            subdomain=None,
            kind="Single Agent",
            target_user="internal",
            description=None,
            tags=None,
            reusability_score=None,
            complexity_score=None,
            created_at=created_at,
            updated_at=updated_at,
            owner_email="test@example.com",
            flow_id=None
        )

        # Test serialization excludes None values when appropriate
        serialized = summary.model_dump(exclude_none=True)
        assert "subdomain" not in serialized
        assert "description" not in serialized
        assert "tags" not in serialized
        assert "reusability_score" not in serialized
        assert "complexity_score" not in serialized
        assert "flow_id" not in serialized

        # Test serialization includes None values when requested
        serialized_with_none = summary.model_dump(exclude_none=False)
        assert serialized_with_none["subdomain"] is None
        assert serialized_with_none["description"] is None