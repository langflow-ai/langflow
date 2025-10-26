"""
Tests for Enhanced Validation Framework.
"""

import pytest
from typing import Dict, Any

from langflow.services.runtime.enhanced_validator import (
    EnhancedValidator,
    TypeCompatibilityMatrix,
    ValidationSeverity,
    ValidationType,
    ValidationResult
)


class TestTypeCompatibilityMatrix:
    """Test type compatibility matrix."""

    @pytest.fixture
    def matrix(self):
        """Create type compatibility matrix."""
        return TypeCompatibilityMatrix()

    def test_exact_type_match(self, matrix):
        """Test exact type matching."""
        assert matrix.are_compatible("Message", "Message")
        assert matrix.are_compatible("Data", "Data")
        assert matrix.are_compatible("str", "str")

    def test_message_compatibility(self, matrix):
        """Test Message type compatibility."""
        assert matrix.are_compatible("Message", "str")
        assert matrix.are_compatible("Message", "Text")
        assert matrix.are_compatible("Message", "any")
        assert matrix.are_compatible("Message", "Any")

    def test_data_compatibility(self, matrix):
        """Test Data type compatibility."""
        assert matrix.are_compatible("Data", "Dict")
        assert matrix.are_compatible("Data", "DataFrame")
        assert matrix.are_compatible("Data", "any")

    def test_universal_compatibility(self, matrix):
        """Test universal types (any, Any)."""
        assert matrix.are_compatible("any", "Message")
        assert matrix.are_compatible("any", "Data")
        assert matrix.are_compatible("Any", "str")
        assert matrix.are_compatible("Message", "any")
        assert matrix.are_compatible("Data", "Any")

    def test_incompatible_types(self, matrix):
        """Test incompatible type combinations."""
        # These should return False unless there's explicit compatibility
        assert not matrix.are_compatible("Tool", "Message")  # Unless explicitly defined
        # Note: some combinations might be compatible through 'any' rules

    def test_get_compatible_types(self, matrix):
        """Test getting compatible types."""
        message_compatible = matrix.get_compatible_types("Message")
        assert "str" in message_compatible
        assert "Text" in message_compatible
        assert "any" in message_compatible


class TestEnhancedValidator:
    """Test enhanced validator."""

    @pytest.fixture
    def validator(self):
        """Create enhanced validator."""
        return EnhancedValidator()

    @pytest.fixture
    def valid_spec(self):
        """Create a valid specification."""
        return {
            "name": "Test Agent",
            "description": "Test specification",
            "agentGoal": "Test goal",
            "components": {
                "input": {
                    "type": "genesis:chat_input",
                    "provides": [
                        {"useAs": "input", "in": "agent"}
                    ]
                },
                "agent": {
                    "type": "genesis:agent",
                    "config": {"temperature": 0.7},
                    "provides": [
                        {"useAs": "input", "in": "output"}
                    ]
                },
                "output": {
                    "type": "genesis:chat_output"
                }
            }
        }

    @pytest.fixture
    def invalid_spec(self):
        """Create an invalid specification."""
        return {
            "name": "Invalid Agent",
            # Missing required fields
            "components": {
                "invalid": "not a dict",  # Invalid component structure
                "agent": {
                    # Missing type field
                    "provides": [
                        {"useAs": "input", "in": "nonexistent"}  # Invalid reference
                    ]
                }
            }
        }

    def test_valid_specification(self, validator, valid_spec):
        """Test validation of valid specification."""
        result = validator.validate_specification(valid_spec)

        assert isinstance(result, ValidationResult)
        # Should be valid or have only warnings
        if not result.is_valid:
            errors = [i for i in result.issues if i.severity == ValidationSeverity.ERROR]
            assert len(errors) == 0, f"Unexpected errors: {[e.message for e in errors]}"

    def test_invalid_specification(self, validator, invalid_spec):
        """Test validation of invalid specification."""
        result = validator.validate_specification(invalid_spec)

        assert isinstance(result, ValidationResult)
        assert not result.is_valid
        assert result.errors_count > 0

        # Check for specific error types
        error_codes = [issue.code for issue in result.issues if issue.severity == ValidationSeverity.ERROR]
        assert "MISSING_REQUIRED_FIELD" in error_codes

    def test_structure_validation(self, validator):
        """Test structure validation."""
        # Missing required fields
        spec = {"name": "Test"}
        result = validator.validate_specification(spec)

        assert not result.is_valid
        missing_field_errors = [
            i for i in result.issues
            if i.code == "MISSING_REQUIRED_FIELD"
        ]
        assert len(missing_field_errors) >= 2  # description, agentGoal, components

    def test_component_validation(self, validator):
        """Test component validation."""
        spec = {
            "name": "Test",
            "description": "Test",
            "agentGoal": "Test",
            "components": {
                "invalid_comp": "not a dict",
                "valid_comp": {
                    "type": "genesis:agent"
                },
                "missing_type": {
                    "config": {}
                    # Missing type field
                }
            }
        }

        result = validator.validate_specification(spec)

        # Should have component validation errors
        component_errors = [
            i for i in result.issues
            if i.validation_type == ValidationType.COMPONENT_TYPE
        ]
        assert len(component_errors) >= 2

    def test_type_compatibility_validation(self, validator):
        """Test type compatibility validation."""
        spec = {
            "name": "Test",
            "description": "Test",
            "agentGoal": "Test",
            "components": {
                "input": {
                    "type": "genesis:chat_input",
                    "provides": [
                        {"useAs": "input", "in": "agent"}
                    ]
                },
                "agent": {
                    "type": "genesis:agent",
                    "provides": [
                        {"useAs": "input", "in": "output"}
                    ]
                },
                "output": {
                    "type": "genesis:chat_output"
                }
            }
        }

        result = validator.validate_specification(spec)

        # Should validate type compatibility between components
        type_issues = [
            i for i in result.issues
            if i.validation_type == ValidationType.TYPE_COMPATIBILITY
        ]

        # May have warnings but should be logically compatible
        for issue in type_issues:
            assert issue.severity != ValidationSeverity.ERROR

    def test_relationship_validation(self, validator):
        """Test relationship validation."""
        spec = {
            "name": "Test",
            "description": "Test",
            "agentGoal": "Test",
            "components": {
                "comp1": {
                    "type": "genesis:agent",
                    "provides": [
                        {"useAs": "input", "in": "nonexistent"},  # Invalid reference
                        {"useAs": "input"},  # Missing 'in' field
                        "invalid_provides"  # Invalid provides entry
                    ]
                }
            }
        }

        result = validator.validate_specification(spec)

        relationship_errors = [
            i for i in result.issues
            if i.validation_type == ValidationType.RELATIONSHIP
        ]
        assert len(relationship_errors) >= 2

    def test_configuration_validation(self, validator):
        """Test configuration validation."""
        spec = {
            "name": "Test",
            "description": "Test",
            "agentGoal": "Test",
            "components": {
                "tool_comp": {
                    "type": "genesis:mcp_tool",
                    "asTools": True,
                    "provides": [
                        {"useAs": "tools", "in": "agent"}
                    ]
                },
                "invalid_tool": {
                    "type": "genesis:mcp_tool",
                    "asTools": True,
                    # Missing tool provides relationships
                },
                "invalid_config": {
                    "type": "genesis:agent",
                    "config": "not a dict"  # Invalid config type
                },
                "agent": {
                    "type": "genesis:agent"
                }
            }
        }

        result = validator.validate_specification(spec)

        config_issues = [
            i for i in result.issues
            if i.validation_type == ValidationType.CONFIGURATION
        ]
        assert len(config_issues) >= 1

    def test_runtime_specific_validation(self, validator):
        """Test runtime-specific validation."""
        # Test Temporal constraints
        temporal_spec = {
            "name": "Test",
            "description": "Test",
            "agentGoal": "Test",
            "runMode": "RealTime",  # Not optimal for Temporal
            "components": {"agent": {"type": "genesis:agent"}}
        }

        result = validator.validate_specification(temporal_spec, runtime="temporal")

        temporal_issues = [
            i for i in result.issues
            if i.validation_type == ValidationType.RUNTIME_SPECIFIC and "temporal" in i.message.lower()
        ]
        assert len(temporal_issues) >= 1

        # Test Kafka constraints
        kafka_spec = {
            "name": "Test",
            "description": "Test",
            "agentGoal": "Test",
            "interactionMode": "Batch",  # Not optimal for Kafka
            "components": {"agent": {"type": "genesis:agent"}}
        }

        result = validator.validate_specification(kafka_spec, runtime="kafka")

        kafka_issues = [
            i for i in result.issues
            if i.validation_type == ValidationType.RUNTIME_SPECIFIC and "kafka" in i.message.lower()
        ]
        assert len(kafka_issues) >= 1

    def test_langflow_constraints(self, validator):
        """Test Langflow-specific constraints."""
        spec = {
            "name": "Test",
            "description": "Test",
            "agentGoal": "Test",
            "components": {
                "agent": {
                    "type": "genesis:agent"
                    # Missing input/output components
                }
            }
        }

        result = validator.validate_specification(spec, runtime="langflow")

        langflow_issues = [
            i for i in result.issues
            if i.validation_type == ValidationType.RUNTIME_SPECIFIC and "langflow" in i.code.lower()
        ]
        assert len(langflow_issues) >= 1  # Should warn about missing input/output

    def test_circular_dependency_detection(self, validator):
        """Test circular dependency detection."""
        spec = {
            "name": "Test",
            "description": "Test",
            "agentGoal": "Test",
            "components": {
                "comp1": {
                    "type": "genesis:agent",
                    "provides": [{"useAs": "input", "in": "comp2"}]
                },
                "comp2": {
                    "type": "genesis:agent",
                    "provides": [{"useAs": "input", "in": "comp3"}]
                },
                "comp3": {
                    "type": "genesis:agent",
                    "provides": [{"useAs": "input", "in": "comp1"}]  # Creates cycle
                }
            }
        }

        result = validator.validate_specification(spec)

        circular_errors = [
            i for i in result.issues
            if i.code == "CIRCULAR_DEPENDENCY"
        ]
        assert len(circular_errors) >= 1

    def test_validation_result_properties(self, validator, valid_spec, invalid_spec):
        """Test ValidationResult properties."""
        # Valid spec
        valid_result = validator.validate_specification(valid_spec)
        assert isinstance(valid_result, ValidationResult)
        assert valid_result.errors_count >= 0
        assert valid_result.warnings_count >= 0

        # Invalid spec
        invalid_result = validator.validate_specification(invalid_spec)
        assert isinstance(invalid_result, ValidationResult)
        assert not invalid_result.is_valid
        assert invalid_result.errors_count > 0

    def test_healthcare_workflow_validation(self, validator):
        """Test validation of healthcare-specific workflow."""
        healthcare_spec = {
            "name": "Eligibility Checker",
            "description": "Healthcare eligibility verification",
            "agentGoal": "Verify patient eligibility",
            "domain": "healthcare",
            "components": {
                "input": {
                    "type": "genesis:chat_input",
                    "provides": [{"useAs": "input", "in": "agent"}]
                },
                "eligibility_tool": {
                    "type": "genesis:mcp_tool",
                    "asTools": True,
                    "config": {"tool_name": "eligibility_check"},
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                "agent": {
                    "type": "genesis:agent",
                    "config": {"temperature": 0.7},
                    "provides": [{"useAs": "input", "in": "output"}]
                },
                "output": {
                    "type": "genesis:chat_output"
                }
            }
        }

        result = validator.validate_specification(healthcare_spec)

        # Should validate successfully for healthcare workflows
        assert result.errors_count == 0 or result.is_valid

    def test_multi_tool_agent_validation(self, validator):
        """Test validation of multi-tool agent."""
        multi_tool_spec = {
            "name": "Multi-Tool Agent",
            "description": "Agent with multiple tools",
            "agentGoal": "Use multiple tools",
            "components": {
                "input": {
                    "type": "genesis:chat_input",
                    "provides": [{"useAs": "input", "in": "agent"}]
                },
                "tool1": {
                    "type": "genesis:knowledge_hub_search",
                    "asTools": True,
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                "tool2": {
                    "type": "genesis:mcp_tool",
                    "asTools": True,
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                "tool3": {
                    "type": "genesis:api_request",
                    "asTools": True,
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                "agent": {
                    "type": "genesis:agent",
                    "provides": [{"useAs": "input", "in": "output"}]
                },
                "output": {
                    "type": "genesis:chat_output"
                }
            }
        }

        result = validator.validate_specification(multi_tool_spec)

        # Multi-tool setup should be valid
        critical_errors = [
            i for i in result.issues
            if i.severity == ValidationSeverity.ERROR
        ]
        assert len(critical_errors) == 0


if __name__ == "__main__":
    pytest.main([__file__])