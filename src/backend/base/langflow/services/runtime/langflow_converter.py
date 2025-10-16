"""
Langflow Runtime Converter with Bidirectional Support.

This module provides bidirectional conversion between Genesis specifications
and Langflow flow JSON format, implementing the RuntimeConverter interface.
"""

from typing import Dict, Any, List, Optional
import logging
import json
from datetime import datetime, timezone

from .base_converter import RuntimeConverter, RuntimeType, ConversionError, ConverterValidationError
from langflow.custom.genesis.spec import FlowConverter, ComponentMapper, VariableResolver, AgentSpec

logger = logging.getLogger(__name__)


class LangflowConverter(RuntimeConverter):
    """
    Bidirectional converter for Langflow runtime.

    Provides conversion from Genesis specifications to Langflow JSON format
    and reverse conversion from Langflow flows back to Genesis specifications.
    """

    def __init__(self):
        """Initialize the Langflow converter."""
        super().__init__(RuntimeType.LANGFLOW)
        self.mapper = ComponentMapper()
        self.flow_converter = FlowConverter(self.mapper)
        self.resolver = VariableResolver()

    def get_runtime_info(self) -> Dict[str, Any]:
        """Return Langflow runtime capabilities and metadata."""
        return {
            "name": "Langflow",
            "version": "1.0.0",
            "runtime_type": self.runtime_type.value,
            "capabilities": [
                "visual_workflow_builder",
                "component_based_architecture",
                "real_time_execution",
                "tool_integration",
                "agent_workflows",
                "multi_llm_support"
            ],
            "supported_components": self._get_supported_components(),
            "bidirectional_support": True,
            "streaming_support": True,
            "export_formats": ["json"],
            "import_formats": ["json", "yaml"],
            "metadata": {
                "description": "Visual workflow builder for AI agents and applications",
                "documentation_url": "https://docs.langflow.org",
                "component_count": len(self._get_supported_components())
            }
        }

    def validate_specification(self, spec: Dict[str, Any]) -> List[str]:
        """
        Validate Genesis specification for Langflow runtime.

        Args:
            spec: Genesis specification dictionary

        Returns:
            List of validation error messages
        """
        errors = []

        # Basic structure validation
        if not isinstance(spec, dict):
            errors.append("Specification must be a dictionary")
            return errors

        # Required fields
        required_fields = ["name", "description", "agentGoal", "components"]
        for field in required_fields:
            if field not in spec:
                errors.append(f"Required field missing: {field}")

        # Validate components
        components = spec.get("components", [])
        if not components:
            errors.append("At least one component is required")
        else:
            component_errors = self._validate_components(components)
            errors.extend(component_errors)

        # Validate component relationships
        if isinstance(components, (list, dict)):
            relationship_errors = self._validate_component_relationships(components)
            errors.extend(relationship_errors)

        return errors

    async def convert_to_runtime(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Genesis specification to Langflow JSON.

        Args:
            spec: Genesis specification dictionary

        Returns:
            Langflow flow JSON structure

        Raises:
            ConversionError: If conversion fails
        """
        try:
            # Validate before conversion
            validation_errors = self.validate_specification(spec)
            if validation_errors:
                raise ConverterValidationError(validation_errors, self.runtime_type.value)

            # Use existing FlowConverter
            flow_json = await self.flow_converter.convert(spec)

            # Add Langflow-specific metadata
            flow_json["converted_by"] = "LangflowConverter"
            flow_json["conversion_timestamp"] = datetime.now(timezone.utc).isoformat()
            flow_json["genesis_spec_version"] = spec.get("version", "1.0.0")

            return flow_json

        except ConverterValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to convert Genesis spec to Langflow: {e}")
            raise ConversionError(
                f"Genesis to Langflow conversion failed: {str(e)}",
                self.runtime_type.value,
                "spec_to_runtime",
                {"original_error": str(e)}
            )

    async def convert_from_runtime(self, runtime_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Langflow JSON back to Genesis specification.

        Args:
            runtime_spec: Langflow flow JSON

        Returns:
            Genesis specification dictionary

        Raises:
            ConversionError: If conversion fails
        """
        try:
            # Validate Langflow JSON structure
            if not self._validate_langflow_json(runtime_spec):
                raise ConversionError(
                    "Invalid Langflow JSON structure",
                    self.runtime_type.value,
                    "runtime_to_spec"
                )

            # Extract flow data
            flow_data = runtime_spec.get("data", {})
            nodes = flow_data.get("nodes", [])
            edges = flow_data.get("edges", [])

            # Convert to Genesis specification
            genesis_spec = self._convert_langflow_to_genesis(runtime_spec, nodes, edges)

            return genesis_spec

        except Exception as e:
            logger.error(f"Failed to convert Langflow to Genesis spec: {e}")
            raise ConversionError(
                f"Langflow to Genesis conversion failed: {str(e)}",
                self.runtime_type.value,
                "runtime_to_spec",
                {"original_error": str(e)}
            )

    def supports_component_type(self, component_type: str) -> bool:
        """Check if Langflow supports given Genesis component type."""
        # Use ComponentMapper to check if type is supported
        try:
            mapping = self.mapper.map_component(component_type)
            return mapping.get("component") is not None
        except Exception:
            return False

    def _get_supported_components(self) -> List[str]:
        """Get list of supported Genesis component types."""
        supported = []

        # Get all mappings from ComponentMapper
        all_mappings = {
            **self.mapper.AUTONOMIZE_MODELS,
            **self.mapper.MCP_MAPPINGS,
            **self.mapper.STANDARD_MAPPINGS
        }

        return list(all_mappings.keys())

    def _validate_components(self, components: Any) -> List[str]:
        """Validate component definitions."""
        errors = []

        if isinstance(components, list):
            for i, component in enumerate(components):
                if not isinstance(component, dict):
                    errors.append(f"Component {i} must be a dictionary")
                    continue

                # Validate required component fields
                required_fields = ["id", "type"]
                for field in required_fields:
                    if field not in component:
                        errors.append(f"Component {i} missing required field: {field}")

                # Validate component type is supported
                component_type = component.get("type")
                if component_type and not self.supports_component_type(component_type):
                    errors.append(f"Unsupported component type: {component_type}")

        elif isinstance(components, dict):
            for comp_id, component in components.items():
                if not isinstance(component, dict):
                    errors.append(f"Component {comp_id} must be a dictionary")
                    continue

                # Type is required
                if "type" not in component:
                    errors.append(f"Component {comp_id} missing required field: type")

                # Validate component type is supported
                component_type = component.get("type")
                if component_type and not self.supports_component_type(component_type):
                    errors.append(f"Unsupported component type: {component_type}")

        else:
            errors.append("Components must be a list or dictionary")

        return errors

    def _validate_component_relationships(self, components: Any) -> List[str]:
        """Validate component provides relationships."""
        errors = []

        # Build component ID set
        component_ids = set()
        component_data = {}

        if isinstance(components, list):
            for comp in components:
                if isinstance(comp, dict) and "id" in comp:
                    component_ids.add(comp["id"])
                    component_data[comp["id"]] = comp
        elif isinstance(components, dict):
            component_ids = set(components.keys())
            component_data = components

        # Validate provides relationships
        for comp_id, comp in component_data.items():
            provides = comp.get("provides", [])
            if provides:
                for i, provide in enumerate(provides):
                    if isinstance(provide, dict):
                        target_id = provide.get("in")
                        if target_id and target_id not in component_ids:
                            errors.append(
                                f"Component {comp_id} provides[{i}] references "
                                f"non-existent component: {target_id}"
                            )

        return errors

    def _validate_langflow_json(self, langflow_json: Dict[str, Any]) -> bool:
        """Validate Langflow JSON structure."""
        # Check required top-level fields
        required_fields = ["data"]
        for field in required_fields:
            if field not in langflow_json:
                return False

        # Check data structure
        data = langflow_json["data"]
        if not isinstance(data, dict):
            return False

        # Check for nodes and edges
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        if not isinstance(nodes, list) or not isinstance(edges, list):
            return False

        return True

    def _convert_langflow_to_genesis(self, langflow_json: Dict[str, Any],
                                   nodes: List[Dict[str, Any]],
                                   edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert Langflow JSON to Genesis specification."""
        # Extract metadata
        name = langflow_json.get("name", "Converted Flow")
        description = langflow_json.get("description", "Flow converted from Langflow")

        # Generate basic Genesis spec structure
        genesis_spec = {
            "id": f"urn:agent:genesis:converted:{name.lower().replace(' ', '-')}:1.0.0",
            "name": name,
            "description": description,
            "domain": "converted",
            "version": "1.0.0",
            "kind": "Single Agent",  # Default, could be inferred from structure
            "agentGoal": "Converted agent workflow",  # Default
            "components": {}
        }

        # Convert nodes to Genesis components
        for node in nodes:
            node_data = node.get("data", {})
            node_id = node.get("id")
            node_type = node_data.get("type")

            if not node_id or not node_type:
                continue

            # Map Langflow component back to Genesis type
            genesis_type = self._map_langflow_to_genesis_type(node_type)

            component = {
                "name": node_data.get("display_name", node_id),
                "kind": self._infer_component_kind(node_type),
                "type": genesis_type,
                "description": node_data.get("description", ""),
            }

            # Extract configuration from node template
            template = node_data.get("node", {}).get("template", {})
            if template:
                config = self._extract_config_from_template(template)
                if config:
                    component["config"] = config

            genesis_spec["components"][node_id] = component

        # Convert edges to provides relationships
        self._add_provides_from_edges(genesis_spec["components"], edges)

        return genesis_spec

    def _map_langflow_to_genesis_type(self, langflow_type: str) -> str:
        """Map Langflow component type back to Genesis type."""
        # Create reverse mapping
        reverse_mapping = {}
        all_mappings = {
            **self.mapper.AUTONOMIZE_MODELS,
            **self.mapper.MCP_MAPPINGS,
            **self.mapper.STANDARD_MAPPINGS
        }

        for genesis_type, mapping in all_mappings.items():
            langflow_component = mapping.get("component")
            if langflow_component:
                reverse_mapping[langflow_component] = genesis_type

        return reverse_mapping.get(langflow_type, f"genesis:{langflow_type.lower()}")

    def _infer_component_kind(self, langflow_type: str) -> str:
        """Infer Genesis component kind from Langflow type."""
        type_lower = langflow_type.lower()

        if "agent" in type_lower:
            return "Agent"
        elif "input" in type_lower or "output" in type_lower:
            return "Data"
        elif "prompt" in type_lower:
            return "Prompt"
        elif "tool" in type_lower or "mcp" in type_lower:
            return "Tool"
        elif "model" in type_lower or "llm" in type_lower:
            return "Model"
        else:
            return "Data"

    def _extract_config_from_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Extract configuration from Langflow node template."""
        config = {}

        for field_name, field_data in template.items():
            if isinstance(field_data, dict) and "value" in field_data:
                value = field_data["value"]
                # Only include non-default values
                if value is not None and value != "":
                    config[field_name] = value

        return config

    def _add_provides_from_edges(self, components: Dict[str, Any], edges: List[Dict[str, Any]]) -> None:
        """Add provides relationships based on Langflow edges."""
        for edge in edges:
            source_id = edge.get("source")
            target_id = edge.get("target")

            if not source_id or not target_id:
                continue

            # Get edge data for useAs mapping
            edge_data = edge.get("data", {})
            target_handle = edge_data.get("targetHandle", {})

            if isinstance(target_handle, str):
                # Parse encoded handle
                try:
                    target_handle = json.loads(target_handle.replace("œ", '"'))
                except:
                    target_handle = {}

            field_name = target_handle.get("fieldName", "input")

            # Map field name to useAs
            use_as = self._map_field_to_use_as(field_name)

            # Add provides to source component
            if source_id in components:
                if "provides" not in components[source_id]:
                    components[source_id]["provides"] = []

                components[source_id]["provides"].append({
                    "useAs": use_as,
                    "in": target_id,
                    "description": f"Provides {use_as} to {target_id}"
                })

    def _map_field_to_use_as(self, field_name: str) -> str:
        """Map Langflow field name to Genesis useAs."""
        field_mapping = {
            "tools": "tools",
            "input_value": "input",
            "system_prompt": "system_prompt",
            "template": "prompt",
            "search_query": "query",
            "message": "input"
        }

        return field_mapping.get(field_name, "input")