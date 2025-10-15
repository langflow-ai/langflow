"""
Unit tests for ComponentSchemaInspector.

Tests the dynamic component schema extraction functionality that validates
input/output specifications against actual Langflow components.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import importlib
import sys
from typing import Dict, Any, List

# Add the path to avoid circular imports
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

try:
    from langflow.services.spec.component_schema_inspector import ComponentSchemaInspector, ComponentSchema
except ImportError:
    # Create mock classes for testing if import fails
    from dataclasses import dataclass

    @dataclass
    class ComponentSchema:
        name: str
        class_name: str
        module_path: str
        inputs: List[Dict[str, Any]]
        outputs: List[Dict[str, Any]]
        input_types: List[str]
        output_types: List[str]
        description: str
        display_name: str
        base_classes: List[str]

    class ComponentSchemaInspector:
        def __init__(self, components_root=None):
            self.components_root = components_root or "langflow.components"
            self._schema_cache = {}
            self._cache_duration = 300
            self._last_scan_time = 0


class TestComponentSchemaInspector:
    """Test suite for ComponentSchemaInspector functionality."""

    @pytest.fixture
    def inspector(self):
        """Create ComponentSchemaInspector instance for testing."""
        return ComponentSchemaInspector()

    @pytest.fixture
    def mock_component_class(self):
        """Create mock component class for testing."""
        mock_class = Mock()
        mock_class.__name__ = "TestComponent"
        mock_class.__module__ = "langflow.components.test.test_component"

        # Mock component attributes
        mock_class.name = "TestComponent"
        mock_class.display_name = "Test Component"
        mock_class.description = "A test component for validation"

        # Mock inputs
        mock_input = Mock()
        mock_input.name = "input_value"
        mock_input.display_name = "Input Value"
        mock_input.field_type = "StrInput"
        mock_input.required = True
        mock_input.value = None
        mock_input.to_dict.return_value = {
            "name": "input_value",
            "display_name": "Input Value",
            "field_type": "StrInput",
            "required": True,
            "value": None
        }
        mock_class.inputs = [mock_input]

        # Mock outputs
        mock_output = Mock()
        mock_output.name = "response"
        mock_output.display_name = "Response"
        mock_output.method = "process"
        mock_output.field_type = "MessageOutput"
        mock_output.to_dict.return_value = {
            "name": "response",
            "display_name": "Response",
            "field_type": "MessageOutput",
            "method": "process"
        }
        mock_class.outputs = [mock_output]

        # Mock inheritance
        mock_class.__mro__ = [mock_class, Mock(__name__="CustomComponent"), Mock(__name__="object")]

        return mock_class

    @pytest.fixture
    def sample_components_mapping(self):
        """Sample component I/O mappings for testing."""
        return {
            "TestComponent": {
                "input_field": "input_value",
                "output_field": "response",
                "output_types": ["Message"],
                "input_types": ["str"],
                "inputs": [
                    {
                        "name": "input_value",
                        "display_name": "Input Value",
                        "field_type": "StrInput",
                        "required": True,
                        "value": None
                    }
                ],
                "outputs": [
                    {
                        "name": "response",
                        "display_name": "Response",
                        "field_type": "MessageOutput",
                        "method": "process"
                    }
                ],
                "description": "A test component for validation"
            }
        }

    def test_init_default_components_root(self, inspector):
        """Test default initialization."""
        assert inspector.components_root == "langflow.components"
        assert inspector._schema_cache == {}
        assert inspector._cache_duration == 300

    def test_init_custom_components_root(self):
        """Test initialization with custom components root."""
        inspector = ComponentSchemaInspector("custom.components")
        assert inspector.components_root == "custom.components"

    def test_is_component_class_valid_component(self, inspector):
        """Test component class validation with valid component."""
        with patch.multiple(
            'langflow.services.spec.component_schema_inspector',
            CustomComponent=Mock(),
            LCModelComponent=Mock(),
            ComponentWithCache=Mock()
        ) as mocks:
            # Mock the component classes
            mock_component = Mock()
            mock_component.__name__ = "TestComponent"

            # Make it a subclass of CustomComponent
            def mock_issubclass(cls, bases):
                return cls == mock_component and any(base == mocks['CustomComponent'] for base in bases)

            with patch('inspect.isclass', return_value=True):
                with patch('builtins.issubclass', side_effect=mock_issubclass):
                    with patch('builtins.hasattr', return_value=True):
                        result = inspector._is_component_class(mock_component)
                        assert result is True

    def test_is_component_class_invalid_component(self, inspector):
        """Test component class validation with invalid component."""
        with patch('inspect.isclass', return_value=False):
            result = inspector._is_component_class(Mock())
            assert result is False

    def test_is_component_class_fallback_validation(self, inspector):
        """Test fallback validation when imports fail."""
        mock_component = Mock()
        mock_component.__name__ = "TestComponent"

        with patch('inspect.isclass', return_value=True):
            with patch('builtins.hasattr') as mock_hasattr:
                # Mock hasattr to return True for inputs and outputs
                def hasattr_side_effect(obj, attr):
                    return attr in ['inputs', 'outputs', '__name__']
                mock_hasattr.side_effect = hasattr_side_effect

                # Simulate ImportError in main validation
                with patch('langflow.services.spec.component_schema_inspector.CustomComponent', side_effect=ImportError()):
                    result = inspector._is_component_class(mock_component)
                    assert result is True

    def test_extract_inputs_with_to_dict_method(self, inspector, mock_component_class):
        """Test input extraction with to_dict method."""
        inputs = inspector._extract_inputs(mock_component_class)

        assert len(inputs) == 1
        assert inputs[0]["name"] == "input_value"
        assert inputs[0]["display_name"] == "Input Value"
        assert inputs[0]["field_type"] == "StrInput"
        assert inputs[0]["required"] is True

    def test_extract_inputs_with_dict_input(self, inspector):
        """Test input extraction with dictionary input."""
        mock_class = Mock()
        mock_class.inputs = [
            {
                "name": "test_input",
                "display_name": "Test Input",
                "field_type": "StrInput",
                "required": False
            }
        ]

        inputs = inspector._extract_inputs(mock_class)

        assert len(inputs) == 1
        assert inputs[0]["name"] == "test_input"
        assert inputs[0]["display_name"] == "Test Input"

    def test_extract_inputs_with_object_attributes(self, inspector):
        """Test input extraction with object attributes."""
        mock_input = Mock()
        mock_input.name = "attr_input"
        mock_input.display_name = "Attribute Input"
        mock_input.required = True
        mock_input.value = "default"
        # Simulate object without to_dict method
        del mock_input.to_dict

        mock_class = Mock()
        mock_class.inputs = [mock_input]

        inputs = inspector._extract_inputs(mock_class)

        assert len(inputs) == 1
        assert inputs[0]["name"] == "attr_input"
        assert inputs[0]["display_name"] == "Attribute Input"
        assert inputs[0]["required"] is True
        assert inputs[0]["value"] == "default"

    def test_extract_outputs_with_to_dict_method(self, inspector, mock_component_class):
        """Test output extraction with to_dict method."""
        outputs = inspector._extract_outputs(mock_component_class)

        assert len(outputs) == 1
        assert outputs[0]["name"] == "response"
        assert outputs[0]["display_name"] == "Response"
        assert outputs[0]["field_type"] == "MessageOutput"
        assert outputs[0]["method"] == "process"

    def test_determine_input_types_message_fields(self, inspector):
        """Test input type determination for message fields."""
        inputs = [
            {"field_type": "MessageInput", "name": "message"},
            {"field_type": "StrInput", "name": "template"},
            {"field_type": "IntInput", "name": "count"}
        ]

        types = inspector._determine_input_types(inputs)

        assert "Message" in types
        assert "str" in types
        assert "Data" in types

    def test_determine_input_types_based_on_names(self, inspector):
        """Test input type determination based on field names."""
        inputs = [
            {"field_type": "UnknownInput", "name": "input_value"},
            {"field_type": "UnknownInput", "name": "search_query"},
            {"field_type": "UnknownInput", "name": "parameters"}
        ]

        types = inspector._determine_input_types(inputs)

        assert "Message" in types
        assert "str" in types
        assert "Data" in types

    def test_determine_output_types_by_class_name(self, inspector):
        """Test output type determination by class name."""
        mock_class = Mock()
        mock_class.__name__ = "TestModelComponent"
        mock_class.__mro__ = [mock_class, Mock(__name__="LCModelComponent"), Mock(__name__="object")]

        types = inspector._determine_output_types([], mock_class)

        assert "Message" in types

    def test_determine_output_types_by_output_names(self, inspector):
        """Test output type determination by output field names."""
        mock_class = Mock()
        mock_class.__name__ = "TestComponent"
        mock_class.__mro__ = [mock_class, Mock(__name__="object")]

        outputs = [
            {"name": "response"},
            {"name": "data"},
            {"name": "prediction"}
        ]

        types = inspector._determine_output_types(outputs, mock_class)

        assert "Message" in types
        assert "Data" in types
        assert "DataFrame" in types

    def test_extract_component_schema(self, inspector, mock_component_class):
        """Test complete component schema extraction."""
        schema = inspector._extract_component_schema(mock_component_class, "test.module")

        assert schema is not None
        assert schema.name == "TestComponent"
        assert schema.class_name == "TestComponent"
        assert schema.module_path == "test.module"
        assert schema.description == "A test component for validation"
        assert len(schema.inputs) == 1
        assert len(schema.outputs) == 1
        assert "Message" in schema.output_types
        assert "str" in schema.input_types

    def test_extract_component_schema_error_handling(self, inspector):
        """Test schema extraction error handling."""
        mock_class = Mock()
        mock_class.__name__ = "ErrorComponent"
        # Simulate error by making getattr raise an exception
        with patch('builtins.getattr', side_effect=Exception("Attribute error")):
            schema = inspector._extract_component_schema(mock_class, "test.module")
            assert schema is None

    def test_get_component_io_mapping(self, inspector, sample_components_mapping):
        """Test component I/O mapping generation."""
        # Mock the schema cache
        schema = ComponentSchema(
            name="TestComponent",
            class_name="TestComponent",
            module_path="test.module",
            inputs=[{"name": "input_value", "field_type": "StrInput"}],
            outputs=[{"name": "response", "field_type": "MessageOutput"}],
            input_types=["str"],
            output_types=["Message"],
            description="A test component",
            display_name="Test Component",
            base_classes=["CustomComponent"]
        )
        inspector._schema_cache = {"TestComponent": schema}

        mapping = inspector.get_component_io_mapping()

        assert "TestComponent" in mapping
        component_mapping = mapping["TestComponent"]
        assert component_mapping["input_field"] == "input_value"
        assert component_mapping["output_field"] == "response"
        assert component_mapping["output_types"] == ["Message"]
        assert component_mapping["input_types"] == ["str"]

    def test_get_components_by_category(self, inspector):
        """Test component categorization."""
        # Mock schema cache with different component types
        schemas = {
            "AgentComponent": Mock(class_name="Agent", module_path="langflow.components.agents.agent"),
            "ModelComponent": Mock(class_name="ModelComponent", module_path="langflow.components.models.openai"),
            "MCPToolComponent": Mock(class_name="MCPTool", module_path="langflow.components.tools.mcp"),
            "InputComponent": Mock(class_name="InputComponent", module_path="langflow.components.inputs.chat"),
            "OutputComponent": Mock(class_name="OutputComponent", module_path="langflow.components.outputs.chat"),
            "ProcessorComponent": Mock(class_name="Processor", module_path="langflow.components.processing.text"),
            "OtherComponent": Mock(class_name="Other", module_path="langflow.components.other.misc")
        }

        # Set name attributes for categorization
        for name, schema in schemas.items():
            schema.name = name

        inspector._schema_cache = schemas

        categories = inspector.get_components_by_category()

        assert "agents" in categories
        assert "models" in categories
        assert "tools" in categories
        assert "inputs" in categories
        assert "outputs" in categories
        assert "processing" in categories
        assert "other" in categories

    def test_validate_component_connection_success(self, inspector):
        """Test successful component connection validation."""
        # Mock component schemas
        source_schema = ComponentSchema(
            name="SourceComponent",
            class_name="SourceComponent",
            module_path="test.source",
            inputs=[],
            outputs=[{"name": "output_field", "field_type": "MessageOutput"}],
            input_types=["str"],
            output_types=["Message"],
            description="Source component",
            display_name="Source Component",
            base_classes=["Component"]
        )

        target_schema = ComponentSchema(
            name="TargetComponent",
            class_name="TargetComponent",
            module_path="test.target",
            inputs=[{"name": "input_field", "field_type": "MessageInput"}],
            outputs=[],
            input_types=["Message"],
            output_types=["Data"],
            description="Target component",
            display_name="Target Component",
            base_classes=["Component"]
        )

        inspector._schema_cache = {
            "SourceComponent": source_schema,
            "TargetComponent": target_schema
        }

        result = inspector.validate_component_connection(
            "SourceComponent", "TargetComponent", "output_field", "input_field"
        )

        assert result["valid"] is True
        assert result["error"] is None
        assert "Message" in result["source_types"]
        assert "Message" in result["target_types"]

    def test_validate_component_connection_type_mismatch(self, inspector):
        """Test component connection validation with type mismatch."""
        # Mock component schemas with incompatible types
        source_schema = ComponentSchema(
            name="SourceComponent",
            class_name="SourceComponent",
            module_path="test.source",
            inputs=[],
            outputs=[{"name": "output_field", "field_type": "DataOutput"}],
            input_types=["str"],
            output_types=["DataFrame"],  # Incompatible with Message input
            description="Source component",
            display_name="Source Component",
            base_classes=["Component"]
        )

        target_schema = ComponentSchema(
            name="TargetComponent",
            class_name="TargetComponent",
            module_path="test.target",
            inputs=[{"name": "input_field", "field_type": "MessageInput"}],
            outputs=[],
            input_types=["Message"],  # Only accepts Message
            output_types=["Data"],
            description="Target component",
            display_name="Target Component",
            base_classes=["Component"]
        )

        inspector._schema_cache = {
            "SourceComponent": source_schema,
            "TargetComponent": target_schema
        }

        result = inspector.validate_component_connection(
            "SourceComponent", "TargetComponent", "output_field", "input_field"
        )

        assert result["valid"] is False
        assert "Type mismatch" in result["error"]

    def test_validate_component_connection_missing_schema(self, inspector):
        """Test connection validation with missing component schema."""
        inspector._schema_cache = {}

        result = inspector.validate_component_connection(
            "MissingComponent", "AnotherComponent", "output", "input"
        )

        assert result["valid"] is False
        assert "Component schema not found" in result["error"]

    def test_validate_component_connection_missing_fields(self, inspector):
        """Test connection validation with missing input/output fields."""
        schema = ComponentSchema(
            name="TestComponent",
            class_name="TestComponent",
            module_path="test.component",
            inputs=[{"name": "valid_input", "field_type": "StrInput"}],
            outputs=[{"name": "valid_output", "field_type": "MessageOutput"}],
            input_types=["str"],
            output_types=["Message"],
            description="Test component",
            display_name="Test Component",
            base_classes=["Component"]
        )

        inspector._schema_cache = {"TestComponent": schema}

        # Test missing output field
        result = inspector.validate_component_connection(
            "TestComponent", "TestComponent", "missing_output", "valid_input"
        )
        assert result["valid"] is False
        assert "Output field missing_output not found" in result["error"]

        # Test missing input field
        result = inspector.validate_component_connection(
            "TestComponent", "TestComponent", "valid_output", "missing_input"
        )
        assert result["valid"] is False
        assert "Input field missing_input not found" in result["error"]

    @patch('time.time')
    def test_cache_expiration(self, mock_time, inspector):
        """Test cache expiration and refresh."""
        # Initial time
        mock_time.return_value = 1000
        inspector._last_scan_time = 500  # Old scan time

        with patch.object(inspector, '_scan_components') as mock_scan:
            inspector._ensure_fresh_cache()
            mock_scan.assert_called_once()
            assert inspector._last_scan_time == 1000

    @patch('time.time')
    def test_cache_still_fresh(self, mock_time, inspector):
        """Test that fresh cache is not rescanned."""
        # Recent scan time
        mock_time.return_value = 1000
        inspector._last_scan_time = 800  # Recent scan

        with patch.object(inspector, '_scan_components') as mock_scan:
            inspector._ensure_fresh_cache()
            mock_scan.assert_not_called()

    def test_get_component_schema_with_cache_refresh(self, inspector):
        """Test component schema retrieval with cache refresh."""
        with patch.object(inspector, '_ensure_fresh_cache') as mock_refresh:
            inspector._schema_cache = {"TestComponent": Mock()}

            schema = inspector.get_component_schema("TestComponent")

            mock_refresh.assert_called_once()
            assert schema is not None

    def test_get_all_schemas_returns_copy(self, inspector):
        """Test that get_all_schemas returns a copy of cache."""
        mock_schema = Mock()
        inspector._schema_cache = {"TestComponent": mock_schema}

        with patch.object(inspector, '_ensure_fresh_cache'):
            schemas = inspector.get_all_schemas()

            # Modify returned dict shouldn't affect cache
            schemas["NewComponent"] = Mock()
            assert "NewComponent" not in inspector._schema_cache
            assert "TestComponent" in inspector._schema_cache


class TestComponentSchemaInspectorIntegration:
    """Integration tests for ComponentSchemaInspector with mocked file system."""

    @pytest.fixture
    def inspector_with_mock_fs(self):
        """Create inspector with mocked file system."""
        return ComponentSchemaInspector()

    @patch('importlib.import_module')
    @patch('pathlib.Path.iterdir')
    def test_scan_components_directory_structure(self, mock_iterdir, mock_import, inspector_with_mock_fs):
        """Test scanning directory structure for components."""
        # Mock package structure
        mock_package = Mock()
        mock_package.__file__ = "/fake/path/langflow/components/__init__.py"
        mock_import.return_value = mock_package

        # Mock directory structure
        mock_agents_dir = Mock()
        mock_agents_dir.name = "agents"
        mock_agents_dir.is_dir.return_value = True

        mock_tools_dir = Mock()
        mock_tools_dir.name = "tools"
        mock_tools_dir.is_dir.return_value = True

        mock_private_dir = Mock()
        mock_private_dir.name = "_private"
        mock_private_dir.is_dir.return_value = True

        mock_iterdir.return_value = [mock_agents_dir, mock_tools_dir, mock_private_dir]

        with patch.object(inspector_with_mock_fs, '_scan_directory') as mock_scan_dir:
            inspector_with_mock_fs._scan_components()

            # Should scan agents and tools but not _private
            assert mock_scan_dir.call_count == 2
            mock_scan_dir.assert_any_call(mock_agents_dir, "langflow.components.agents")
            mock_scan_dir.assert_any_call(mock_tools_dir, "langflow.components.tools")

    @patch('pathlib.Path.glob')
    def test_scan_directory_for_python_files(self, mock_glob, inspector_with_mock_fs):
        """Test scanning directory for Python component files."""
        # Mock Python files
        mock_file1 = Mock()
        mock_file1.name = "agent.py"
        mock_file1.stem = "agent"

        mock_file2 = Mock()
        mock_file2.name = "_private.py"
        mock_file2.stem = "_private"

        mock_file3 = Mock()
        mock_file3.name = "tool.py"
        mock_file3.stem = "tool"

        mock_glob.return_value = [mock_file1, mock_file2, mock_file3]

        mock_directory = Mock()

        with patch.object(inspector_with_mock_fs, '_analyze_module') as mock_analyze:
            inspector_with_mock_fs._scan_directory(mock_directory, "test.components")

            # Should analyze agent.py and tool.py but not _private.py
            assert mock_analyze.call_count == 2
            mock_analyze.assert_any_call("test.components.agent")
            mock_analyze.assert_any_call("test.components.tool")

    @patch('importlib.import_module')
    @patch('inspect.getmembers')
    def test_analyze_module_with_components(self, mock_getmembers, mock_import, inspector_with_mock_fs):
        """Test analyzing module for component classes."""
        # Mock module
        mock_module = Mock()
        mock_module.__name__ = "test.module"
        mock_import.return_value = mock_module

        # Mock component classes
        mock_component1 = Mock()
        mock_component1.__name__ = "Component1"
        mock_component1.__module__ = "test.module"

        mock_component2 = Mock()
        mock_component2.__name__ = "Component2"
        mock_component2.__module__ = "other.module"  # Different module

        mock_getmembers.return_value = [
            ("Component1", mock_component1),
            ("Component2", mock_component2),
            ("NotAClass", "string_value")
        ]

        with patch.object(inspector_with_mock_fs, '_is_component_class') as mock_is_component:
            with patch.object(inspector_with_mock_fs, '_extract_component_schema') as mock_extract:
                # Only Component1 is valid component and from same module
                mock_is_component.side_effect = lambda cls: cls == mock_component1

                mock_schema = Mock()
                mock_schema.name = "Component1"
                mock_extract.return_value = mock_schema

                inspector_with_mock_fs._analyze_module("test.module")

                # Should only extract schema for Component1
                mock_extract.assert_called_once_with(mock_component1, "test.module")
                assert "Component1" in inspector_with_mock_fs._schema_cache


if __name__ == "__main__":
    pytest.main([__file__, "-v"])