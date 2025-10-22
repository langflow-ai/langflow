"""Unit tests for database migration and tool capabilities model changes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentMappingUpdate,
    ComponentCategoryEnum,
)


class TestDatabaseMigration:
    """Test suite for database migration and model changes."""

    def test_component_mapping_model_has_tool_capabilities_field(self):
        """Test that ComponentMapping model has the new tool_capabilities field."""
        mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test",
            base_config={},
            component_category=ComponentCategoryEnum.TOOL.value,
            tool_capabilities={
                "accepts_tools": True,
                "provides_tools": False,
                "discovery_method": "test"
            },
            version="1.0.0"
        )

        assert mapping.tool_capabilities is not None
        assert mapping.tool_capabilities["accepts_tools"] is True
        assert mapping.tool_capabilities["provides_tools"] is False

    def test_component_mapping_model_has_runtime_introspection_field(self):
        """Test that ComponentMapping model has the new runtime_introspection field."""
        mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test",
            base_config={},
            component_category=ComponentCategoryEnum.TOOL.value,
            runtime_introspection={
                "discovered_at": "2025-10-22T12:00:00Z",
                "method": "class_introspection",
                "capabilities": {"tool_methods": ["calculate", "compute"]}
            },
            version="1.0.0"
        )

        assert mapping.runtime_introspection is not None
        assert mapping.runtime_introspection["method"] == "class_introspection"

    def test_component_mapping_create_schema_includes_new_fields(self):
        """Test that ComponentMappingCreate schema includes new fields."""
        create_data = ComponentMappingCreate(
            genesis_type="genesis:test",
            base_config={},
            component_category=ComponentCategoryEnum.AGENT.value,
            tool_capabilities={
                "accepts_tools": True,
                "provides_tools": True
            },
            runtime_introspection={
                "discovered_methods": ["process_tool", "handle_input"]
            },
            version="1.0.0"
        )

        assert hasattr(create_data, 'tool_capabilities')
        assert hasattr(create_data, 'runtime_introspection')
        assert create_data.tool_capabilities["accepts_tools"] is True

    def test_component_mapping_update_schema_includes_new_fields(self):
        """Test that ComponentMappingUpdate schema includes new fields."""
        update_data = ComponentMappingUpdate(
            tool_capabilities={
                "accepts_tools": False,
                "provides_tools": True,
                "updated_at": "2025-10-22T12:00:00Z"
            },
            runtime_introspection={
                "last_scan": "2025-10-22T12:00:00Z",
                "scan_method": "dynamic"
            }
        )

        assert hasattr(update_data, 'tool_capabilities')
        assert hasattr(update_data, 'runtime_introspection')
        assert update_data.tool_capabilities["provides_tools"] is True

    def test_tool_capabilities_field_validation(self):
        """Test validation of tool_capabilities field."""
        # Valid dictionary should pass
        mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test",
            base_config={},
            component_category=ComponentCategoryEnum.TOOL.value,
            tool_capabilities={"accepts_tools": True},
            version="1.0.0"
        )
        assert mapping.tool_capabilities == {"accepts_tools": True}

        # None should be acceptable
        mapping_none = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test2",
            base_config={},
            component_category=ComponentCategoryEnum.TOOL.value,
            tool_capabilities=None,
            version="1.0.0"
        )
        assert mapping_none.tool_capabilities is None

    def test_runtime_introspection_field_validation(self):
        """Test validation of runtime_introspection field."""
        # Valid dictionary should pass
        mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test",
            base_config={},
            component_category=ComponentCategoryEnum.TOOL.value,
            runtime_introspection={"scan_date": "2025-10-22"},
            version="1.0.0"
        )
        assert mapping.runtime_introspection == {"scan_date": "2025-10-22"}

        # None should be acceptable
        mapping_none = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test2",
            base_config={},
            component_category=ComponentCategoryEnum.TOOL.value,
            runtime_introspection=None,
            version="1.0.0"
        )
        assert mapping_none.runtime_introspection is None

    def test_model_serialization_with_new_fields(self):
        """Test that model serialization includes new fields."""
        mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test",
            base_config={"test": "value"},
            component_category=ComponentCategoryEnum.TOOL.value,
            tool_capabilities={
                "accepts_tools": True,
                "provides_tools": False,
                "discovery_method": "pattern_matching"
            },
            runtime_introspection={
                "last_updated": "2025-10-22T12:00:00Z",
                "introspection_version": "1.0"
            },
            version="1.0.0"
        )

        # Test model dump includes new fields
        model_dict = mapping.model_dump()
        assert "tool_capabilities" in model_dict
        assert "runtime_introspection" in model_dict
        assert model_dict["tool_capabilities"]["accepts_tools"] is True
        assert model_dict["runtime_introspection"]["introspection_version"] == "1.0"

    def test_backward_compatibility_without_new_fields(self):
        """Test that existing mappings without new fields still work."""
        # Create mapping without new fields
        mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:legacy",
            base_config={"legacy": "config"},
            component_category=ComponentCategoryEnum.TOOL.value,
            version="1.0.0"
        )

        # Should work fine with None values for new fields
        assert mapping.tool_capabilities is None
        assert mapping.runtime_introspection is None
        assert mapping.genesis_type == "genesis:legacy"

    def test_model_field_types_are_correct(self):
        """Test that new model fields have correct types."""
        from langflow.services.database.models.component_mapping.model import ComponentMappingBase

        # Check field annotations exist
        field_annotations = getattr(ComponentMappingBase, '__annotations__', {})

        # tool_capabilities should be Optional[dict]
        assert 'tool_capabilities' in field_annotations

        # runtime_introspection should be Optional[dict]
        assert 'runtime_introspection' in field_annotations

    def test_migration_file_structure(self):
        """Test that migration file has correct structure."""
        # This would typically read the actual migration file
        # For now, we'll test that the expected migration exists
        import os
        migration_file = "/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/alembic/versions/add_tool_capabilities_to_component_mapping.py"

        assert os.path.exists(migration_file), "Migration file should exist"

        # Read migration file and check it contains the expected operations
        with open(migration_file, 'r') as f:
            content = f.read()

        assert "tool_capabilities" in content, "Migration should add tool_capabilities column"
        assert "runtime_introspection" in content, "Migration should add runtime_introspection column"
        assert "idx_tool_capabilities" in content, "Migration should add index for tool_capabilities"

    def test_json_field_handling(self):
        """Test that JSON fields are properly handled."""
        # Test complex nested JSON structure
        complex_capabilities = {
            "accepts_tools": True,
            "provides_tools": False,
            "tool_types": ["calculator", "api_request"],
            "metadata": {
                "discovery_date": "2025-10-22",
                "confidence": 0.95,
                "source": "automatic_introspection"
            }
        }

        mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:complex_test",
            base_config={},
            component_category=ComponentCategoryEnum.TOOL.value,
            tool_capabilities=complex_capabilities,
            version="1.0.0"
        )

        # Verify nested structure is preserved
        assert mapping.tool_capabilities["metadata"]["confidence"] == 0.95
        assert "calculator" in mapping.tool_capabilities["tool_types"]