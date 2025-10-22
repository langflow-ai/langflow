"""
Comprehensive tests for the unified component discovery system (AUTPE-6206).

Tests data-driven introspection, variant consolidation, and runtime adapter creation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
from pathlib import Path
import inspect

from langflow.services.component_mapping.discovery import (
    UnifiedComponentDiscovery,
    ComponentCapabilities,
    ComponentVariant,
    DiscoveredComponent,
)


class TestComponentCapabilities:
    """Test the ComponentCapabilities dataclass."""

    def test_capabilities_initialization(self):
        """Test that capabilities are initialized with correct defaults."""
        caps = ComponentCapabilities()

        assert caps.accepts_tools is False
        assert caps.provides_tools is False
        assert caps.tool_methods == []
        assert caps.tool_input_fields == []
        assert caps.base_classes == []
        assert caps.implements_interfaces == []
        assert caps.has_build_method is False
        assert caps.has_as_tool_method is False
        assert caps.has_tool_mode is False
        assert caps.discovery_method == "introspection"
        assert caps.introspected_at is not None

    def test_capabilities_with_tools(self):
        """Test capabilities for a tool-providing component."""
        caps = ComponentCapabilities(
            accepts_tools=False,
            provides_tools=True,
            tool_methods=["as_tool", "build_tool"],
            has_as_tool_method=True,
            has_build_method=True,
        )

        assert caps.provides_tools is True
        assert caps.accepts_tools is False
        assert "as_tool" in caps.tool_methods
        assert caps.has_as_tool_method is True

    def test_agent_capabilities(self):
        """Test that agents have both accepts and provides tools."""
        caps = ComponentCapabilities(
            accepts_tools=True,
            provides_tools=True,  # Agents ARE tools!
            tool_methods=["as_tool"],
            tool_input_fields=["tools"],
            base_classes=["BaseAgent", "ToolCallingAgent"],
        )

        assert caps.accepts_tools is True
        assert caps.provides_tools is True
        assert "ToolCallingAgent" in caps.base_classes


class TestComponentVariant:
    """Test the ComponentVariant dataclass."""

    def test_variant_creation(self):
        """Test creating a component variant."""
        variant = ComponentVariant(
            model_name="gpt-4o",
            display_name="GPT-4 Optimized",
            config={"temperature": 0.7},
            metadata={"provider": "openai"},
        )

        assert variant.model_name == "gpt-4o"
        assert variant.display_name == "GPT-4 Optimized"
        assert variant.config["temperature"] == 0.7
        assert variant.metadata["provider"] == "openai"


class TestDiscoveredComponent:
    """Test the DiscoveredComponent dataclass."""

    def test_component_creation(self):
        """Test creating a discovered component."""
        caps = ComponentCapabilities(provides_tools=True)
        component = DiscoveredComponent(
            genesis_type="genesis:test_tool",
            component_name="TestTool",
            module_path="langflow.components.tools.test",
            class_name="TestTool",
            category="tool",
            capabilities=caps,
        )

        assert component.genesis_type == "genesis:test_tool"
        assert component.capabilities.provides_tools is True
        assert component.category == "tool"

    def test_component_with_variants(self):
        """Test component with model variants."""
        component = DiscoveredComponent(
            genesis_type="genesis:agent",
            component_name="AgentComponent",
            module_path="langflow.components.agents.agent",
            class_name="AgentComponent",
            category="agent",
            capabilities=ComponentCapabilities(accepts_tools=True, provides_tools=True),
            has_variants=True,
            variants=[
                ComponentVariant(model_name="gpt-4o", display_name="Agent - GPT-4"),
                ComponentVariant(model_name="claude-3", display_name="Agent - Claude 3"),
            ],
        )

        assert component.has_variants is True
        assert len(component.variants) == 2
        assert component.variants[0].model_name == "gpt-4o"

    def test_to_database_entry(self):
        """Test converting component to database entry format."""
        caps = ComponentCapabilities(
            accepts_tools=True,
            provides_tools=True,
            tool_methods=["as_tool"],
        )

        component = DiscoveredComponent(
            genesis_type="genesis:test_agent",
            component_name="TestAgent",
            module_path="langflow.components.agents.test",
            class_name="TestAgent",
            category="agent",
            capabilities=caps,
            display_name="Test Agent",
            description="A test agent component",
            inputs=[{"name": "tools", "type": "List[Tool]"}],
            outputs=[{"name": "result", "type": "Message"}],
        )

        entry = component.to_database_entry()

        assert entry["genesis_type"] == "genesis:test_agent"
        assert entry["component_category"] == "agent"
        assert entry["tool_capabilities"]["accepts_tools"] is True
        assert entry["tool_capabilities"]["provides_tools"] is True
        assert "as_tool" in entry["tool_capabilities"]["tool_methods"]
        assert entry["introspection_data"] is not None
        assert entry["introspected_at"] is not None


class TestUnifiedComponentDiscovery:
    """Test the unified component discovery service."""

    def test_initialization(self):
        """Test discovery service initialization."""
        discovery = UnifiedComponentDiscovery()

        assert discovery.components == {}
        assert discovery.variant_groups == {}
        assert discovery.errors == []
        assert discovery.stats["total_discovered"] == 0

    @patch("langflow.services.component_mapping.discovery.importlib.import_module")
    def test_introspect_capabilities_agent(self, mock_import):
        """Test introspecting capabilities for an agent component."""
        discovery = UnifiedComponentDiscovery()

        # Mock agent class
        class MockAgent:
            __name__ = "TestAgent"
            __module__ = "langflow.components.agents.test"

            @classmethod
            def as_tool(cls):
                pass

            @classmethod
            def build_tool(cls):
                pass

            inputs = [
                Mock(name="tools", type="List[Tool]"),
            ]

        # Mock inspect.getmro to return agent base classes
        with patch("inspect.getmro", return_value=[MockAgent, Mock(__name__="ToolCallingAgent"), object]):
            caps = discovery._introspect_capabilities(MockAgent)

        assert caps.accepts_tools is True
        assert caps.provides_tools is True  # Agents ARE tools!
        assert "as_tool" in caps.tool_methods
        assert "build_tool" in caps.tool_methods
        assert "ToolCallingAgent" in caps.base_classes

    def test_introspect_capabilities_tool(self):
        """Test introspecting capabilities for a tool component."""
        discovery = UnifiedComponentDiscovery()

        # Mock tool class
        class MockTool:
            __name__ = "TestTool"
            __module__ = "langflow.components.tools.test"

            @classmethod
            def as_tool(cls):
                pass

        with patch("inspect.getmro", return_value=[MockTool, Mock(__name__="BaseTool"), object]):
            with patch("inspect.getmembers") as mock_members:
                mock_members.return_value = [("as_tool", Mock())]
                caps = discovery._introspect_capabilities(MockTool)

        assert caps.provides_tools is True
        assert "as_tool" in caps.tool_methods

    def test_introspect_capabilities_no_tools(self):
        """Test introspecting capabilities for non-tool component."""
        discovery = UnifiedComponentDiscovery()

        # Mock basic component
        class MockComponent:
            __name__ = "TestComponent"
            __module__ = "langflow.components.io.test"

        with patch("inspect.getmro", return_value=[MockComponent, object]):
            with patch("inspect.getmembers", return_value=[]):
                caps = discovery._introspect_capabilities(MockComponent)

        assert caps.accepts_tools is False
        assert caps.provides_tools is False
        assert caps.tool_methods == []

    def test_extract_variants(self):
        """Test extracting model variants from component."""
        discovery = UnifiedComponentDiscovery()

        # Mock component with MODEL_OPTIONS
        class MockComponent:
            MODEL_OPTIONS = [
                {"name": "gpt-4o", "display_name": "GPT-4 Optimized"},
                {"name": "gpt-3.5-turbo", "display_name": "GPT-3.5 Turbo"},
            ]

        variants = discovery._extract_variants(MockComponent)

        assert len(variants) == 2
        assert variants[0].model_name == "gpt-4o"
        assert variants[0].display_name == "GPT-4 Optimized"
        assert variants[1].model_name == "gpt-3.5-turbo"

    def test_variant_consolidation(self):
        """Test consolidating variant components."""
        discovery = UnifiedComponentDiscovery()

        # Create multiple variant components
        base_component = DiscoveredComponent(
            genesis_type="genesis:agent",
            component_name="AgentComponent",
            module_path="langflow.components.agents",
            class_name="AgentComponent",
            category="agent",
            capabilities=ComponentCapabilities(),
        )

        variant1 = DiscoveredComponent(
            genesis_type="genesis:agent_gpt_4o",
            component_name="AgentComponent_gpt_4o",
            module_path="langflow.components.agents",
            class_name="AgentComponent_gpt_4o",
            category="agent",
            capabilities=ComponentCapabilities(),
        )

        variant2 = DiscoveredComponent(
            genesis_type="genesis:agent_claude_3",
            component_name="AgentComponent_claude_3",
            module_path="langflow.components.agents",
            class_name="AgentComponent_claude_3",
            category="agent",
            capabilities=ComponentCapabilities(),
        )

        # Add to discovery
        discovery.components = {
            "genesis:agent": base_component,
            "genesis:agent_gpt_4o": variant1,
            "genesis:agent_claude_3": variant2,
        }

        discovery.variant_groups = {
            "AgentComponent": [base_component, variant1, variant2],
        }

        discovery.stats["total_discovered"] = 3

        # Consolidate variants
        discovery._consolidate_variants()

        # Check that variants were consolidated
        assert len(discovery.components) == 1  # Only base component remains
        assert "genesis:agent" in discovery.components
        assert "genesis:agent_gpt_4o" not in discovery.components
        assert "genesis:agent_claude_3" not in discovery.components

        # Check that base component has variants
        consolidated = discovery.components["genesis:agent"]
        assert consolidated.has_variants is True
        assert len(consolidated.variants) >= 2

    def test_generate_runtime_adapters(self):
        """Test generating runtime adapters for all components."""
        discovery = UnifiedComponentDiscovery()

        # Add test components
        component1 = DiscoveredComponent(
            genesis_type="genesis:test_tool",
            component_name="TestTool",
            module_path="langflow.components.tools.test",
            class_name="TestTool",
            category="tool",
            capabilities=ComponentCapabilities(provides_tools=True),
        )

        component2 = DiscoveredComponent(
            genesis_type="genesis:test_agent",
            component_name="TestAgent",
            module_path="langflow.components.agents.test",
            class_name="TestAgent",
            category="agent",
            capabilities=ComponentCapabilities(accepts_tools=True, provides_tools=True),
            has_variants=True,
            variants=[ComponentVariant(model_name="gpt-4o", display_name="GPT-4")],
        )

        component3 = DiscoveredComponent(
            genesis_type="genesis:healthcare_connector",
            component_name="HealthcareConnector",
            module_path="langflow.components.healthcare.connector",
            class_name="HealthcareConnector",
            category="healthcare",
            capabilities=ComponentCapabilities(),
        )

        discovery.components = {
            "genesis:test_tool": component1,
            "genesis:test_agent": component2,
            "genesis:healthcare_connector": component3,
        }

        # Generate adapters
        adapters = discovery.generate_runtime_adapters()

        # Should have one adapter per component
        assert len(adapters) == 3

        # Check adapter properties
        tool_adapter = next(a for a in adapters if a["genesis_type"] == "genesis:test_tool")
        assert tool_adapter["runtime_type"] == "langflow"
        assert tool_adapter["target_component"] == "TestTool"

        agent_adapter = next(a for a in adapters if a["genesis_type"] == "genesis:test_agent")
        assert agent_adapter["adapter_config"]["variants"] == ["gpt-4o"]

        healthcare_adapter = next(a for a in adapters if a["genesis_type"] == "genesis:healthcare_connector")
        assert "compliance_rules" in healthcare_adapter
        assert healthcare_adapter["compliance_rules"]["hipaa_required"] is True

    def test_generate_database_entries(self):
        """Test generating database entries from discovered components."""
        discovery = UnifiedComponentDiscovery()

        # Add a test component with full details
        component = DiscoveredComponent(
            genesis_type="genesis:comprehensive_agent",
            component_name="ComprehensiveAgent",
            module_path="langflow.components.agents.comprehensive",
            class_name="ComprehensiveAgent",
            category="agent",
            capabilities=ComponentCapabilities(
                accepts_tools=True,
                provides_tools=True,
                tool_methods=["as_tool", "build_tool"],
                tool_input_fields=["tools"],
                base_classes=["BaseAgent", "ToolCallingAgent"],
            ),
            has_variants=True,
            variants=[
                ComponentVariant(model_name="gpt-4o", display_name="GPT-4"),
                ComponentVariant(model_name="claude-3", display_name="Claude 3"),
            ],
            display_name="Comprehensive Agent",
            description="A fully-featured agent component",
            inputs=[{"name": "tools", "type": "List[Tool]", "required": False}],
            outputs=[{"name": "result", "type": "Message"}],
            methods=["build", "as_tool", "process"],
        )

        discovery.components = {"genesis:comprehensive_agent": component}

        # Generate database entries
        entries = discovery.generate_database_entries()

        assert len(entries) == 1
        entry = entries[0]

        # Verify all fields are properly populated
        assert entry["genesis_type"] == "genesis:comprehensive_agent"
        assert entry["component_category"] == "agent"
        assert entry["description"] == "A fully-featured agent component"

        # Check tool capabilities
        assert entry["tool_capabilities"]["accepts_tools"] is True
        assert entry["tool_capabilities"]["provides_tools"] is True
        assert "as_tool" in entry["tool_capabilities"]["tool_methods"]

        # Check variants
        assert entry["variants"] is not None
        assert len(entry["variants"]) == 2
        assert entry["variants"][0]["model_name"] == "gpt-4o"

        # Check introspection data
        assert entry["introspection_data"] is not None
        assert "methods" in entry["introspection_data"]
        assert "build" in entry["introspection_data"]["methods"]
        assert "base_classes" in entry["introspection_data"]

        # Check timestamps
        assert entry["introspected_at"] is not None

    @patch("os.walk")
    @patch("builtins.open")
    @patch("ast.parse")
    def test_discover_all_integration(self, mock_parse, mock_open, mock_walk):
        """Test the full discovery process."""
        discovery = UnifiedComponentDiscovery()

        # Mock file system
        mock_walk.return_value = [
            ("/path/components/agents", [], ["agent.py"]),
            ("/path/components/tools", [], ["tool.py"]),
        ]

        # Mock file content parsing
        mock_parse.return_value = Mock()

        # Mock the discovery process
        with patch.object(discovery, "_process_file") as mock_process:
            results = discovery.discover_all()

        assert results["success"] is True
        assert "statistics" in results
        assert "summary" in results

    def test_reduction_statistics(self):
        """Test that variant consolidation reduces database entries."""
        discovery = UnifiedComponentDiscovery()

        # Simulate many variant components
        for i in range(100):
            base_name = f"Component{i // 10}"
            variant_name = f"{base_name}_variant_{i}"

            component = DiscoveredComponent(
                genesis_type=f"genesis:{variant_name.lower()}",
                component_name=variant_name,
                module_path=f"langflow.components.{variant_name}",
                class_name=variant_name,
                category="agent",
                capabilities=ComponentCapabilities(),
            )

            discovery.components[component.genesis_type] = component

            # Add to variant groups
            if base_name not in discovery.variant_groups:
                discovery.variant_groups[base_name] = []
            discovery.variant_groups[base_name].append(component)

        discovery.stats["total_discovered"] = 100

        # Consolidate
        discovery._consolidate_variants()

        # Should have reduced to ~10 components (one per base)
        assert len(discovery.components) <= 20  # Some tolerance for test
        assert discovery.stats["total_consolidated"] < discovery.stats["total_discovered"]

        # Generate summary
        results = discovery._generate_results()
        assert results["summary"]["reduction_ratio"] > 50  # At least 50% reduction


if __name__ == "__main__":
    pytest.main([__file__, "-v"])