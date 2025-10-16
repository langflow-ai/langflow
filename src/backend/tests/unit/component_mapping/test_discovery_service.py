"""Unit tests for ComponentDiscoveryService."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from langflow.services.component_mapping.discovery_service import ComponentDiscoveryService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentCategoryEnum,
)
from langflow.services.spec.component_schema_inspector import ComponentSchema


@pytest.fixture
def discovery_service():
    """Create a discovery service instance for testing."""
    return ComponentDiscoveryService()


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def sample_component_schema():
    """Create a sample component schema for testing."""
    return ComponentSchema(
        name="TestComponent",
        class_name="TestComponent",
        module_path="test.module",
        inputs=[{"name": "input_value", "type": "str"}],
        outputs=[{"name": "output", "type": "Data"}],
        input_types=["str"],
        output_types=["Data"],
        description="Test component for testing",
        display_name="Test Component",
        base_classes=["Component"],
    )


@pytest.fixture
def sample_component_mapping():
    """Create a sample component mapping for testing."""
    return ComponentMapping(
        id=uuid4(),
        genesis_type="genesis:test_component",
        base_config={"test": "config"},
        io_mapping={
            "component": "TestComponent",
            "input_field": "input_value",
            "output_field": "output",
            "input_types": ["str"],
            "output_types": ["Data"],
        },
        component_category=ComponentCategoryEnum.TOOL,
        description="Test mapping",
        version="1.0.0",
        active=True,
    )


class TestComponentDiscoveryService:
    """Test cases for ComponentDiscoveryService."""

    def test_init(self):
        """Test service initialization."""
        service = ComponentDiscoveryService()
        assert service.name == "component_discovery_service"
        assert service._inspector is None
        assert service._mapping_service is None

    def test_inspector_property(self, discovery_service):
        """Test inspector property lazy loading."""
        with patch('langflow.services.component_mapping.discovery_service.ComponentSchemaInspector') as mock_inspector:
            inspector = discovery_service.inspector
            assert inspector is not None
            mock_inspector.assert_called_once()

    def test_mapping_service_property(self, discovery_service):
        """Test mapping service property lazy loading."""
        with patch('langflow.services.component_mapping.discovery_service.ComponentMappingService') as mock_service:
            service = discovery_service.mapping_service
            assert service is not None
            mock_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_components_success(self, discovery_service, mock_session, sample_component_schema):
        """Test successful component discovery."""
        # Mock inspector
        mock_inspector = Mock()
        mock_inspector.get_all_schemas.return_value = {
            "TestComponent": sample_component_schema,
            "NewComponent": ComponentSchema(
                name="NewComponent",
                class_name="NewComponent",
                module_path="new.module",
                inputs=[],
                outputs=[],
                input_types=[],
                output_types=[],
                description="New component",
                display_name="New Component",
                base_classes=["Component"],
            )
        }
        discovery_service._inspector = mock_inspector

        # Mock mapping service
        mock_mapping_service = AsyncMock()
        mock_mapping_service.get_all_component_mappings.return_value = []
        discovery_service._mapping_service = mock_mapping_service

        result = await discovery_service.discover_components(mock_session)

        assert result["total_langflow_components"] == 2
        assert result["existing_mappings"] == 0
        assert len(result["new_components_found"]) == 2
        assert result["statistics"]["unmapped_components"] == 2

    @pytest.mark.asyncio
    async def test_discover_components_with_existing_mappings(
        self, discovery_service, mock_session, sample_component_schema, sample_component_mapping
    ):
        """Test discovery with existing mappings."""
        # Mock inspector
        mock_inspector = Mock()
        mock_inspector.get_all_schemas.return_value = {"TestComponent": sample_component_schema}
        discovery_service._inspector = mock_inspector

        # Mock mapping service with existing mapping
        mock_mapping_service = AsyncMock()
        mock_mapping_service.get_all_component_mappings.return_value = [sample_component_mapping]
        discovery_service._mapping_service = mock_mapping_service

        result = await discovery_service.discover_components(mock_session)

        assert result["total_langflow_components"] == 1
        assert result["existing_mappings"] == 1
        assert len(result["new_components_found"]) == 0
        assert result["statistics"]["mapped_components"] == 1

    @pytest.mark.asyncio
    async def test_discover_components_error_handling(self, discovery_service, mock_session):
        """Test error handling during discovery."""
        # Mock inspector to raise exception
        mock_inspector = Mock()
        mock_inspector.get_all_schemas.side_effect = Exception("Inspector error")
        discovery_service._inspector = mock_inspector

        result = await discovery_service.discover_components(mock_session)

        assert "error" in result
        assert "Inspector error" in result["error"]

    @pytest.mark.asyncio
    async def test_auto_create_mappings_success(self, discovery_service, mock_session, sample_component_schema):
        """Test successful automatic mapping creation."""
        # Mock inspector
        mock_inspector = Mock()
        mock_inspector.get_all_schemas.return_value = {"TestComponent": sample_component_schema}
        discovery_service._inspector = mock_inspector

        # Mock mapping service
        mock_mapping_service = AsyncMock()
        mock_mapping_service.get_component_mapping_by_genesis_type.return_value = None
        mock_mapping_service.create_component_mapping.return_value = sample_component_mapping
        mock_mapping_service.create_runtime_adapter.return_value = Mock()
        discovery_service._mapping_service = mock_mapping_service

        result = await discovery_service.auto_create_mappings(
            mock_session, ["TestComponent"], "genesis:"
        )

        assert result["created"] == 1
        assert len(result["errors"]) == 0
        assert len(result["created_mappings"]) == 1

    @pytest.mark.asyncio
    async def test_auto_create_mappings_component_not_found(self, discovery_service, mock_session):
        """Test auto creation with component not found."""
        # Mock inspector with empty schemas
        mock_inspector = Mock()
        mock_inspector.get_all_schemas.return_value = {}
        discovery_service._inspector = mock_inspector

        result = await discovery_service.auto_create_mappings(
            mock_session, ["NonExistentComponent"], "genesis:"
        )

        assert result["created"] == 0
        assert len(result["errors"]) == 1
        assert "NonExistentComponent not found" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_auto_create_mappings_existing_mapping(self, discovery_service, mock_session, sample_component_schema, sample_component_mapping):
        """Test auto creation with existing mapping."""
        # Mock inspector
        mock_inspector = Mock()
        mock_inspector.get_all_schemas.return_value = {"TestComponent": sample_component_schema}
        discovery_service._inspector = mock_inspector

        # Mock mapping service with existing mapping
        mock_mapping_service = AsyncMock()
        mock_mapping_service.get_component_mapping_by_genesis_type.return_value = sample_component_mapping
        discovery_service._mapping_service = mock_mapping_service

        result = await discovery_service.auto_create_mappings(
            mock_session, ["TestComponent"], "genesis:"
        )

        assert result["created"] == 0
        assert len(result["errors"]) == 1
        assert "already exists" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_update_schemas_from_discovery(self, discovery_service, mock_session, sample_component_schema, sample_component_mapping):
        """Test schema updates from discovery."""
        # Mock inspector
        mock_inspector = Mock()
        mock_inspector.get_all_schemas.return_value = {"TestComponent": sample_component_schema}
        discovery_service._inspector = mock_inspector

        # Mock mapping service
        mock_mapping_service = AsyncMock()
        mock_mapping_service.get_all_component_mappings.return_value = [sample_component_mapping]
        mock_mapping_service.update_component_mapping.return_value = sample_component_mapping
        discovery_service._mapping_service = mock_mapping_service

        result = await discovery_service.update_schemas_from_discovery(mock_session, force_update=True)

        assert result["updated"] == 1
        assert len(result["errors"]) == 0

    def test_generate_genesis_type_name(self, discovery_service):
        """Test genesis type name generation."""
        # Test CamelCase conversion
        assert discovery_service._generate_genesis_type_name("TestComponent") == "genesis:test_component"

        # Test suffix removal
        assert discovery_service._generate_genesis_type_name("MyToolComponent") == "genesis:my_tool"

        # Test custom prefix
        assert discovery_service._generate_genesis_type_name("TestComponent", "custom:") == "custom:test_component"

    def test_determine_component_category(self, discovery_service, sample_component_schema):
        """Test component category determination."""
        # Test healthcare category
        healthcare_schema = ComponentSchema(
            name="HealthComponent",
            class_name="HealthComponent",
            module_path="health.module",
            inputs=[], outputs=[], input_types=[], output_types=[],
            description="Healthcare component", display_name="Health Component",
            base_classes=["Component"]
        )
        assert discovery_service._determine_component_category(healthcare_schema) == ComponentCategoryEnum.HEALTHCARE

        # Test agent category
        agent_schema = ComponentSchema(
            name="AgentComponent",
            class_name="AgentComponent",
            module_path="agent.module",
            inputs=[], outputs=[], input_types=[], output_types=[],
            description="Agent component", display_name="Agent Component",
            base_classes=["Component"]
        )
        assert discovery_service._determine_component_category(agent_schema) == ComponentCategoryEnum.AGENT

        # Test default category
        assert discovery_service._determine_component_category(sample_component_schema) == ComponentCategoryEnum.PROCESSING

    def test_assess_mapping_priority(self, discovery_service, sample_component_schema):
        """Test mapping priority assessment."""
        # Test high priority (healthcare)
        healthcare_schema = ComponentSchema(
            name="HealthComponent",
            class_name="HealthComponent",
            module_path="health.module",
            inputs=[], outputs=[], input_types=[], output_types=[],
            description="Healthcare component", display_name="Health Component",
            base_classes=["Component"]
        )
        assert discovery_service._assess_mapping_priority(healthcare_schema) == "high"

        # Test medium priority (tool)
        tool_schema = ComponentSchema(
            name="ToolComponent",
            class_name="ToolComponent",
            module_path="tool.module",
            inputs=[], outputs=[], input_types=[], output_types=[],
            description="Tool component", display_name="Tool Component",
            base_classes=["Component"]
        )
        assert discovery_service._assess_mapping_priority(tool_schema) == "medium"

        # Test low priority (default)
        assert discovery_service._assess_mapping_priority(sample_component_schema) == "low"

    def test_has_schema_changed(self, discovery_service, sample_component_schema, sample_component_mapping):
        """Test schema change detection."""
        # Test no change
        assert not discovery_service._has_schema_changed(sample_component_mapping, sample_component_schema)

        # Test change in input types
        changed_schema = ComponentSchema(
            name="TestComponent",
            class_name="TestComponent",
            module_path="test.module",
            inputs=[{"name": "input_value", "type": "int"}],
            outputs=[{"name": "output", "type": "Data"}],
            input_types=["int"],  # Changed from str
            output_types=["Data"],
            description="Test component for testing",
            display_name="Test Component",
            base_classes=["Component"],
        )
        assert discovery_service._has_schema_changed(sample_component_mapping, changed_schema)

        # Test mapping without io_mapping
        mapping_without_io = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test_component",
            base_config={},
            io_mapping=None,
            component_category=ComponentCategoryEnum.TOOL,
            description="Test mapping",
            version="1.0.0",
            active=True,
        )
        assert discovery_service._has_schema_changed(mapping_without_io, sample_component_schema)

    def test_create_io_mapping_from_schema(self, discovery_service, sample_component_schema):
        """Test I/O mapping creation from schema."""
        result = discovery_service._create_io_mapping_from_schema(sample_component_schema)

        assert result["component"] == "TestComponent"
        assert result["class_name"] == "TestComponent"
        assert result["module_path"] == "test.module"
        assert result["input_field"] == "input_value"
        assert result["output_field"] == "output"
        assert result["input_types"] == ["str"]
        assert result["output_types"] == ["Data"]

    def test_extract_default_config(self, discovery_service):
        """Test default config extraction."""
        schema_with_defaults = ComponentSchema(
            name="TestComponent",
            class_name="TestComponent",
            module_path="test.module",
            inputs=[
                {"name": "param1", "type": "str", "default": "default_value"},
                {"name": "param2", "type": "int", "default": 42}
            ],
            outputs=[],
            input_types=[],
            output_types=[],
            description="Test component",
            display_name="Test Component",
            base_classes=["Component"],
        )

        result = discovery_service._extract_default_config(schema_with_defaults)

        assert result["param1"] == "default_value"
        assert result["param2"] == 42

    def test_generate_discovery_statistics(self, discovery_service, sample_component_schema, sample_component_mapping):
        """Test discovery statistics generation."""
        all_schemas = {
            "TestComponent": sample_component_schema,
            "AnotherComponent": ComponentSchema(
                name="AnotherComponent",
                class_name="AnotherComponent",
                module_path="another.module",
                inputs=[], outputs=[], input_types=[], output_types=[],
                description="Another component", display_name="Another Component",
                base_classes=["Component"]
            )
        }

        existing_mappings = [sample_component_mapping]

        result = discovery_service._generate_discovery_statistics(all_schemas, existing_mappings)

        assert result["total_langflow_components"] == 2
        assert result["mapped_components"] == 1
        assert result["unmapped_components"] == 1
        assert result["mapping_coverage"] == 50.0
        assert "components_by_category" in result

    def test_generate_mapping_recommendations(self, discovery_service):
        """Test mapping recommendations generation."""
        new_components = [
            {
                "component_name": "HighPriorityComponent",
                "recommendation": {
                    "priority": "high",
                    "suggested_genesis_type": "genesis:high_priority_component",
                    "category": "healthcare",
                    "rationale": "High priority component",
                }
            },
            {
                "component_name": "LowPriorityComponent",
                "recommendation": {
                    "priority": "low",
                    "suggested_genesis_type": "genesis:low_priority_component",
                    "category": "tool",
                    "rationale": "Low priority component",
                }
            }
        ]

        result = discovery_service._generate_mapping_recommendations(new_components)

        assert len(result) == 2
        assert result[0]["priority"] == "high"  # High priority first
        assert result[1]["priority"] == "low"
        assert all("component_name" in rec for rec in result)
        assert all("suggested_genesis_type" in rec for rec in result)


# Integration Tests

@pytest.mark.asyncio
async def test_discovery_integration_workflow(discovery_service, mock_session):
    """Test complete discovery workflow integration."""
    # Mock all dependencies
    mock_schema = ComponentSchema(
        name="IntegrationTestComponent",
        class_name="IntegrationTestComponent",
        module_path="integration.test",
        inputs=[{"name": "input", "type": "str"}],
        outputs=[{"name": "output", "type": "Data"}],
        input_types=["str"],
        output_types=["Data"],
        description="Integration test component",
        display_name="Integration Test Component",
        base_classes=["Component"],
    )

    mock_inspector = Mock()
    mock_inspector.get_all_schemas.return_value = {"IntegrationTestComponent": mock_schema}
    discovery_service._inspector = mock_inspector

    mock_mapping_service = AsyncMock()
    mock_mapping_service.get_all_component_mappings.return_value = []
    mock_mapping_service.create_component_mapping.return_value = Mock(id=uuid4())
    mock_mapping_service.create_runtime_adapter.return_value = Mock()
    discovery_service._mapping_service = mock_mapping_service

    # Run discovery
    discovery_result = await discovery_service.discover_components(mock_session)
    assert discovery_result["total_langflow_components"] == 1
    assert len(discovery_result["new_components_found"]) == 1

    # Auto-create mappings
    create_result = await discovery_service.auto_create_mappings(
        mock_session, ["IntegrationTestComponent"]
    )
    assert create_result["created"] == 1

    # Verify method calls
    mock_mapping_service.create_component_mapping.assert_called_once()
    mock_mapping_service.create_runtime_adapter.assert_called_once()


@pytest.mark.asyncio
async def test_error_handling_throughout_workflow(discovery_service, mock_session):
    """Test error handling in various parts of the workflow."""
    # Mock inspector to fail
    mock_inspector = Mock()
    mock_inspector.get_all_schemas.side_effect = Exception("Inspector failed")
    discovery_service._inspector = mock_inspector

    # Discovery should handle error gracefully
    result = await discovery_service.discover_components(mock_session)
    assert "error" in result

    # Mock mapping service to fail
    mock_mapping_service = AsyncMock()
    mock_mapping_service.create_component_mapping.side_effect = Exception("Service failed")
    discovery_service._mapping_service = mock_mapping_service

    # Reset inspector to work
    mock_inspector.get_all_schemas.side_effect = None
    mock_inspector.get_all_schemas.return_value = {"TestComponent": Mock()}

    # Auto-create should handle service error
    result = await discovery_service.auto_create_mappings(mock_session, ["TestComponent"])
    assert result["created"] == 0
    assert len(result["errors"]) == 1
    assert "Service failed" in result["errors"][0]