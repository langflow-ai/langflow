"""
Test suite for enhanced Genesis specification validation system.

This module provides comprehensive tests for the enhanced validation capabilities,
including JSON Schema validation, semantic validation, and error reporting.
"""

import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock

from langflow.services.spec.service import SpecService
from langflow.services.spec.validation_schemas import GENESIS_SPEC_SCHEMA
from langflow.services.spec.semantic_validator import SemanticValidator, SemanticValidationResult


class TestJSONSchemaValidation:
    """Test JSON Schema validation for Genesis specifications."""

    @pytest.fixture
    def spec_service(self):
        """Create SpecService instance for testing."""
        service = SpecService()
        service.get_all_available_components = AsyncMock(return_value={
            "genesis_mapped": {
                "genesis:agent": {"component": "Agent"},
                "genesis:chat_input": {"component": "ChatInput"},
                "genesis:chat_output": {"component": "ChatOutput"}
            }
        })
        return service

    def test_valid_minimal_spec(self, spec_service):
        """Test validation of a minimal valid specification."""
        valid_spec = {
            "id": "urn:agent:genesis:autonomize.ai:test-agent:1.0.0",
            "name": "Test Agent",
            "description": "A test agent for validation testing",
            "kind": "Single Agent",
            "agentGoal": "Test agent functionality and validation",
            "components": {
                "input": {
                    "name": "Input",
                    "type": "genesis:chat_input",
                    "kind": "Data"
                },
                "agent": {
                    "name": "Main Agent",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "provides": [{
                        "useAs": "input",
                        "in": "output"
                    }]
                },
                "output": {
                    "name": "Output",
                    "type": "genesis:chat_output",
                    "kind": "Data"
                }
            }
        }

        spec_yaml = yaml.dump(valid_spec)
        result = spec_service._validate_json_schema(valid_spec)

        assert len(result["errors"]) == 0
        assert result.get("warnings", []) == []

    def test_missing_required_fields(self, spec_service):
        """Test validation with missing required fields."""
        invalid_spec = {
            "name": "Test Agent",
            # Missing: id, description, kind, agentGoal, components
        }

        result = spec_service._validate_json_schema(invalid_spec)
        assert len(result["errors"]) > 0

        error_messages = " ".join(result["errors"])
        assert "required" in error_messages.lower()

    def test_invalid_urn_format(self, spec_service):
        """Test validation with invalid URN format."""
        invalid_spec = {
            "id": "invalid-urn-format",
            "name": "Test Agent",
            "description": "A test agent",
            "kind": "Single Agent",
            "agentGoal": "Test agent",
            "components": {}
        }

        result = spec_service._validate_json_schema(invalid_spec)
        assert len(result["errors"]) > 0

        error_messages = " ".join(result["errors"])
        assert "pattern" in error_messages.lower() or "format" in error_messages.lower()

    def test_invalid_component_type(self, spec_service):
        """Test validation with invalid component type."""
        invalid_spec = {
            "id": "urn:agent:genesis:autonomize.ai:test-agent:1.0.0",
            "name": "Test Agent",
            "description": "A test agent",
            "kind": "Single Agent",
            "agentGoal": "Test agent",
            "components": {
                "invalid": {
                    "name": "Invalid Component",
                    "type": "invalid_type",  # Should start with genesis:
                    "kind": "Data"
                }
            }
        }

        result = spec_service._validate_json_schema(invalid_spec)
        assert len(result["errors"]) > 0

    def test_component_config_validation(self, spec_service):
        """Test validation of component configurations."""
        spec_with_config = {
            "id": "urn:agent:genesis:autonomize.ai:test-agent:1.0.0",
            "name": "Test Agent",
            "description": "A test agent",
            "kind": "Single Agent",
            "agentGoal": "Test agent",
            "components": {
                "agent": {
                    "name": "Test Agent",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "config": {
                        "temperature": 2.5,  # Invalid: should be <= 2.0
                        "max_tokens": "invalid"  # Invalid: should be integer
                    }
                }
            }
        }

        result = spec_service._validate_json_schema(spec_with_config)
        # Should have config validation errors
        config_errors = [e for e in result["errors"] if "config" in e.lower()]
        assert len(config_errors) > 0


class TestSemanticValidation:
    """Test semantic validation for Genesis specifications."""

    @pytest.fixture
    def semantic_validator(self):
        """Create SemanticValidator instance for testing."""
        mapper_mock = MagicMock()
        return SemanticValidator(mapper_mock)

    def test_valid_single_agent_workflow(self, semantic_validator):
        """Test validation of a valid single agent workflow."""
        valid_spec = {
            "kind": "Single Agent",
            "agentGoal": "Process user queries",
            "components": {
                "input": {
                    "id": "input",
                    "name": "Input",
                    "type": "genesis:chat_input",
                    "kind": "Data",
                    "provides": [{
                        "useAs": "input",
                        "in": "agent"
                    }]
                },
                "agent": {
                    "id": "agent",
                    "name": "Main Agent",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "provides": [{
                        "useAs": "input",
                        "in": "output"
                    }]
                },
                "output": {
                    "id": "output",
                    "name": "Output",
                    "type": "genesis:chat_output",
                    "kind": "Data"
                }
            }
        }

        result = semantic_validator.validate(valid_spec)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_agent_in_single_workflow(self, semantic_validator):
        """Test validation when single agent workflow has no agents."""
        invalid_spec = {
            "kind": "Single Agent",
            "agentGoal": "Process user queries",
            "components": {
                "input": {
                    "id": "input",
                    "name": "Input",
                    "type": "genesis:chat_input",
                    "kind": "Data"
                },
                "output": {
                    "id": "output",
                    "name": "Output",
                    "type": "genesis:chat_output",
                    "kind": "Data"
                }
            }
        }

        result = semantic_validator.validate(invalid_spec)
        assert not result.is_valid

        # Should have error about missing agent
        agent_errors = [e for e in result.errors if "agent" in e.get("message", "").lower()]
        assert len(agent_errors) > 0

    def test_circular_dependency_detection(self, semantic_validator):
        """Test detection of circular dependencies."""
        spec_with_cycle = {
            "kind": "Single Agent",
            "agentGoal": "Test circular dependencies",
            "components": {
                "comp1": {
                    "id": "comp1",
                    "name": "Component 1",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "provides": [{
                        "useAs": "input",
                        "in": "comp2"
                    }]
                },
                "comp2": {
                    "id": "comp2",
                    "name": "Component 2",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "provides": [{
                        "useAs": "input",
                        "in": "comp1"  # Creates cycle
                    }]
                }
            }
        }

        result = semantic_validator.validate(spec_with_cycle)
        assert not result.is_valid

        # Should detect circular dependency
        circular_errors = [e for e in result.errors if "circular" in e.get("message", "").lower()]
        assert len(circular_errors) > 0

    def test_crewai_workflow_validation(self, semantic_validator):
        """Test validation of CrewAI multi-agent workflow."""
        crewai_spec = {
            "kind": "Multi Agent",
            "agentGoal": "Collaborative task processing",
            "components": {
                "agent1": {
                    "id": "agent1",
                    "name": "Research Agent",
                    "type": "genesis:crewai_agent",
                    "kind": "Agent",
                    "config": {
                        "role": "Researcher",
                        "goal": "Research information",
                        "backstory": "Expert researcher"
                    }
                },
                "agent2": {
                    "id": "agent2",
                    "name": "Writer Agent",
                    "type": "genesis:crewai_agent",
                    "kind": "Agent",
                    "config": {
                        "role": "Writer",
                        "goal": "Write content",
                        "backstory": "Professional writer"
                    }
                },
                "task1": {
                    "id": "task1",
                    "name": "Research Task",
                    "type": "genesis:crewai_sequential_task",
                    "kind": "Agent",
                    "config": {
                        "description": "Research the topic",
                        "expected_output": "Research report",
                        "agent_id": "agent1"
                    }
                },
                "crew": {
                    "id": "crew",
                    "name": "Research Crew",
                    "type": "genesis:crewai_sequential_crew",
                    "kind": "Agent",
                    "config": {
                        "agents": ["agent1", "agent2"],
                        "tasks": ["task1"]
                    }
                }
            }
        }

        result = semantic_validator.validate(crewai_spec)
        assert result.is_valid or len(result.errors) == 0  # Should be valid or have minor warnings

    def test_invalid_tool_connection(self, semantic_validator):
        """Test validation of invalid tool connections."""
        invalid_tool_spec = {
            "kind": "Single Agent",
            "agentGoal": "Test tool connections",
            "components": {
                "non_tool": {
                    "id": "non_tool",
                    "name": "Non-Tool Component",
                    "type": "genesis:chat_input",
                    "kind": "Data",
                    "provides": [{
                        "useAs": "tools",  # Invalid: chat_input can't be a tool
                        "in": "agent"
                    }]
                },
                "agent": {
                    "id": "agent",
                    "name": "Agent",
                    "type": "genesis:agent",
                    "kind": "Agent"
                }
            }
        }

        result = semantic_validator.validate(invalid_tool_spec)
        assert not result.is_valid

        # Should have tool connection error
        tool_errors = [e for e in result.errors if "tool" in e.get("message", "").lower()]
        assert len(tool_errors) > 0

    def test_orphaned_components_detection(self, semantic_validator):
        """Test detection of orphaned components."""
        spec_with_orphan = {
            "kind": "Single Agent",
            "agentGoal": "Test orphaned components",
            "components": {
                "input": {
                    "id": "input",
                    "name": "Input",
                    "type": "genesis:chat_input",
                    "kind": "Data"
                },
                "orphan": {
                    "id": "orphan",
                    "name": "Orphaned Component",
                    "type": "genesis:agent",
                    "kind": "Agent"
                    # No provides, not connected
                },
                "output": {
                    "id": "output",
                    "name": "Output",
                    "type": "genesis:chat_output",
                    "kind": "Data"
                }
            }
        }

        result = semantic_validator.validate(spec_with_orphan)
        # Should have warning about orphaned component
        orphan_warnings = [w for w in result.warnings if "orphan" in w.get("message", "").lower()]
        assert len(orphan_warnings) > 0


class TestComprehensiveValidation:
    """Test the comprehensive validation system integration."""

    @pytest.fixture
    def spec_service(self):
        """Create SpecService instance for testing."""
        service = SpecService()
        service.get_all_available_components = AsyncMock(return_value={
            "genesis_mapped": {
                "genesis:agent": {"component": "Agent"},
                "genesis:chat_input": {"component": "ChatInput"},
                "genesis:chat_output": {"component": "ChatOutput"},
                "genesis:crewai_agent": {"component": "CrewAIAgentComponent"},
                "genesis:crewai_sequential_task": {"component": "CrewAIAgentComponent"},
                "genesis:crewai_sequential_crew": {"component": "CrewAIAgentComponent"}
            }
        })
        return service

    @pytest.mark.asyncio
    async def test_comprehensive_validation_valid_spec(self, spec_service):
        """Test comprehensive validation with a valid specification."""
        valid_spec_yaml = """
id: urn:agent:genesis:autonomize.ai:test-agent:1.0.0
name: Test Agent
description: A comprehensive test agent for validation testing
kind: Single Agent
agentGoal: Process user queries and provide helpful responses
targetUser: internal
valueGeneration: ProcessAutomation
toolsUse: false
components:
  input:
    name: Chat Input
    type: genesis:chat_input
    kind: Data
    provides:
      - useAs: input
        in: agent
        description: User input to the agent
  agent:
    name: Main Agent
    type: genesis:agent
    kind: Agent
    config:
      temperature: 0.7
      max_tokens: 1000
    provides:
      - useAs: input
        in: output
        description: Agent response to output
  output:
    name: Chat Output
    type: genesis:chat_output
    kind: Data
"""

        result = await spec_service.validate_spec(valid_spec_yaml, detailed=True)

        assert result["valid"]
        assert result["summary"]["error_count"] == 0
        assert all(phase for phase in result["validation_phases"].values() if phase is not None)

    @pytest.mark.asyncio
    async def test_comprehensive_validation_invalid_spec(self, spec_service):
        """Test comprehensive validation with an invalid specification."""
        invalid_spec_yaml = """
# Missing required fields: id, description, agentGoal
name: Invalid Agent
kind: Single Agent
components:
  invalid_component:
    name: Invalid Component
    type: invalid_type  # Invalid type
    kind: Data
"""

        result = await spec_service.validate_spec(invalid_spec_yaml, detailed=True)

        assert not result["valid"]
        assert result["summary"]["error_count"] > 0

        # Should have multiple types of errors
        error_codes = [error.get("code", "") for error in result["errors"]]
        assert len(set(error_codes)) > 1  # Multiple different error types

    @pytest.mark.asyncio
    async def test_validation_error_suggestions(self, spec_service):
        """Test that validation provides helpful suggestions."""
        spec_with_issues_yaml = """
id: urn:agent:genesis:autonomize.ai:test:1.0.0
name: Test Agent
description: Test
kind: Single Agent
agentGoal: Test goals and provide suggestions
toolsUse: true  # Says uses tools but no tools defined
components:
  input:
    name: Input
    type: genesis:chat_input
    kind: Data
  agent:
    name: Agent
    type: genesis:agent
    kind: Agent
    # No provides - disconnected
  output:
    name: Output
    type: genesis:chat_output
    kind: Data
    # No input connections
"""

        result = await spec_service.validate_spec(spec_with_issues_yaml, detailed=True)

        # Should have suggestions for improvements
        suggestions = spec_service.get_validation_suggestions(result)
        assert len(suggestions) > 0

        # Should provide actionable suggestions
        suggestion_text = " ".join(suggestions).lower()
        assert any(keyword in suggestion_text for keyword in ["add", "connect", "set", "use", "consider"])

    @pytest.mark.asyncio
    async def test_quick_validation_mode(self, spec_service):
        """Test quick validation mode for real-time feedback."""
        spec_yaml = """
id: urn:agent:genesis:autonomize.ai:test:1.0.0
name: Test Agent
description: Test agent
kind: Single Agent
agentGoal: Test
components:
  input:
    name: Input
    type: genesis:chat_input
    kind: Data
"""

        # Quick validation should be faster and less comprehensive
        result = await spec_service.validate_spec_quick(spec_yaml)

        # Should have validation phases but semantic validation should be None
        phases = result.get("validation_phases", {})
        assert phases.get("semantic_validation") is None  # Not performed in quick mode

    def test_validation_report_formatting(self, spec_service):
        """Test validation report formatting."""
        mock_result = {
            "valid": False,
            "errors": [
                {
                    "code": "MISSING_FIELD",
                    "message": "Missing required field: id",
                    "severity": "error",
                    "suggestion": "Add unique ID in URN format"
                }
            ],
            "warnings": [
                {
                    "code": "TOOL_MISMATCH",
                    "message": "toolsUse is true but no tools found",
                    "severity": "warning",
                    "component_id": "agent",
                    "suggestion": "Add tool components or set toolsUse to false"
                }
            ],
            "suggestions": [
                {
                    "code": "OPTIMIZATION",
                    "message": "Consider using CrewAI for multi-agent workflows",
                    "action": "Use genesis:crewai_agent components"
                }
            ],
            "summary": {
                "error_count": 1,
                "warning_count": 1,
                "suggestion_count": 1
            },
            "validation_phases": {
                "schema_validation": False,
                "structure_validation": True,
                "component_validation": True,
                "type_validation": True,
                "semantic_validation": True
            }
        }

        report = spec_service.format_validation_report(mock_result)

        # Should contain all sections
        assert "validation failed" in report.lower()
        assert "summary:" in report.lower()
        assert "validation phases:" in report.lower()
        assert "errors:" in report.lower()
        assert "warnings:" in report.lower()
        assert "suggestions:" in report.lower()

        # Should contain specific content
        assert "Missing required field: id" in report
        assert "Add unique ID in URN format" in report
        assert "[agent]" in report  # Component context


@pytest.mark.integration
class TestValidationIntegration:
    """Integration tests for the validation system."""

    @pytest.fixture
    def spec_service(self):
        """Create real SpecService instance for integration testing."""
        return SpecService()

    @pytest.mark.asyncio
    async def test_end_to_end_validation_workflow(self, spec_service):
        """Test complete validation workflow from YAML to formatted report."""
        # Realistic specification with various issues
        realistic_spec_yaml = """
id: urn:agent:genesis:autonomize.ai:patient-care-agent:1.0.0
name: Patient Care Coordination Agent
description: An agent that helps coordinate patient care by integrating with EHR systems and managing appointments
domain: autonomize.ai
subDomain: patient-experience
version: 1.0.0
environment: production
agentOwner: healthcare-team@autonomize.ai
agentOwnerDisplayName: Healthcare Team
status: ACTIVE
kind: Multi Agent
agentGoal: Coordinate comprehensive patient care by managing appointments, accessing medical records, and facilitating communication between healthcare providers
targetUser: internal
valueGeneration: ProcessAutomation
interactionMode: RequestResponse
runMode: RealTime
toolsUse: true
learningCapability: None
securityInfo:
  visibility: Private
  confidentiality: High
  hipaaCompliant: true
components:
  input:
    name: Patient Input
    type: genesis:chat_input
    kind: Data
    description: Patient queries and care coordination requests
    provides:
      - useAs: input
        in: care-coordinator
        description: Patient input to coordination agent
  care-coordinator:
    name: Care Coordination Agent
    type: genesis:crewai_agent
    kind: Agent
    description: Main agent for coordinating patient care
    config:
      role: Care Coordinator
      goal: Coordinate patient care activities and manage healthcare workflows
      backstory: Experienced healthcare coordinator with deep knowledge of medical systems
      verbose: false
      allow_delegation: true
    provides:
      - useAs: input
        in: output
        description: Coordination results to output
  ehr-tool:
    name: EHR Integration Tool
    type: genesis:mcp_tool
    kind: Tool
    description: Tool for accessing electronic health records
    asTools: true
    config:
      tool_name: ehr_patient_records
      description: Access patient records from EHR system
    provides:
      - useAs: tools
        in: care-coordinator
        description: EHR access capability for the coordination agent
  output:
    name: Care Output
    type: genesis:chat_output
    kind: Data
    description: Care coordination results and next steps
tags:
  - healthcare
  - patient-care
  - coordination
  - ehr-integration
kpis:
  - name: Response Time
    category: performance
    valueType: duration
    target: 30
    unit: seconds
    description: Time to process care coordination requests
  - name: Care Accuracy
    category: quality
    valueType: percentage
    target: 95
    unit: percent
    description: Accuracy of care coordination recommendations
"""

        # Perform comprehensive validation
        result = await spec_service.validate_spec(realistic_spec_yaml, detailed=True)

        # Generate formatted report
        report = spec_service.format_validation_report(result)

        # Validate that the system can handle a realistic specification
        assert isinstance(result, dict)
        assert "valid" in result
        assert "summary" in result
        assert isinstance(report, str)
        assert len(report) > 0

        # Should provide useful feedback
        if not result["valid"]:
            assert len(result["errors"]) > 0
            suggestions = spec_service.get_validation_suggestions(result)
            assert len(suggestions) > 0

    @pytest.mark.asyncio
    async def test_validation_performance(self, spec_service):
        """Test validation performance with larger specifications."""
        import time

        # Create a larger specification with many components
        large_spec_components = {}
        for i in range(50):  # 50 components
            large_spec_components[f"comp_{i}"] = {
                "name": f"Component {i}",
                "type": "genesis:agent" if i % 5 == 0 else "genesis:mcp_tool",
                "kind": "Agent" if i % 5 == 0 else "Tool",
                "provides": [{
                    "useAs": "input",
                    "in": f"comp_{(i + 1) % 50}"
                }] if i < 49 else []
            }

        large_spec = {
            "id": "urn:agent:genesis:autonomize.ai:large-test:1.0.0",
            "name": "Large Test Specification",
            "description": "A large specification for performance testing",
            "kind": "Multi Agent",
            "agentGoal": "Test performance with many components",
            "components": large_spec_components
        }

        large_spec_yaml = yaml.dump(large_spec)

        # Measure validation time
        start_time = time.time()
        result = await spec_service.validate_spec(large_spec_yaml, detailed=True)
        validation_time = time.time() - start_time

        # Should complete within reasonable time (< 5 seconds for 50 components)
        assert validation_time < 5.0
        assert isinstance(result, dict)
        assert "valid" in result