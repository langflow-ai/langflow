"""Tests for component mapping database models."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from langflow.services.database.models.component_mapping.model import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentMappingUpdate,
    ComponentCategoryEnum,
)
from pydantic import ValidationError


class TestComponentMappingModel:
    """Test ComponentMapping model validation and functionality."""

    def test_component_mapping_base_validation(self):
        """Test basic validation of ComponentMapping model."""
        # Valid data
        valid_data = ComponentMappingCreate(
            genesis_type="genesis:test_component",
            base_config={"key": "value"},
            io_mapping={"input": "test", "output": "result"},
            component_category=ComponentCategoryEnum.TOOL,
            description="Test component mapping",
            version="1.0.0",
        )
        assert valid_data.genesis_type == "genesis:test_component"
        assert valid_data.version == "1.0.0"
        assert valid_data.active is True

    def test_genesis_type_validation(self):
        """Test genesis type validation."""
        # Invalid genesis type - no prefix
        with pytest.raises(ValidationError) as exc_info:
            ComponentMappingCreate(
                genesis_type="test_component",
                component_category=ComponentCategoryEnum.TOOL,
            )
        assert "Genesis type must start with 'genesis:'" in str(exc_info.value)

        # Invalid genesis type - too short
        with pytest.raises(ValidationError) as exc_info:
            ComponentMappingCreate(
                genesis_type="genesis:",
                component_category=ComponentCategoryEnum.TOOL,
            )
        assert "Genesis type must have content after 'genesis:'" in str(exc_info.value)

    def test_version_validation(self):
        """Test version format validation."""
        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "10.20.30"]
        for version in valid_versions:
            data = ComponentMappingCreate(
                genesis_type="genesis:test",
                component_category=ComponentCategoryEnum.TOOL,
                version=version,
            )
            assert data.version == version

        # Invalid versions
        invalid_versions = ["1.0", "1", "1.0.0.1", "v1.0.0", "1.0.0-beta"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                ComponentMappingCreate(
                    genesis_type="genesis:test",
                    component_category=ComponentCategoryEnum.TOOL,
                    version=version,
                )

    def test_json_field_validation(self):
        """Test JSON field validation."""
        # Valid JSON data
        valid_config = {"key": "value", "nested": {"data": 123}}
        data = ComponentMappingCreate(
            genesis_type="genesis:test",
            component_category=ComponentCategoryEnum.TOOL,
            base_config=valid_config,
        )
        assert data.base_config == valid_config

        # Invalid JSON data - non-dict
        with pytest.raises(ValidationError):
            ComponentMappingCreate(
                genesis_type="genesis:test",
                component_category=ComponentCategoryEnum.TOOL,
                base_config="not a dict",
            )

    def test_healthcare_metadata_structure(self):
        """Test healthcare metadata field structure."""
        healthcare_metadata = {
            "hipaa_compliant": True,
            "phi_handling": True,
            "encryption_required": True,
            "audit_trail": True,
            "medical_standards": ["FHIR R4", "HL7 v2.x"],
            "compliance_frameworks": ["HIPAA", "HITECH"],
        }

        data = ComponentMappingCreate(
            genesis_type="genesis:ehr_connector",
            component_category=ComponentCategoryEnum.HEALTHCARE,
            healthcare_metadata=healthcare_metadata,
        )

        assert data.healthcare_metadata["hipaa_compliant"] is True
        assert "FHIR R4" in data.healthcare_metadata["medical_standards"]

    def test_component_category_enum(self):
        """Test component category enumeration."""
        # Test all valid categories
        valid_categories = [
            ComponentCategoryEnum.HEALTHCARE,
            ComponentCategoryEnum.AGENT,
            ComponentCategoryEnum.TOOL,
            ComponentCategoryEnum.DATA,
            ComponentCategoryEnum.PROMPT,
            ComponentCategoryEnum.MEMORY,
            ComponentCategoryEnum.LLM,
            ComponentCategoryEnum.EMBEDDING,
            ComponentCategoryEnum.VECTOR_STORE,
            ComponentCategoryEnum.IO,
            ComponentCategoryEnum.PROCESSING,
            ComponentCategoryEnum.INTEGRATION,
        ]

        for category in valid_categories:
            data = ComponentMappingCreate(
                genesis_type="genesis:test",
                component_category=category,
            )
            assert data.component_category == category

    def test_component_mapping_update_validation(self):
        """Test ComponentMappingUpdate model validation."""
        # Valid update data
        update_data = ComponentMappingUpdate(
            base_config={"updated": True},
            version="1.1.0",
            active=False,
        )
        assert update_data.base_config["updated"] is True
        assert update_data.version == "1.1.0"
        assert update_data.active is False

        # Invalid version in update
        with pytest.raises(ValidationError):
            ComponentMappingUpdate(version="invalid-version")

    def test_default_values(self):
        """Test default values for ComponentMapping fields."""
        data = ComponentMappingCreate(
            genesis_type="genesis:test",
            component_category=ComponentCategoryEnum.TOOL,
        )

        # Test default values
        assert data.version == "1.0.0"
        assert data.active is True
        assert data.base_config is None
        assert data.io_mapping is None
        assert data.healthcare_metadata is None
        assert data.description is None

    def test_datetime_handling(self):
        """Test datetime field handling."""
        # Create with current time
        mapping = ComponentMapping(
            genesis_type="genesis:test",
            component_category=ComponentCategoryEnum.TOOL,
        )

        # Check that timestamps are set
        assert mapping.created_at is not None
        assert mapping.updated_at is not None
        assert isinstance(mapping.created_at, datetime)
        assert isinstance(mapping.updated_at, datetime)

        # Check timezone aware
        assert mapping.created_at.tzinfo is not None
        assert mapping.updated_at.tzinfo is not None

    def test_io_mapping_structure(self):
        """Test I/O mapping field structure."""
        io_mapping = {
            "component": "TestComponent",
            "dataType": "Data",
            "input_field": "input_value",
            "output_field": "output_data",
            "input_types": ["str", "Message"],
            "output_types": ["Data"],
        }

        data = ComponentMappingCreate(
            genesis_type="genesis:test",
            component_category=ComponentCategoryEnum.TOOL,
            io_mapping=io_mapping,
        )

        assert data.io_mapping["component"] == "TestComponent"
        assert data.io_mapping["input_types"] == ["str", "Message"]
        assert data.io_mapping["output_types"] == ["Data"]