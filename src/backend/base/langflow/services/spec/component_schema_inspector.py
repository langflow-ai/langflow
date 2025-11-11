"""
Component Schema Inspector for extracting I/O information from actual Langflow components.

This module dynamically analyzes Langflow components to extract their input/output
schemas, providing accurate validation data for specification type checking.
"""

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass
import sys
import time

from langflow.template.field.base import Input
from langflow.template import Output
from langflow.custom.custom_component.component import Component

logger = logging.getLogger(__name__)


@dataclass
class ComponentSchema:
    """Schema information for a component."""
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
    """
    Inspects Langflow components to extract their I/O schemas.

    This class dynamically discovers and analyzes all Langflow components
    to provide accurate type information for validation.
    """

    def __init__(self, components_root: Optional[str] = None):
        """
        Initialize the inspector.

        Args:
            components_root: Root path for components. Defaults to langflow.components
        """
        self.components_root = components_root or "langflow.components"
        self._schema_cache: Dict[str, ComponentSchema] = {}
        # Additional cache keyed by Python class name for robust lookup
        self._schema_cache_by_class: Dict[str, ComponentSchema] = {}
        self._last_scan_time = 0
        self._cache_duration = 300  # 5 minutes

    def get_component_schema(self, component_name: str) -> Optional[ComponentSchema]:
        """
        Get schema for a specific component.

        Args:
            component_name: Name of the component class

        Returns:
            ComponentSchema or None if not found
        """
        self._ensure_fresh_cache()
        # Try by display/name key first
        schema = self._schema_cache.get(component_name)
        if schema:
            return schema

        # Fallback: try by class name key
        schema = self._schema_cache_by_class.get(component_name)
        if schema:
            return schema

        # Final fallback: case-insensitive search across both caches
        lowered = component_name.lower()
        for s in self._schema_cache.values():
            if s.name.lower() == lowered or s.class_name.lower() == lowered:
                return s

        return None

    def get_all_schemas(self) -> Dict[str, ComponentSchema]:
        """
        Get schemas for all discovered components.

        Returns:
            Dictionary mapping component names to schemas
        """
        self._ensure_fresh_cache()
        return self._schema_cache.copy()

    def get_component_io_mapping(self) -> Dict[str, Dict[str, Any]]:
        """
        Get I/O mapping in ComponentMapper format.

        Returns:
            Dictionary compatible with ComponentMapper.get_component_io_mapping()
        """
        self._ensure_fresh_cache()

        mapping: Dict[str, Dict[str, Any]] = {}
        for name, schema in self._schema_cache.items():
            # Determine primary input and output fields
            input_field = None
            output_field = None

            # Look for common input field names
            for inp in schema.inputs:
                field_name = inp.get("name", "")
                if field_name in ["input_value", "message", "template", "search_query", "url_input"]:
                    input_field = field_name
                    break

            # Look for common output field names
            for out in schema.outputs:
                field_name = out.get("name", "")
                if field_name in ["response", "message", "data", "prediction", "output"]:
                    output_field = field_name
                    break

            # Default to first available fields
            if not input_field and schema.inputs:
                input_field = schema.inputs[0].get("name")
            if not output_field and schema.outputs:
                output_field = schema.outputs[0].get("name")

            entry = {
                "input_field": input_field,
                "output_field": output_field,
                "output_types": schema.output_types,
                "input_types": schema.input_types,
                "inputs": schema.inputs,
                "outputs": schema.outputs,
                "description": schema.description
            }

            # Map under both display/name and class name for flexible lookups
            mapping[name] = entry
            mapping[schema.class_name] = entry

        return mapping

    def _ensure_fresh_cache(self) -> None:
        """Ensure the cache is fresh, rescanning if necessary."""
        current_time = time.time()
        if current_time - self._last_scan_time > self._cache_duration:
            self._scan_components()
            self._last_scan_time = current_time

    def _scan_components(self) -> None:
        """Scan all components and build schema cache."""
        logger.info(f"Scanning components in {self.components_root}")
        self._schema_cache.clear()
        self._schema_cache_by_class.clear()

        try:
            # Import the components package
            components_package = importlib.import_module(self.components_root)
            package_path = Path(components_package.__file__).parent

            # Walk through all subdirectories
            for subdir in package_path.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('_'):
                    self._scan_directory(subdir, f"{self.components_root}.{subdir.name}")

        except Exception as e:
            logger.error(f"Error scanning components: {e}")

    def _scan_directory(self, directory: Path, module_prefix: str) -> None:
        """
        Scan a directory for component files.

        Args:
            directory: Directory path to scan
            module_prefix: Module prefix for imports
        """
        for file_path in directory.glob("*.py"):
            if file_path.name.startswith('_'):
                continue

            module_name = f"{module_prefix}.{file_path.stem}"
            self._analyze_module(module_name)

    def _analyze_module(self, module_name: str) -> None:
        """
        Analyze a module for component classes.

        Args:
            module_name: Full module name to analyze
        """
        try:
            module = importlib.import_module(module_name)

            # Find all component classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if self._is_component_class(obj) and obj.__module__ == module_name:
                    schema = self._extract_component_schema(obj, module_name)
                    if schema:
                        # Cache by display/name and by class name
                        self._schema_cache[schema.name] = schema
                        self._schema_cache_by_class[schema.class_name] = schema
                        logger.debug(f"Extracted schema for {schema.name}")

        except Exception as e:
            logger.debug(f"Could not analyze module {module_name}: {e}")

    def _is_component_class(self, cls: type) -> bool:
        """
        Check if a class is a Langflow component.

        Args:
            cls: Class to check

        Returns:
            True if it's a component class
        """
        # Check if it's a subclass of known component base classes
        try:
            # Import base component classes
            from langflow.custom.custom_component import Component as CustomComponent
            from langflow.base.models.model import LCModelComponent
            from langflow.custom.custom_component.component_with_cache import ComponentWithCache

            base_classes = (CustomComponent, LCModelComponent, ComponentWithCache)

            return (
                inspect.isclass(cls) and
                issubclass(cls, base_classes) and
                cls not in base_classes and  # Exclude base classes themselves
                hasattr(cls, '__name__') and
                not cls.__name__.startswith('_')
            )
        except ImportError:
            # Fallback: check for common component attributes
            return (
                inspect.isclass(cls) and
                hasattr(cls, 'inputs') and
                hasattr(cls, 'outputs') and
                not cls.__name__.startswith('_')
            )

    def _extract_component_schema(self, cls: type, module_name: str) -> Optional[ComponentSchema]:
        """
        Extract schema information from a component class.

        Args:
            cls: Component class
            module_name: Module name

        Returns:
            ComponentSchema or None if extraction failed
        """
        try:
            # Get basic information
            name = getattr(cls, 'name', cls.__name__)
            display_name = getattr(cls, 'display_name', name)
            description = getattr(cls, 'description', '')

            # Extract inputs and outputs
            inputs = self._extract_inputs(cls)
            outputs = self._extract_outputs(cls)

            # Determine input/output types
            input_types = self._determine_input_types(inputs)
            output_types = self._determine_output_types(outputs, cls)

            # Get base classes
            base_classes = [base.__name__ for base in cls.__mro__[1:] if base.__name__ != 'object']

            return ComponentSchema(
                name=name,
                class_name=cls.__name__,
                module_path=module_name,
                inputs=inputs,
                outputs=outputs,
                input_types=input_types,
                output_types=output_types,
                description=description,
                display_name=display_name,
                base_classes=base_classes
            )

        except Exception as e:
            logger.debug(f"Error extracting schema from {cls.__name__}: {e}")
            return None

    def _extract_inputs(self, cls: type) -> List[Dict[str, Any]]:
        """Extract input information from component class."""
        inputs = []

        try:
            inputs_attr = getattr(cls, 'inputs', [])
            if not inputs_attr:
                return inputs

            for inp in inputs_attr:
                if hasattr(inp, 'to_dict'):
                    # Input object with to_dict method
                    input_dict = inp.to_dict()
                    inputs.append(input_dict)
                elif isinstance(inp, dict):
                    # Already a dictionary
                    inputs.append(inp)
                elif hasattr(inp, 'name'):
                    # Input object, extract manually
                    input_dict = {
                        'name': getattr(inp, 'name', ''),
                        'display_name': getattr(inp, 'display_name', ''),
                        'field_type': inp.__class__.__name__,
                        'required': getattr(inp, 'required', True),
                        'value': getattr(inp, 'value', None),
                    }
                    inputs.append(input_dict)

        except Exception as e:
            logger.debug(f"Error extracting inputs from {cls.__name__}: {e}")

        return inputs

    def _extract_outputs(self, cls: type) -> List[Dict[str, Any]]:
        """Extract output information from component class."""
        outputs = []

        try:
            outputs_attr = getattr(cls, 'outputs', [])
            if not outputs_attr:
                return outputs

            for out in outputs_attr:
                if hasattr(out, 'to_dict'):
                    # Output object with to_dict method
                    output_dict = out.to_dict()
                    outputs.append(output_dict)
                elif isinstance(out, dict):
                    # Already a dictionary
                    outputs.append(out)
                elif hasattr(out, 'name'):
                    # Output object, extract manually
                    output_dict = {
                        'name': getattr(out, 'name', ''),
                        'display_name': getattr(out, 'display_name', ''),
                        'method': getattr(out, 'method', ''),
                        'field_type': out.__class__.__name__,
                    }
                    outputs.append(output_dict)

        except Exception as e:
            logger.debug(f"Error extracting outputs from {cls.__name__}: {e}")

        return outputs

    def _determine_input_types(self, inputs: List[Dict[str, Any]]) -> List[str]:
        """
        Determine input types based on input definitions.

        Args:
            inputs: List of input dictionaries

        Returns:
            List of input type strings
        """
        types = set()

        for inp in inputs:
            field_type = inp.get('field_type', '')
            name = inp.get('name', '')

            # Map field types to data types
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

    def _determine_output_types(self, outputs: List[Dict[str, Any]], cls: type) -> List[str]:
        """
        Determine output types based on output definitions and class type.

        Args:
            outputs: List of output dictionaries
            cls: Component class

        Returns:
            List of output type strings
        """
        types = set()

        # Check class type for common patterns
        class_name = cls.__name__.lower()
        base_classes = [base.__name__.lower() for base in cls.__mro__]

        if 'model' in class_name or any('model' in base for base in base_classes):
            types.add('Message')
        elif 'tool' in class_name or 'mcp' in class_name:
            types.add('DataFrame')
        elif 'api' in class_name or 'request' in class_name:
            types.add('Data')
        elif 'agent' in class_name:
            types.add('Message')
        elif 'input' in class_name:
            types.add('Message')
        elif 'output' in class_name:
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

    def get_components_by_category(self) -> Dict[str, List[str]]:
        """
        Get components grouped by category.

        Returns:
            Dictionary mapping categories to component lists
        """
        self._ensure_fresh_cache()

        categories = {
            'agents': [],
            'models': [],
            'tools': [],
            'inputs': [],
            'outputs': [],
            'processing': [],
            'other': []
        }

        for name, schema in self._schema_cache.items():
            class_name = schema.class_name.lower()
            module_path = schema.module_path.lower()

            if 'agent' in class_name or 'agents' in module_path:
                categories['agents'].append(name)
            elif 'model' in class_name or 'models' in module_path:
                categories['models'].append(name)
            elif 'tool' in class_name or 'mcp' in class_name or 'api' in class_name:
                categories['tools'].append(name)
            elif 'input' in class_name:
                categories['inputs'].append(name)
            elif 'output' in class_name:
                categories['outputs'].append(name)
            elif 'processing' in module_path:
                categories['processing'].append(name)
            else:
                categories['other'].append(name)

        return categories

    def validate_component_connection(self, source_comp: str, target_comp: str,
                                    source_output: str, target_input: str) -> Dict[str, Any]:
        """
        Validate a connection between two components.

        Args:
            source_comp: Source component name
            target_comp: Target component name
            source_output: Source output field name
            target_input: Target input field name

        Returns:
            Validation result with compatibility information
        """
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
        # Special-case: tool connections targeting the 'tools' input should be considered compatible.
        # Tool semantics imply registration rather than direct data type matching.
        if isinstance(target_input, str) and target_input.lower() == "tools":
            return {
                'valid': True,
                'source_types': source_schema.output_types,
                'target_types': target_schema.input_types,
                'error': None
            }

        # Treat 'any'/'Any'/'object' on target as wildcard accepting any source type
        source_types = set(source_schema.output_types or [])
        target_types = set(target_schema.input_types or [])

        if any(t in target_types for t in ("any", "Any", "object")):
            compatible = True
        else:
            compatible = bool(source_types & target_types)

        return {
            'valid': compatible,
            'source_types': source_schema.output_types,
            'target_types': target_schema.input_types,
            'error': None if compatible else 'Type mismatch between components'
        }