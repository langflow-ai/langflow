"""Tests for Genesis Spec Models."""

import pytest
from pydantic import ValidationError
from langflow.custom.genesis.spec.models import (
    ComponentProvides,
    Component,
    Variable,
    KPI,
    SecurityInfo,
    ReusabilityInfo,
    AgentSpec,
)


class TestComponentProvides:
    """Test ComponentProvides model."""

    def test_component_provides_creation(self):
        """Test valid ComponentProvides creation."""
        provides = ComponentProvides(
            useAs="tools",
            in_="agent-main",
            description="Tool connection",
            fromOutput="tool_output"
        )
        assert provides.useAs == "tools"
        assert provides.in_ == "agent-main"
        assert provides.description == "Tool connection"
        assert provides.fromOutput == "tool_output"

    def test_component_provides_alias_in(self):
        """Test that 'in' field works as alias."""
        provides = ComponentProvides(useAs="input", **{"in": "target-component"})
        assert provides.in_ == "target-component"

    def test_component_provides_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            ComponentProvides(useAs="tools")  # Missing 'in' field

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("in",) for error in errors)

    def test_component_provides_optional_fields(self):
        """Test optional fields default to None."""
        provides = ComponentProvides(useAs="tools", in_="target")
        assert provides.description is None
        assert provides.fromOutput is None


class TestComponent:
    """Test Component model."""

    def test_component_creation(self):
        """Test valid Component creation."""
        component = Component(
            id="test-tool",
            name="Test Tool",
            kind="Tool",
            type="genesis:calculator",
            description="A test tool",
            config={"param1": "value1"},
            asTools=True,
            modelEndpoint="http://example.com"
        )
        assert component.id == "test-tool"
        assert component.name == "Test Tool"
        assert component.kind == "Tool"
        assert component.type == "genesis:calculator"
        assert component.description == "A test tool"
        assert component.config == {"param1": "value1"}
        assert component.asTools is True
        assert component.modelEndpoint == "http://example.com"

    def test_component_with_provides(self):
        """Test Component with provides relationships."""
        provides = [
            ComponentProvides(useAs="tools", in_="agent-main"),
            ComponentProvides(useAs="input", in_="output-component")
        ]
        component = Component(
            id="test-tool",
            name="Test Tool",
            kind="Tool",
            type="genesis:calculator",
            provides=provides
        )
        assert len(component.provides) == 2
        assert component.provides[0].useAs == "tools"
        assert component.provides[1].in_ == "output-component"

    def test_component_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            Component(name="Test Tool", kind="Tool")  # Missing id and type

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)
        assert any(error["loc"] == ("type",) for error in errors)

    def test_component_defaults(self):
        """Test default values for optional fields."""
        component = Component(
            id="test-tool",
            name="Test Tool",
            kind="Tool",
            type="genesis:calculator"
        )
        assert component.description is None
        assert component.config is None
        assert component.provides is None
        assert component.asTools is False
        assert component.modelEndpoint is None


class TestVariable:
    """Test Variable model."""

    def test_variable_creation(self):
        """Test valid Variable creation."""
        variable = Variable(
            name="api_key",
            type="string",
            required=True,
            default="default_value",
            description="API key for external service"
        )
        assert variable.name == "api_key"
        assert variable.type == "string"
        assert variable.required is True
        assert variable.default == "default_value"
        assert variable.description == "API key for external service"

    def test_variable_defaults(self):
        """Test default values."""
        variable = Variable(name="test_var")
        assert variable.type == "string"
        assert variable.required is False
        assert variable.default is None
        assert variable.description is None

    def test_variable_types(self):
        """Test different variable types."""
        int_var = Variable(name="count", type="integer", default=10)
        bool_var = Variable(name="enabled", type="boolean", default=True)

        assert int_var.type == "integer"
        assert int_var.default == 10
        assert bool_var.type == "boolean"
        assert bool_var.default is True


class TestKPI:
    """Test KPI model."""

    def test_kpi_creation(self):
        """Test valid KPI creation."""
        kpi = KPI(
            name="Response Time",
            category="Performance",
            valueType="number",
            target=100,
            unit="ms",
            description="Average response time"
        )
        assert kpi.name == "Response Time"
        assert kpi.category == "Performance"
        assert kpi.valueType == "number"
        assert kpi.target == 100
        assert kpi.unit == "ms"
        assert kpi.description == "Average response time"

    def test_kpi_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            KPI(name="Test KPI")  # Missing required fields

        errors = exc_info.value.errors()
        required_fields = {error["loc"][0] for error in errors}
        assert "category" in required_fields
        assert "valueType" in required_fields
        assert "target" in required_fields


class TestSecurityInfo:
    """Test SecurityInfo model."""

    def test_security_info_defaults(self):
        """Test default security values."""
        security = SecurityInfo()
        assert security.visibility == "Private"
        assert security.confidentiality == "High"
        assert security.gdprSensitive is False

    def test_security_info_custom_values(self):
        """Test custom security values."""
        security = SecurityInfo(
            visibility="Public",
            confidentiality="Low",
            gdprSensitive=True
        )
        assert security.visibility == "Public"
        assert security.confidentiality == "Low"
        assert security.gdprSensitive is True


class TestReusabilityInfo:
    """Test ReusabilityInfo model."""

    def test_reusability_info_defaults(self):
        """Test default reusability values."""
        reusability = ReusabilityInfo()
        assert reusability.asTools is False
        assert reusability.standalone is True
        assert reusability.provides is None
        assert reusability.dependencies is None

    def test_reusability_info_with_data(self):
        """Test reusability info with custom data."""
        reusability = ReusabilityInfo(
            asTools=True,
            standalone=False,
            provides={"output": "data"},
            dependencies=[{"type": "service", "name": "database"}]
        )
        assert reusability.asTools is True
        assert reusability.standalone is False
        assert reusability.provides == {"output": "data"}
        assert len(reusability.dependencies) == 1
        assert reusability.dependencies[0]["type"] == "service"


class TestAgentSpec:
    """Test AgentSpec model."""

    @pytest.fixture
    def minimal_agent_spec_data(self):
        """Minimal data for creating AgentSpec."""
        return {
            "id": "test-agent",
            "name": "Test Agent",
            "description": "A test agent",
            "components": [
                {
                    "id": "test-tool",
                    "name": "Test Tool",
                    "kind": "Tool",
                    "type": "genesis:calculator"
                }
            ]
        }

    @pytest.fixture
    def complete_agent_spec_data(self):
        """Complete data for creating AgentSpec."""
        return {
            "id": "complete-agent",
            "name": "Complete Test Agent",
            "fullyQualifiedName": "com.example.complete-agent",
            "description": "A complete test agent",
            "domain": "Healthcare",
            "subDomain": "Diagnostics",
            "version": "2.0.0",
            "environment": "staging",
            "agentOwner": "test-team",
            "agentGoal": "Process medical data",
            "components": [
                {
                    "id": "tool-1",
                    "name": "Tool 1",
                    "kind": "Tool",
                    "type": "genesis:calculator",
                    "asTools": True,
                    "provides": [
                        {"useAs": "tools", "in": "agent-main"}
                    ]
                },
                {
                    "id": "agent-main",
                    "name": "Main Agent",
                    "kind": "Agent",
                    "type": "genesis:agent"
                }
            ],
            "variables": [
                {
                    "name": "api_key",
                    "type": "string",
                    "required": True,
                    "description": "API key"
                }
            ],
            "kpis": [
                {
                    "name": "Accuracy",
                    "category": "Quality",
                    "valueType": "percentage",
                    "target": 95
                }
            ],
            "security": {
                "visibility": "Internal",
                "confidentiality": "Medium",
                "gdprSensitive": True
            },
            "reusability": {
                "asTools": True,
                "standalone": True
            }
        }

    def test_agent_spec_minimal(self, minimal_agent_spec_data):
        """Test AgentSpec with minimal required data."""
        spec = AgentSpec(**minimal_agent_spec_data)
        assert spec.id == "test-agent"
        assert spec.name == "Test Agent"
        assert spec.description == "A test agent"
        assert len(spec.components) == 1
        assert spec.components[0].id == "test-tool"

    def test_agent_spec_complete(self, complete_agent_spec_data):
        """Test AgentSpec with complete data."""
        spec = AgentSpec(**complete_agent_spec_data)
        assert spec.id == "complete-agent"
        assert spec.name == "Complete Test Agent"
        assert spec.fullyQualifiedName == "com.example.complete-agent"
        assert spec.domain == "Healthcare"
        assert spec.subDomain == "Diagnostics"
        assert spec.version == "2.0.0"
        assert spec.environment == "staging"
        assert spec.agentOwner == "test-team"
        assert spec.agentGoal == "Process medical data"

        # Test components
        assert len(spec.components) == 2
        tool_component = next(c for c in spec.components if c.id == "tool-1")
        assert tool_component.asTools is True
        assert len(tool_component.provides) == 1

        # Test variables
        assert len(spec.variables) == 1
        assert spec.variables[0].name == "api_key"
        assert spec.variables[0].required is True

        # Test KPIs
        assert len(spec.kpis) == 1
        assert spec.kpis[0].name == "Accuracy"
        assert spec.kpis[0].target == 95

        # Test security
        assert spec.security.visibility == "Internal"
        assert spec.security.gdprSensitive is True

        # Test reusability
        assert spec.reusability.asTools is True

    def test_agent_spec_from_dict(self, complete_agent_spec_data):
        """Test creating AgentSpec from dictionary using from_dict method."""
        spec = AgentSpec.from_dict(complete_agent_spec_data)
        assert isinstance(spec, AgentSpec)
        assert spec.id == "complete-agent"
        assert len(spec.components) == 2

    def test_agent_spec_defaults(self, minimal_agent_spec_data):
        """Test default values for optional fields."""
        spec = AgentSpec(**minimal_agent_spec_data)
        assert spec.fullyQualifiedName is None
        assert spec.domain is None
        assert spec.subDomain is None
        assert spec.version == "1.0.0"
        assert spec.environment == "production"
        assert spec.agentOwner is None
        assert spec.variables is None
        assert spec.kpis is None
        assert spec.security is None
        assert spec.reusability is None

    def test_agent_spec_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSpec(name="Test Agent")  # Missing required fields

        errors = exc_info.value.errors()
        required_fields = {error["loc"][0] for error in errors}
        assert "id" in required_fields
        assert "description" in required_fields
        assert "components" in required_fields

    def test_agent_spec_component_validation(self):
        """Test that components are properly validated."""
        with pytest.raises(ValidationError) as exc_info:
            AgentSpec(
                id="test-agent",
                name="Test Agent",
                description="Test description",
                components=[
                    {"id": "test-tool", "name": "Test Tool"}  # Missing required fields
                ]
            )

        # Should have validation errors for component fields
        errors = exc_info.value.errors()
        assert any("components" in str(error["loc"]) for error in errors)