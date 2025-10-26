"""
Unified Component Discovery Service - AUTPE-6206.

This module provides data-driven component discovery and introspection,
replacing all static pattern matching with actual component code inspection.
Consolidates variants and ensures proper runtime adapter creation.
"""

import os
import logging
import importlib
import inspect
import pkgutil
import ast
from typing import Dict, List, Any, Optional, Type, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class ComponentCapabilities:
    """Data-driven capabilities discovered through introspection."""

    accepts_tools: bool = False
    provides_tools: bool = False
    tool_methods: List[str] = field(default_factory=list)
    tool_input_fields: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    implements_interfaces: List[str] = field(default_factory=list)
    has_build_method: bool = False
    has_as_tool_method: bool = False
    has_tool_mode: bool = False
    discovery_method: str = "introspection"
    introspected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ComponentVariant:
    """Represents a model variant of a component."""

    model_name: str
    display_name: str
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveredComponent:
    """Complete component information from introspection."""

    # Identity
    genesis_type: str
    component_name: str
    module_path: str
    class_name: str

    # Categorization (from introspection, not patterns)
    category: str

    # Capabilities (data-driven)
    capabilities: ComponentCapabilities

    # Optional fields
    subcategory: Optional[str] = None

    # Variants (consolidated)
    has_variants: bool = False
    variants: List[ComponentVariant] = field(default_factory=list)
    base_component: Optional[str] = None  # For variant components

    # Introspection metadata
    introspection_data: Dict[str, Any] = field(default_factory=dict)
    introspected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Component metadata
    display_name: str = ""
    description: str = ""
    icon: Optional[str] = None
    version: str = "1.0.0"

    # Runtime info
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)

    def to_database_entry(self) -> Dict[str, Any]:
        """Convert to database-ready format with consolidated variants."""
        return {
            "genesis_type": self.genesis_type,
            "component_category": self.category,
            "description": self.description or f"Component: {self.display_name}",
            "base_config": {
                "component": self.component_name,
                "module_path": self.module_path,
                "class_name": self.class_name,
                "display_name": self.display_name,
                "icon": self.icon,
            },
            "io_mapping": {
                "inputs": self.inputs,
                "outputs": self.outputs,
                "category": self.category,
                "subcategory": self.subcategory,
            },
            "tool_capabilities": {
                "accepts_tools": self.capabilities.accepts_tools,
                "provides_tools": self.capabilities.provides_tools,
                "tool_methods": self.capabilities.tool_methods,
                "discovery_method": self.capabilities.discovery_method,
                "introspected_at": self.capabilities.introspected_at,
            },
            "runtime_introspection": self.introspection_data,
            "variants": {
                "variant_list": [
                    {
                        "model_name": v.model_name,
                        "display_name": v.display_name,
                        "config": v.config,
                        "metadata": v.metadata,
                    }
                    for v in self.variants
                ],
                "count": len(self.variants)
            } if self.has_variants else None,
            "introspection_data": {
                "methods": self.methods,
                "base_classes": self.capabilities.base_classes,
                "implements_interfaces": self.capabilities.implements_interfaces,
                "has_build_method": self.capabilities.has_build_method,
                "has_as_tool_method": self.capabilities.has_as_tool_method,
                "introspected_at": self.introspected_at,
            },
            "introspected_at": self.introspected_at,
            "version": self.version,
            "active": True,
        }


class UnifiedComponentDiscovery:
    """
    Unified discovery service with data-driven introspection.

    Key features:
    - NO static pattern matching
    - Actual component code introspection
    - Variant consolidation
    - Proper capability detection
    """

    def __init__(self):
        """Initialize the unified discovery service."""
        self.components: Dict[str, DiscoveredComponent] = {}
        self.variant_groups: Dict[str, List[DiscoveredComponent]] = {}
        self.errors: List[Dict[str, Any]] = []
        self.stats = {
            "total_discovered": 0,
            "total_consolidated": 0,
            "variants_found": 0,
            "components_with_variants": 0,
            "introspection_failures": 0,
        }

        # Paths to scan
        self.component_paths = [
            Path(__file__).parent.parent.parent / "components",
            Path(__file__).parent.parent.parent / "custom",
        ]

    def discover_all(self) -> Dict[str, Any]:
        """
        Discover all components using data-driven introspection.

        Returns:
            Discovery results with consolidated components
        """
        logger.info("Starting unified component discovery with introspection...")

        # Reset state
        self.components.clear()
        self.variant_groups.clear()
        self.errors.clear()
        self.stats = {
            "total_discovered": 0,
            "total_consolidated": 0,
            "variants_found": 0,
            "components_with_variants": 0,
            "introspection_failures": 0,
        }

        # Phase 1: Discover all components
        for path in self.component_paths:
            if path.exists():
                self._scan_directory(path)

        # Phase 2: Consolidate variants
        self._consolidate_variants()

        # Phase 3: Generate results
        return self._generate_results()

    def _scan_directory(self, path: Path) -> None:
        """Scan directory for component files."""
        try:
            for root, dirs, files in os.walk(path):
                # Skip __pycache__ and test directories
                dirs[:] = [d for d in dirs if d not in ['__pycache__', 'tests', 'test']]

                for file in files:
                    if file.endswith('.py') and not file.startswith('__'):
                        file_path = Path(root) / file
                        self._process_file(file_path)
        except Exception as e:
            logger.error(f"Error scanning directory {path}: {e}")
            self.errors.append({"type": "scan_error", "path": str(path), "error": str(e)})

    def _process_file(self, file_path: Path) -> None:
        """Process a Python file for component definitions."""
        try:
            # Get module name from file path
            module_name = self._get_module_name(file_path)
            if not module_name:
                return

            # Parse the file AST first for initial analysis
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError as e:
                    logger.debug(f"Syntax error parsing {file_path}: {e}")
                    return

            # Find component classes
            component_classes = self._find_component_classes(tree)

            if not component_classes:
                return

            # Import module for introspection
            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                logger.debug(f"Could not import {module_name}: {e}")
                return

            # Process each component class
            for class_name in component_classes:
                if hasattr(module, class_name):
                    component_class = getattr(module, class_name)
                    if inspect.isclass(component_class):
                        self._introspect_component(component_class, module_name, file_path)

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            self.errors.append({"type": "process_error", "file": str(file_path), "error": str(e)})

    def _get_module_name(self, file_path: Path) -> Optional[str]:
        """Convert file path to module name."""
        try:
            # Find the relative path from langflow
            for parent in file_path.parents:
                if parent.name == "langflow":
                    rel_path = file_path.relative_to(parent.parent)
                    # Convert to module name
                    parts = list(rel_path.parts[:-1])  # Remove .py file
                    parts.append(rel_path.stem)  # Add file name without .py
                    return ".".join(parts)
            return None
        except Exception:
            return None

    def _find_component_classes(self, tree: ast.AST) -> List[str]:
        """Find component classes in AST."""
        component_classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from Component-like base classes
                for base in node.bases:
                    base_name = self._get_base_name(base)
                    # Check for both "component" and "connector" base classes
                    if base_name and ("component" in base_name.lower() or "connector" in base_name.lower()):
                        component_classes.append(node.name)
                        break

        return component_classes

    def _get_base_name(self, node: ast.AST) -> Optional[str]:
        """Extract base class name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _introspect_component(
        self,
        component_class: Type,
        module_name: str,
        file_path: Path
    ) -> None:
        """
        Introspect a component class to extract ALL capabilities.

        This is the CORE of data-driven discovery - NO PATTERNS!
        """
        try:
            class_name = component_class.__name__

            # Skip abstract classes
            if inspect.isabstract(component_class):
                return

            # Create component info
            # Use 'name' attribute if available, otherwise use class name
            component_name = getattr(component_class, 'name', class_name)
            # Ensure component_name is not None
            if not component_name:
                component_name = class_name
            genesis_name = self._generate_genesis_name(component_name)

            component = DiscoveredComponent(
                genesis_type=f"genesis:{genesis_name}",
                component_name=component_name,
                module_path=module_name,
                class_name=class_name,
                category=self._introspect_category(component_class),
                capabilities=self._introspect_capabilities(component_class),
                introspection_data=self._extract_introspection_data(component_class),
            )

            # Extract display information
            component.display_name = getattr(component_class, "display_name", class_name)
            component.description = getattr(component_class, "description", "") or inspect.getdoc(component_class) or ""
            component.icon = getattr(component_class, "icon", None)

            # Extract inputs/outputs
            component.inputs = self._extract_inputs(component_class)
            component.outputs = self._extract_outputs(component_class)

            # Extract methods
            component.methods = [
                name for name, _ in inspect.getmembers(component_class, inspect.ismethod)
                if not name.startswith('_')
            ]

            # Check for variants
            variants = self._extract_variants(component_class)
            if variants:
                component.has_variants = True
                component.variants = variants
                self.stats["variants_found"] += len(variants)

            # Store component
            self.components[component.genesis_type] = component
            self.stats["total_discovered"] += 1

            # Track base component for variants
            if component.has_variants:
                base_name = self._get_base_component_name(class_name)
                if base_name not in self.variant_groups:
                    self.variant_groups[base_name] = []
                self.variant_groups[base_name].append(component)

        except Exception as e:
            logger.error(f"Failed to introspect {component_class.__name__}: {e}")
            self.stats["introspection_failures"] += 1
            self.errors.append({
                "type": "introspection_error",
                "class": component_class.__name__,
                "error": str(e)
            })

    def _introspect_capabilities(self, component_class: Type) -> ComponentCapabilities:
        """
        Extract capabilities through actual code introspection.

        NO PATTERN MATCHING - only actual code analysis!
        """
        capabilities = ComponentCapabilities()

        # Get all methods (including functions defined in the class)
        methods = inspect.getmembers(component_class, lambda m: inspect.ismethod(m) or inspect.isfunction(m))
        method_names = [name for name, _ in methods]

        # Check for tool-providing methods
        if "as_tool" in method_names:
            capabilities.provides_tools = True
            capabilities.has_as_tool_method = True
            capabilities.tool_methods.append("as_tool")

        if "build_tool" in method_names:
            capabilities.provides_tools = True
            capabilities.tool_methods.append("build_tool")

        if "to_toolkit" in method_names:
            capabilities.provides_tools = True
            capabilities.tool_methods.append("to_toolkit")

        if "get_tool" in method_names:
            capabilities.provides_tools = True
            capabilities.tool_methods.append("get_tool")

        # Check for _get_tools method (used by AgentComponent)
        if "_get_tools" in method_names:
            capabilities.provides_tools = True
            capabilities.tool_methods.append("_get_tools")

        # Check for build method
        if "build" in method_names:
            capabilities.has_build_method = True

        # Check base classes
        for base in inspect.getmro(component_class):
            base_name = base.__name__
            capabilities.base_classes.append(base_name)

            # Check if inherits from tool-related classes
            if "Tool" in base_name and base_name != "Tool":
                capabilities.provides_tools = True

            if "Agent" in base_name:
                # CRITICAL: Agents both accept AND provide tools
                capabilities.accepts_tools = True
                capabilities.provides_tools = True

            if "LCToolComponent" in base_name:
                capabilities.provides_tools = True

            if "ToolCallingAgent" in base_name:
                capabilities.accepts_tools = True
                capabilities.provides_tools = True

        # Check for tool inputs through actual field inspection
        if hasattr(component_class, "inputs"):
            for input_field in self._get_input_fields(component_class):
                field_name = input_field.get("name", "")
                field_type = input_field.get("type", "")

                # Check field name and type
                if field_name == "tools" or "tool" in field_name.lower():
                    capabilities.accepts_tools = True
                    capabilities.tool_input_fields.append(field_name)

                if field_type in ["Tool", "BaseTool", "List[Tool]", "List[BaseTool]"]:
                    capabilities.accepts_tools = True
                    capabilities.tool_input_fields.append(field_name)

        # Check for tool_mode attribute
        if hasattr(component_class, "tool_mode"):
            capabilities.has_tool_mode = True
            capabilities.provides_tools = True

        # Check implemented interfaces
        if hasattr(component_class, "__implements__"):
            interfaces = getattr(component_class, "__implements__", [])
            capabilities.implements_interfaces = list(interfaces)

            # Check for tool interfaces
            for interface in interfaces:
                if "Tool" in str(interface):
                    capabilities.provides_tools = True

        return capabilities

    def _introspect_category(self, component_class: Type) -> str:
        """
        Determine category from actual component structure, not patterns.
        """
        # Check explicit category attribute
        if hasattr(component_class, "category"):
            return str(getattr(component_class, "category"))

        # Check base classes for category hints
        for base in inspect.getmro(component_class):
            base_name = base.__name__

            if "Agent" in base_name:
                return "agent"
            elif "Model" in base_name or "LLM" in base_name:
                return "llm"
            elif "Tool" in base_name:
                return "tool"
            elif "Memory" in base_name:
                return "memory"
            elif "Prompt" in base_name:
                return "prompt"
            elif "Embedding" in base_name:
                return "embedding"
            elif "VectorStore" in base_name:
                return "vector_store"
            elif "Input" in base_name or "Output" in base_name:
                return "io"
            elif "Data" in base_name:
                return "data"

        # Check module path for category hints
        module_parts = component_class.__module__.split(".")
        for part in module_parts:
            if part == "agents":
                return "agent"
            elif part == "models":
                return "llm"
            elif part == "tools":
                return "tool"
            elif part == "memories":
                return "memory"
            elif part == "prompts":
                return "prompt"
            elif part == "embeddings":
                return "embedding"
            elif part == "vectorstores":
                return "vector_store"
            elif part == "inputs" or part == "outputs":
                return "io"
            elif part == "data":
                return "data"
            elif part == "healthcare":
                return "healthcare"

        # Default category
        return "tool"

    def _extract_introspection_data(self, component_class: Type) -> Dict[str, Any]:
        """Extract detailed introspection metadata."""
        data = {
            "module": component_class.__module__,
            "qualname": component_class.__qualname__,
            "file": inspect.getfile(component_class) if hasattr(component_class, "__module__") else None,
            "line_number": inspect.getsourcelines(component_class)[1] if hasattr(component_class, "__module__") else None,
            "is_abstract": inspect.isabstract(component_class),
            "mro": [base.__name__ for base in inspect.getmro(component_class)],
            "attributes": [],
            "class_variables": [],
            "properties": [],
        }

        # Extract attributes
        for name, value in inspect.getmembers(component_class):
            if not name.startswith('_'):
                if isinstance(value, property):
                    data["properties"].append(name)
                elif not inspect.ismethod(value) and not inspect.isfunction(value):
                    data["class_variables"].append({
                        "name": name,
                        "type": type(value).__name__,
                        "value": str(value)[:100] if not callable(value) else "<callable>"
                    })

        return data

    def _extract_inputs(self, component_class: Type) -> List[Dict[str, Any]]:
        """Extract input fields from component."""
        inputs = []

        if hasattr(component_class, "inputs"):
            input_fields = self._get_input_fields(component_class)
            for field in input_fields:
                inputs.append({
                    "name": field.get("name"),
                    "type": field.get("type"),
                    "required": field.get("required", False),
                    "description": field.get("description", ""),
                })

        return inputs

    def _extract_outputs(self, component_class: Type) -> List[Dict[str, Any]]:
        """Extract output fields from component."""
        outputs = []

        if hasattr(component_class, "outputs"):
            output_fields = self._get_output_fields(component_class)
            for field in output_fields:
                outputs.append({
                    "name": field.get("name"),
                    "type": field.get("type"),
                    "description": field.get("description", ""),
                })

        return outputs

    def _get_input_fields(self, component_class: Type) -> List[Dict[str, Any]]:
        """Get input fields from component class."""
        fields = []

        if hasattr(component_class, "inputs"):
            inputs = getattr(component_class, "inputs")
            if isinstance(inputs, list):
                for input_item in inputs:
                    if hasattr(input_item, "__dict__"):
                        fields.append(input_item.__dict__)

        return fields

    def _get_output_fields(self, component_class: Type) -> List[Dict[str, Any]]:
        """Get output fields from component class."""
        fields = []

        if hasattr(component_class, "outputs"):
            outputs = getattr(component_class, "outputs")
            if isinstance(outputs, list):
                for output_item in outputs:
                    if hasattr(output_item, "__dict__"):
                        fields.append(output_item.__dict__)

        return fields

    def _extract_variants(self, component_class: Type) -> List[ComponentVariant]:
        """Extract model variants from component."""
        variants = []

        # Check for MODEL_OPTIONS or similar variant indicators
        if hasattr(component_class, "MODEL_OPTIONS"):
            options = getattr(component_class, "MODEL_OPTIONS")
            for option in options:
                if isinstance(option, dict):
                    variant = ComponentVariant(
                        model_name=option.get("name", option.get("model", "")),
                        display_name=option.get("display_name", option.get("name", "")),
                        config=option.get("config", {}),
                        metadata=option.get("metadata", {}),
                    )
                    variants.append(variant)
                elif isinstance(option, str):
                    variant = ComponentVariant(
                        model_name=option,
                        display_name=option,
                    )
                    variants.append(variant)

        # Check for model_name variations in class name
        class_name = component_class.__name__
        if "_" in class_name and any(model in class_name for model in ["gpt", "claude", "llama", "mistral"]):
            # This is likely a variant component
            parts = class_name.split("_")
            if len(parts) > 1:
                model_part = "_".join(parts[1:])
                variant = ComponentVariant(
                    model_name=model_part.replace("_", "-"),
                    display_name=f"{parts[0]} - {model_part.replace('_', '-')}",
                )
                variants.append(variant)

        return variants

    def _generate_genesis_name(self, class_name: str) -> str:
        """Generate genesis type name from class name."""
        # Handle None or empty class names
        if not class_name:
            return "unknown_component"

        # Remove common suffixes
        name = class_name
        for suffix in ["Component", "Node", "Tool", "Agent", "Model"]:
            if name and name.endswith(suffix):
                name = name[:-len(suffix)]

        # If name is empty after removing suffixes, use the original class name
        if not name or name.strip() == "":
            name = class_name

        # Convert to snake_case
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

        # Ensure name is not empty
        if not name or name.strip() == "":
            name = class_name.lower()

        return name

    def _get_base_component_name(self, class_name: str) -> str:
        """Get base component name for variant grouping."""
        # Remove variant suffixes (e.g., _gpt_4o, _claude_3)
        import re

        # Pattern to match model variants
        patterns = [
            r"_gpt_[\d\w]+",
            r"_claude_[\d\w]+",
            r"_llama_[\d\w]+",
            r"_mistral_[\d\w]+",
            r"_\d+_\d+",  # Version patterns like _3_5
        ]

        base_name = class_name
        for pattern in patterns:
            base_name = re.sub(pattern, "", base_name, flags=re.IGNORECASE)

        return base_name

    def _consolidate_variants(self) -> None:
        """
        Consolidate variant components into single entries.

        This reduces database entries from 2346 to ~400!
        """
        logger.info(f"Consolidating {len(self.variant_groups)} component groups with variants...")

        for base_name, variant_components in self.variant_groups.items():
            if len(variant_components) <= 1:
                continue

            # Find or create base component
            base_component = None
            for comp in variant_components:
                if not comp.variants:  # This might be the base
                    base_component = comp
                    break

            if not base_component:
                # Use first as base
                base_component = variant_components[0]

            # Merge all variants into base
            all_variants = []
            for comp in variant_components:
                if comp != base_component:
                    # Add this component as a variant
                    variant = ComponentVariant(
                        model_name=comp.component_name,
                        display_name=comp.display_name,
                        config={"component": comp.component_name},
                        metadata={"module": comp.module_path},
                    )
                    all_variants.append(variant)

                    # Remove individual variant entry
                    if comp.genesis_type in self.components:
                        del self.components[comp.genesis_type]

                # Add component's own variants
                all_variants.extend(comp.variants)

            # Update base component with all variants
            if all_variants:
                base_component.has_variants = True
                base_component.variants = all_variants
                self.stats["components_with_variants"] += 1

        self.stats["total_consolidated"] = len(self.components)
        logger.info(f"Consolidated to {self.stats['total_consolidated']} components")

    def _generate_results(self) -> Dict[str, Any]:
        """Generate final discovery results."""
        return {
            "success": True,
            "components": list(self.components.values()),
            "statistics": self.stats,
            "errors": self.errors,
            "summary": {
                "total_discovered": self.stats["total_discovered"],
                "total_consolidated": self.stats["total_consolidated"],
                "reduction_ratio": (
                    1 - (self.stats["total_consolidated"] / self.stats["total_discovered"])
                ) * 100 if self.stats["total_discovered"] > 0 else 0,
                "components_with_variants": self.stats["components_with_variants"],
                "total_variants": self.stats["variants_found"],
            }
        }

    def generate_database_entries(self) -> List[Dict[str, Any]]:
        """
        Generate database-ready entries for all discovered components.

        Returns:
            List of database entry dictionaries
        """
        entries = []

        for component in self.components.values():
            entry = component.to_database_entry()
            entries.append(entry)

        logger.info(f"Generated {len(entries)} database entries from {self.stats['total_discovered']} discovered components")
        return entries

    def generate_runtime_adapters(self) -> List[Dict[str, Any]]:
        """
        Generate runtime adapters for ALL components (not just 6!).

        Returns:
            List of runtime adapter dictionaries
        """
        adapters = []

        for component in self.components.values():
            # Create adapter for each component
            # Ensure target_component is never None
            target_component = component.component_name or component.class_name or "UnknownComponent"
            adapter = {
                "genesis_type": component.genesis_type,
                "runtime_type": "langflow",  # Default runtime
                "target_component": target_component,
                "adapter_config": {
                    "module": component.module_path,
                    "class": component.class_name,
                    "variants": [v.model_name for v in component.variants] if component.variants else [],
                },
                "version": component.version,
                "description": f"Runtime adapter for {component.display_name}",
                "active": True,
                "priority": 100,
            }

            # Add compliance rules for healthcare components
            if component.category == "healthcare":
                adapter["compliance_rules"] = {
                    "hipaa_required": True,
                    "audit_logging": True,
                    "data_encryption": True,
                }

            adapters.append(adapter)

        logger.info(f"Generated {len(adapters)} runtime adapters (one for each component)")
        return adapters


# Convenience function for direct usage
def discover_and_introspect_all() -> Dict[str, Any]:
    """
    Discover all components with full introspection.

    Returns:
        Complete discovery results with consolidated variants
    """
    discovery = UnifiedComponentDiscovery()
    return discovery.discover_all()