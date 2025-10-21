"""Tests for runtime adapter database models."""

import pytest
from datetime import datetime

from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapter,
    RuntimeAdapterCreate,
    RuntimeAdapterUpdate,
    RuntimeTypeEnum,
)
from pydantic import ValidationError


class TestRuntimeAdapterModel:
    """Test RuntimeAdapter model validation and functionality."""

    def test_runtime_adapter_basic_validation(self):
        """Test basic validation of RuntimeAdapter model."""
        # Valid data
        valid_data = RuntimeAdapterCreate(
            genesis_type="genesis:test_component",
            runtime_type=RuntimeTypeEnum.LANGFLOW,
            target_component="TestComponent",
            adapter_config={"key": "value"},
            version="1.0.0",
        )
        assert valid_data.genesis_type == "genesis:test_component"
        assert valid_data.runtime_type == RuntimeTypeEnum.LANGFLOW
        assert valid_data.target_component == "TestComponent"

    def test_genesis_type_validation(self):
        """Test genesis type validation."""
        # Invalid genesis type - no prefix
        with pytest.raises(ValidationError) as exc_info:
            RuntimeAdapterCreate(
                genesis_type="test_component",
                runtime_type=RuntimeTypeEnum.LANGFLOW,
                target_component="TestComponent",
            )
        assert "Genesis type must start with 'genesis:'" in str(exc_info.value)

    def test_target_component_validation(self):
        """Test target component validation."""
        # Valid target component
        data = RuntimeAdapterCreate(
            genesis_type="genesis:test",
            runtime_type=RuntimeTypeEnum.LANGFLOW,
            target_component="ValidComponent",
        )
        assert data.target_component == "ValidComponent"

        # Empty target component
        with pytest.raises(ValidationError) as exc_info:
            RuntimeAdapterCreate(
                genesis_type="genesis:test",
                runtime_type=RuntimeTypeEnum.LANGFLOW,
                target_component="",
            )
        assert "Target component name cannot be empty" in str(exc_info.value)

        # Whitespace-only target component
        with pytest.raises(ValidationError):
            RuntimeAdapterCreate(
                genesis_type="genesis:test",
                runtime_type=RuntimeTypeEnum.LANGFLOW,
                target_component="   ",
            )

    def test_runtime_type_enum(self):
        """Test runtime type enumeration."""
        # Test all valid runtime types
        valid_runtimes = [
            RuntimeTypeEnum.LANGFLOW,
            RuntimeTypeEnum.TEMPORAL,
            RuntimeTypeEnum.KAFKA,
            RuntimeTypeEnum.AIRFLOW,
            RuntimeTypeEnum.DAGSTER,
        ]

        for runtime in valid_runtimes:
            data = RuntimeAdapterCreate(
                genesis_type="genesis:test",
                runtime_type=runtime,
                target_component="TestComponent",
            )
            assert data.runtime_type == runtime

    def test_version_validation(self):
        """Test version format validation."""
        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "10.20.30"]
        for version in valid_versions:
            data = RuntimeAdapterCreate(
                genesis_type="genesis:test",
                runtime_type=RuntimeTypeEnum.LANGFLOW,
                target_component="TestComponent",
                version=version,
            )
            assert data.version == version

        # Invalid versions
        invalid_versions = ["1.0", "1", "1.0.0.1", "v1.0.0"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                RuntimeAdapterCreate(
                    genesis_type="genesis:test",
                    runtime_type=RuntimeTypeEnum.LANGFLOW,
                    target_component="TestComponent",
                    version=version,
                )

    def test_priority_validation(self):
        """Test priority validation."""
        # Valid priority values
        valid_priorities = [0, 1, 50, 100, 999]
        for priority in valid_priorities:
            data = RuntimeAdapterCreate(
                genesis_type="genesis:test",
                runtime_type=RuntimeTypeEnum.LANGFLOW,
                target_component="TestComponent",
                priority=priority,
            )
            assert data.priority == priority

        # Invalid priority (negative)
        with pytest.raises(ValidationError) as exc_info:
            RuntimeAdapterCreate(
                genesis_type="genesis:test",
                runtime_type=RuntimeTypeEnum.LANGFLOW,
                target_component="TestComponent",
                priority=-1,
            )
        assert "Priority must be non-negative" in str(exc_info.value)

    def test_adapter_config_validation(self):
        """Test adapter configuration validation."""
        # Valid adapter config
        valid_config = {
            "component_class": "TestComponent",
            "input_mapping": {"input": "value"},
            "output_mapping": {"output": "result"},
        }

        data = RuntimeAdapterCreate(
            genesis_type="genesis:test",
            runtime_type=RuntimeTypeEnum.LANGFLOW,
            target_component="TestComponent",
            adapter_config=valid_config,
        )
        assert data.adapter_config == valid_config

        # Invalid adapter config - non-dict
        with pytest.raises(ValidationError):
            RuntimeAdapterCreate(
                genesis_type="genesis:test",
                runtime_type=RuntimeTypeEnum.LANGFLOW,
                target_component="TestComponent",
                adapter_config="not a dict",
            )

    def test_compliance_rules_validation(self):
        """Test compliance rules validation."""
        # Valid compliance rules
        valid_rules = {
            "minimum_log_level": "INFO",
            "phi_encryption": True,
            "access_control": "RBAC",
            "audit_retention_days": 2555,
        }

        data = RuntimeAdapterCreate(
            genesis_type="genesis:test",
            runtime_type=RuntimeTypeEnum.LANGFLOW,
            target_component="TestComponent",
            compliance_rules=valid_rules,
        )
        assert data.compliance_rules == valid_rules

    def test_healthcare_adapter_config(self):
        """Test healthcare-specific adapter configuration."""
        healthcare_config = {
            "component_class": "EHRConnector",
            "input_mapping": {
                "patient_query": "input_value",
            },
            "output_mapping": {
                "ehr_data": "data",
            },
            "healthcare_specific": {
                "phi_fields": ["patient_id", "patient_name", "dob"],
                "encryption_fields": ["ssn", "patient_data"],
                "audit_actions": ["read", "write", "search"],
            },
        }

        compliance_rules = {
            "minimum_log_level": "INFO",
            "phi_encryption": True,
            "access_control": "RBAC",
            "audit_retention_days": 2555,
            "data_masking": True,
        }

        data = RuntimeAdapterCreate(
            genesis_type="genesis:ehr_connector",
            runtime_type=RuntimeTypeEnum.LANGFLOW,
            target_component="EHRConnector",
            adapter_config=healthcare_config,
            compliance_rules=compliance_rules,
        )

        assert data.adapter_config["healthcare_specific"]["phi_fields"] == [
            "patient_id", "patient_name", "dob"
        ]
        assert data.compliance_rules["phi_encryption"] is True

    def test_runtime_adapter_update_validation(self):
        """Test RuntimeAdapterUpdate model validation."""
        # Valid update data
        update_data = RuntimeAdapterUpdate(
            target_component="UpdatedComponent",
            version="1.1.0",
            priority=50,
            active=False,
        )
        assert update_data.target_component == "UpdatedComponent"
        assert update_data.version == "1.1.0"
        assert update_data.priority == 50

        # Invalid version in update
        with pytest.raises(ValidationError):
            RuntimeAdapterUpdate(version="invalid-version")

        # Invalid priority in update
        with pytest.raises(ValidationError):
            RuntimeAdapterUpdate(priority=-5)

    def test_default_values(self):
        """Test default values for RuntimeAdapter fields."""
        data = RuntimeAdapterCreate(
            genesis_type="genesis:test",
            runtime_type=RuntimeTypeEnum.LANGFLOW,
            target_component="TestComponent",
        )

        # Test default values
        assert data.version == "1.0.0"
        assert data.priority == 100
        assert data.active is True
        assert data.adapter_config is None
        assert data.compliance_rules is None
        assert data.description is None

    def test_datetime_handling(self):
        """Test datetime field handling."""
        # Create with current time
        adapter = RuntimeAdapter(
            genesis_type="genesis:test",
            runtime_type=RuntimeTypeEnum.LANGFLOW,
            target_component="TestComponent",
        )

        # Check that timestamps are set
        assert adapter.created_at is not None
        assert adapter.updated_at is not None
        assert isinstance(adapter.created_at, datetime)
        assert isinstance(adapter.updated_at, datetime)

    def test_target_component_whitespace_handling(self):
        """Test target component whitespace trimming."""
        # Test whitespace trimming in validation
        data = RuntimeAdapterCreate(
            genesis_type="genesis:test",
            runtime_type=RuntimeTypeEnum.LANGFLOW,
            target_component="  TestComponent  ",
        )
        assert data.target_component == "TestComponent"