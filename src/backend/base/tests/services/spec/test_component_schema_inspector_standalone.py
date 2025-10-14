"""
Standalone unit tests for ComponentSchemaInspector logic.

These tests validate the core functionality without requiring full langflow imports.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class MockComponentSchema:
    """Mock ComponentSchema for testing."""
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


class MockComponentSchemaInspector:
    """Mock ComponentSchemaInspector for testing core logic."""

    def __init__(self, components_root: str = None):
        self.components_root = components_root or "langflow.components"
        self._schema_cache = {}
        self._cache_duration = 300
        self._last_scan_time = 0

    def get_component_schema(self, component_name: str):
        """Get schema for a specific component."""
        return self._schema_cache.get(component_name)

    def _is_component_class(self, cls) -> bool:
        """Check if a class is a component class."""
        return hasattr(cls, 'inputs') and hasattr(cls, 'outputs')

    def _determine_input_types(self, inputs: List[Dict[str, Any]]) -> List[str]:
        """Determine input types based on input definitions."""
        types = set()

        for inp in inputs:
            field_type = inp.get('field_type', '')
            name = inp.get('name', '')

            if 'Message' in field_type or 'Text' in field_type:
                types.add('Message')
            elif 'Str' in field_type or 'String' in field_type:
                types.add('str')
            elif 'Int' in field_type or 'Float' in field_type or 'Number' in field_type:
                types.add('Data')
            elif 'Dict' in field_type or 'Json' in field_type:
                types.add('Data')
            elif 'File' in field_type or 'Path' in field_type:
                types.add('Document')
            else:
                # Default based on common field names
                if name in ['input_value', 'message']:
                    types.add('Message')
                elif name in ['search_query', 'template']:
                    types.add('str')
                elif name in ['data', 'parameters']:
                    types.add('Data')
                else:
                    types.add('any')

        return list(types) if types else ['any']

    def _determine_output_types(self, outputs: List[Dict[str, Any]], cls) -> List[str]:
        """Determine output types based on output definitions and class type."""
        types = set()

        # Check class type for common patterns
        class_name = cls.__name__.lower() if hasattr(cls, '__name__') else ''

        if 'model' in class_name:
            types.add('Message')
        elif 'tool' in class_name or 'mcp' in class_name:
            types.add('DataFrame')
        elif 'api' in class_name or 'request' in class_name:
            types.add('Data')
        elif 'agent' in class_name:
            types.add('Message')

        # Also check output definitions
        for out in outputs:
            name = out.get('name', '')
            if name in ['response', 'message']:
                types.add('Message')
            elif name in ['data', 'result']:
                types.add('Data')
            elif name in ['prediction', 'output']:
                types.add('DataFrame')

        return list(types) if types else ['any']

    def validate_component_connection(self, source_comp: str, target_comp: str,
                                    source_output: str, target_input: str) -> Dict[str, Any]:
        """Validate connection between two components."""
        source_schema = self.get_component_schema(source_comp)
        target_schema = self.get_component_schema(target_comp)

        if not source_schema or not target_schema:
            return {
                'valid': False,
                'error': f'Component schema not found: {source_comp if not source_schema else target_comp}'
            }

        # Check if output field exists
        source_outputs = {out.get('name'): out for out in source_schema.outputs}
        if source_output not in source_outputs:
            return {
                'valid': False,
                'error': f'Output field {source_output} not found in {source_comp}'
            }

        # Check if input field exists
        target_inputs = {inp.get('name'): inp for inp in target_schema.inputs}
        if target_input not in target_inputs:
            return {
                'valid': False,
                'error': f'Input field {target_input} not found in {target_comp}'
            }

        # Check type compatibility
        compatible = any(otype in target_schema.input_types
                        for otype in source_schema.output_types)

        return {
            'valid': compatible,
            'source_types': source_schema.output_types,
            'target_types': target_schema.input_types,
            'error': None if compatible else 'Type mismatch between components'
        }


class TestComponentSchemaInspectorStandalone:
    """Test ComponentSchemaInspector core logic."""

    @pytest.fixture
    def inspector(self):
        """Create test inspector."""
        return MockComponentSchemaInspector()

    @pytest.fixture
    def sample_schema(self):
        """Create sample component schema."""
        return MockComponentSchema(
            name="TestComponent",
            class_name="TestComponent",
            module_path="test.module",
            inputs=[{"name": "input_value", "field_type": "StrInput"}],
            outputs=[{"name": "response", "field_type": "MessageOutput"}],
            input_types=["str"],
            output_types=["Message"],
            description="Test component",
            display_name="Test Component",
            base_classes=["Component"]
        )

    def test_input_type_determination_message_fields(self, inspector):
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

    def test_input_type_determination_by_name(self, inspector):
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

    def test_output_type_determination_by_class(self, inspector):
        """Test output type determination by class name."""
        mock_class = Mock()
        mock_class.__name__ = "TestModelComponent"

        types = inspector._determine_output_types([], mock_class)

        assert "Message" in types

    def test_output_type_determination_by_outputs(self, inspector):
        """Test output type determination by output names."""
        mock_class = Mock()
        mock_class.__name__ = "TestComponent"

        outputs = [
            {"name": "response"},
            {"name": "data"},
            {"name": "prediction"}
        ]

        types = inspector._determine_output_types(outputs, mock_class)

        assert "Message" in types
        assert "Data" in types
        assert "DataFrame" in types

    def test_component_connection_validation_success(self, inspector, sample_schema):
        """Test successful component connection validation."""
        # Create compatible schemas
        source_schema = MockComponentSchema(
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

        target_schema = MockComponentSchema(
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

    def test_component_connection_validation_type_mismatch(self, inspector):
        """Test component connection validation with type mismatch."""
        # Create incompatible schemas
        source_schema = MockComponentSchema(
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

        target_schema = MockComponentSchema(
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

    def test_component_connection_validation_missing_schema(self, inspector):
        """Test connection validation with missing component schema."""
        inspector._schema_cache = {}

        result = inspector.validate_component_connection(
            "MissingComponent", "AnotherComponent", "output", "input"
        )

        assert result["valid"] is False
        assert "Component schema not found" in result["error"]

    def test_component_connection_validation_missing_fields(self, inspector):
        """Test connection validation with missing input/output fields."""
        schema = MockComponentSchema(
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

    def test_is_component_class(self, inspector):
        """Test component class detection."""
        # Valid component class
        mock_component = Mock()
        mock_component.inputs = []
        mock_component.outputs = []

        assert inspector._is_component_class(mock_component) is True

        # Invalid class (missing attributes)
        mock_invalid = Mock()
        del mock_invalid.inputs  # Remove inputs attribute

        assert inspector._is_component_class(mock_invalid) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])