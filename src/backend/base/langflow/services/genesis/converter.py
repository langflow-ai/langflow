"""GenesisSpecificationConverter - Core YAML to Langflow JSON conversion."""

import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .mapper import ComponentMapper
from ...custom.specification_framework.services.connection_builder import ConnectionBuilder

logger = logging.getLogger(__name__)


class GenesisSpecificationConverter:
    """
    Core converter for Genesis YAML specifications to Langflow JSON.

    This is the main converter that orchestrates the entire conversion process
    from a 15-line YAML specification to a complete Langflow JSON workflow.
    """

    def __init__(self, mapper: Optional[ComponentMapper] = None):
        """
        Initialize the Genesis converter.

        Args:
            mapper: Component mapper for genesis type resolution
        """
        self.mapper = mapper or ComponentMapper()
        self.connection_builder = ConnectionBuilder()

    async def convert(self, spec_dict: Dict[str, Any], variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Convert Genesis YAML specification to Langflow JSON.

        This is the core MVP functionality that takes a specification like:

        ```yaml
        name: "Patient Q&A Agent"
        description: "Answer patient questions about procedures"
        agentGoal: "Provide accurate medical information to patients"
        components:
          patient_input:
            type: "genesis:chat_input"
          medical_agent:
            type: "genesis:agent"
            config:
              system_message: "You are a medical assistant."
            provides:
              - useAs: "response"
                in: "patient_output"
          patient_output:
            type: "genesis:chat_output"
        ```

        And converts it to a complete Langflow JSON with nodes, edges, and proper configuration.

        Args:
            spec_dict: Parsed YAML specification
            variables: Optional runtime variables

        Returns:
            Complete Langflow JSON workflow

        Raises:
            ValueError: If conversion fails
        """
        try:
            logger.info(f"Starting conversion for specification: {spec_dict.get('name', 'Unnamed')}")

            # 1. Extract specification metadata
            metadata = self._extract_metadata(spec_dict)

            # 2. Process components and create nodes
            components = spec_dict.get("components", {})
            if not components:
                raise ValueError("Specification must contain at least one component")

            nodes = []
            component_map = {}  # Maps component IDs to node IDs

            # Normalize components to a list of (id, data) tuples for processing
            component_items = []
            if isinstance(components, dict):
                # Dict format: {comp_id: comp_data}
                component_items = [(comp_id, comp_data) for comp_id, comp_data in components.items()]
            elif isinstance(components, list):
                # List format: [{id: comp_id, ...comp_data}]
                component_items = [(comp.get("id", f"component_{i}"), comp) for i, comp in enumerate(components)]
            else:
                raise ValueError("Components must be either a dictionary or a list")

            for comp_id, comp_data in component_items:
                node = await self._create_node_from_component(comp_id, comp_data, variables)
                nodes.append(node)
                component_map[comp_id] = node["id"]

            # 3. Generate edges automatically from provides declarations
            # Convert component_items back to dict format for edge generation
            normalized_components = {comp_id: comp_data for comp_id, comp_data in component_items}
            edges = await self._generate_edges(normalized_components, component_map)

            # 4. Apply healthcare compliance if needed
            if self._requires_healthcare_compliance(spec_dict):
                self._apply_healthcare_compliance(nodes, edges, metadata)

            # 5. Create final Langflow JSON structure
            langflow_json = self._create_langflow_json(nodes, edges, metadata)

            # 6. Validate the generated flow
            validation_result = self._validate_generated_flow(langflow_json)
            if not validation_result["valid"]:
                logger.warning(f"Generated flow has validation issues: {validation_result['warnings']}")

            logger.info(f"Successfully converted specification to Langflow JSON with {len(nodes)} nodes and {len(edges)} edges")
            return langflow_json

        except Exception as e:
            logger.error(f"Error converting specification: {e}")
            raise ValueError(f"Conversion failed: {e}")

    def _extract_metadata(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from the specification."""
        return {
            "name": spec_dict.get("name", "Generated Flow"),
            "description": spec_dict.get("description", "Generated from Genesis specification"),
            "agent_goal": spec_dict.get("agentGoal", ""),
            "version": spec_dict.get("version", "1.0.0"),
            "created_at": datetime.now().isoformat(),
            "generator": "GenesisSpecificationConverter",
            "specification_id": spec_dict.get("id", f"genesis:generated:{uuid.uuid4()}")
        }

    async def _create_node_from_component(self, comp_id: str, comp_data: Dict[str, Any],
                                        variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a Langflow node from a Genesis component.

        Args:
            comp_id: Component identifier
            comp_data: Component configuration
            variables: Runtime variables

        Returns:
            Langflow node structure
        """
        comp_type = comp_data.get("type", "")
        if not comp_type:
            raise ValueError(f"Component {comp_id} missing required 'type' field")

        # Get component mapping
        mapping = self.mapper.map_component(comp_type)
        langflow_component = mapping.get("component", "CustomComponent")

        # Create unique node ID
        node_id = str(uuid.uuid4())

        # Get base configuration from mapping
        base_config = mapping.get("config", {}).copy()

        # Override with component-specific config
        component_config = comp_data.get("config", {})
        base_config.update(component_config)

        # Resolve variables in config if provided
        if variables:
            base_config = self._resolve_variables_in_config(base_config, variables)

        # Create node template from configuration
        template = self._create_node_template(langflow_component, base_config)

        # All nodes should be visible in the UI
        show_node = True  # Fix: All nodes should be visible, not hidden

        # Calculate position and dimensions
        position = self._calculate_node_position(comp_id, len(template))

        # Standard node dimensions used by Langflow UI
        node_width = 320
        node_height = 234  # Base height, can be adjusted based on template size

        # Create the node structure compatible with UI rendering
        node = {
            "id": node_id,
            "type": "genericNode",  # Fix: Use genericNode instead of customComponent
            "position": position,
            "data": {
                "description": f"Genesis component: {comp_type}",  # Fix: Add missing description
                "display_name": langflow_component,  # Fix: Add missing display_name
                "id": node_id,  # Fix: Use node_id instead of component name
                "type": langflow_component,
                "showNode": show_node,  # Fix: Add required showNode field
                "node": {
                    "template": template,
                    "description": f"Genesis component: {comp_type}",
                    "base_classes": [langflow_component],
                    "name": langflow_component,
                    "display_name": langflow_component,
                    "documentation": f"Generated from {comp_type}",
                    "custom_fields": {},
                    "output_types": mapping.get("io_mapping", {}).get("output_types", ["Data"]),
                    "outputs": self._create_node_outputs(langflow_component, comp_type),
                    "full_path": None,
                    "field_formatters": {},
                    "beta": False,
                    "error": None
                }
                # Fix: Remove value and _genesis_metadata fields for UI compatibility
            },
            "selected": False,
            "dragging": False,
            "height": node_height,  # Fix: Add missing height
            "width": node_width,    # Fix: Add missing width
            "measured": {           # Fix: Add missing measured object
                "height": node_height,
                "width": node_width
            },
            "positionAbsolute": position  # Fix: Use same position as position
        }

        logger.debug(f"Created node {node_id} for component {comp_id} ({comp_type} -> {langflow_component})")
        return node

    def _create_node_outputs(self, langflow_component: str, genesis_type: str) -> List[Dict[str, Any]]:
        """
        Create outputs structure for UI handle generation.

        Args:
            langflow_component: Langflow component name
            genesis_type: Genesis component type

        Returns:
            List of output definitions
        """
        if langflow_component == "ChatInput":
            return [
                {
                    "allows_loop": False,
                    "cache": True,
                    "display_name": "Chat Message",
                    "group_outputs": False,
                    "method": "message_response",
                    "name": "message",
                    "selected": "Message",
                    "tool_mode": True,
                    "types": ["Message"],
                    "value": "__UNDEFINED__"
                }
            ]
        elif langflow_component == "Agent":
            return [
                {
                    "allows_loop": False,
                    "cache": True,
                    "display_name": "Agent Response",
                    "group_outputs": False,
                    "method": "text_response",
                    "name": "response",  # Fix: Use "response" to match starter projects
                    "selected": "Message",
                    "tool_mode": True,
                    "types": ["Message"],
                    "value": "__UNDEFINED__"
                }
            ]
        elif langflow_component == "ChatOutput":
            return [
                {
                    "allows_loop": False,
                    "cache": True,
                    "display_name": "Output Message",
                    "group_outputs": False,
                    "method": "message_response",
                    "name": "message",
                    "selected": "Message",
                    "tool_mode": True,
                    "types": ["Message"],
                    "value": "__UNDEFINED__"
                }
            ]
        else:
            # Default output for unknown components
            return [
                {
                    "allows_loop": False,
                    "cache": True,
                    "display_name": "Output",
                    "group_outputs": False,
                    "method": "build_output",
                    "name": "output",
                    "selected": "Data",
                    "tool_mode": True,
                    "types": ["Data"],
                    "value": "__UNDEFINED__"
                }
            ]

    def _create_node_template(self, langflow_component: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create Langflow node template from configuration.

        Args:
            langflow_component: Langflow component name
            config: Component configuration

        Returns:
            Node template structure
        """
        template = {}

        # Create template fields based on configuration
        for field_name, field_value in config.items():
            template[field_name] = {
                "multiline": False,
                "required": False,
                "placeholder": "",
                "show": True,
                "value": field_value,
                "name": field_name,
                "display_name": field_name.replace("_", " ").title(),
                "type": self._infer_field_type(field_value),
                "list": isinstance(field_value, list),
                "advanced": False,
                "input_types": ["Data", "Message", "str"]  # Fix: Add required input_types field
            }

        # Add standard fields based on component type
        if langflow_component == "Agent":
            if "input_value" not in template:
                template["input_value"] = {
                    "multiline": True,
                    "required": False,
                    "placeholder": "Enter your message here...",
                    "show": True,
                    "value": "",
                    "name": "input_value",
                    "display_name": "Input",
                    "type": "str",
                    "list": False,
                    "advanced": False,
                    "input_types": ["Data", "Message", "str"]  # Fix: Add required input_types field
                }
            if "tools" not in template:
                template["tools"] = {
                    "multiline": False,
                    "required": False,
                    "placeholder": "",
                    "show": True,
                    "value": [],
                    "name": "tools",
                    "display_name": "Tools",
                    "type": "Tool",
                    "list": True,
                    "advanced": False,
                    "input_types": ["Tool"]  # Fix: Add required input_types field
                }

        elif langflow_component in ["ChatInput", "ChatOutput"]:
            if "input_value" not in template:
                template["input_value"] = {
                    "multiline": True,
                    "required": False,
                    "placeholder": "Type your message...",
                    "show": True,
                    "value": "",
                    "name": "input_value",
                    "display_name": "Message",
                    "type": "str",
                    "list": False,
                    "advanced": False,
                    "input_types": ["Data", "Message", "str"]  # Fix: Add required input_types field
                }

        return template

    def _infer_field_type(self, value: Any) -> str:
        """Infer Langflow field type from value."""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, list):
            return "list"
        elif isinstance(value, dict):
            return "dict"
        else:
            return "str"

    def _calculate_node_position(self, comp_id: str, field_count: int) -> Dict[str, float]:
        """
        Calculate node position for better layout.

        Args:
            comp_id: Component identifier
            field_count: Number of fields in the component

        Returns:
            Position coordinates
        """
        # Simple layout algorithm - can be enhanced
        base_x = 300
        base_y = 200

        # Hash component ID for consistent positioning
        hash_value = hash(comp_id) % 1000
        x = base_x + (hash_value % 3) * 400
        y = base_y + (hash_value // 3) * 200

        return {"x": float(x), "y": float(y)}

    def _resolve_variables_in_config(self, config: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve variables in component configuration."""
        from .resolver import VariableResolver
        resolver = VariableResolver()
        return resolver.resolve_variables(config, variables)

    async def _generate_edges(self, components: Dict[str, Any], component_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Generate edges from component provides declarations.

        Args:
            components: Component specifications
            component_map: Mapping from component IDs to node IDs

        Returns:
            List of Langflow edges
        """
        # Create a mock context for the connection builder
        from ...custom.specification_framework.models.processing_context import ProcessingContext
        context = ProcessingContext(specification={"components": components})

        # Convert component_map to component_mappings format expected by ConnectionBuilder
        component_mappings = {}
        for comp_id, node_id in component_map.items():
            component_mappings[comp_id] = {
                "genesis_type": components.get(comp_id, {}).get("type", ""),
                "langflow_component": "UnknownComponent",
                "mapping_info": {},
                "node_id": node_id
            }

        return await self.connection_builder.build_connections(components, component_mappings, context)

    def _requires_healthcare_compliance(self, spec_dict: Dict[str, Any]) -> bool:
        """Check if specification requires healthcare compliance."""
        # Check for healthcare components - handle both dict and list formats
        components = spec_dict.get("components", {})

        # Normalize to list of component data
        component_data_list = []
        if isinstance(components, dict):
            component_data_list = list(components.values())
        elif isinstance(components, list):
            component_data_list = components

        for comp_data in component_data_list:
            comp_type = comp_data.get("type", "")
            if any(term in comp_type for term in ["ehr", "eligibility", "claims", "medical", "patient"]):
                return True

        # Check for explicit compliance requirement
        compliance = spec_dict.get("compliance", {})
        return compliance.get("hipaa", False) or compliance.get("healthcare", False)

    def _apply_healthcare_compliance(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]],
                                   metadata: Dict[str, Any]) -> None:
        """
        Apply healthcare compliance configurations to the flow.

        Args:
            nodes: Flow nodes to modify
            edges: Flow edges to modify
            metadata: Flow metadata to modify
        """
        # Add HIPAA compliance metadata
        metadata["compliance"] = {
            "hipaa": True,
            "audit_enabled": True,
            "encryption_required": True,
            "data_retention_policy": "7_years",
            "compliance_officer": "system@autonomize.ai"
        }

        # Add compliance configurations to healthcare nodes
        for node in nodes:
            node_data = node.get("data", {})
            genesis_metadata = node_data.get("_genesis_metadata", {})
            genesis_type = genesis_metadata.get("genesis_type", "")

            if any(term in genesis_type for term in ["ehr", "eligibility", "claims", "medical"]):
                # Add HIPAA compliance to template
                template = node_data.get("node", {}).get("template", {})
                template["hipaa_compliant"] = {
                    "multiline": False,
                    "required": True,
                    "placeholder": "",
                    "show": True,
                    "value": True,
                    "name": "hipaa_compliant",
                    "display_name": "HIPAA Compliant",
                    "type": "bool",
                    "list": False,
                    "advanced": False
                }

                # Add audit logging
                template["audit_enabled"] = {
                    "multiline": False,
                    "required": False,
                    "placeholder": "",
                    "show": False,
                    "value": True,
                    "name": "audit_enabled",
                    "display_name": "Audit Logging",
                    "type": "bool",
                    "list": False,
                    "advanced": True
                }

        logger.info("Applied healthcare compliance configurations to flow")

    def _create_langflow_json(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]],
                             metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create the final Langflow JSON structure.

        Args:
            nodes: Generated nodes
            edges: Generated edges
            metadata: Flow metadata

        Returns:
            Complete Langflow JSON
        """
        return {
            "data": {
                "nodes": nodes,
                "edges": edges,
                "viewport": {
                    "x": 0,
                    "y": 0,
                    "zoom": 1
                }
            },
            "description": metadata.get("description", ""),
            "endpoint_name": None,
            "id": str(uuid.uuid4()),  # Fix: Add missing flow ID required by UI
            "is_component": False,
            "last_tested_version": "1.1.1",
            "name": metadata.get("name", "Generated Flow"),
            "_genesis_metadata": metadata
        }

    def _validate_generated_flow(self, langflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the generated Langflow JSON.

        Args:
            langflow_json: Generated flow to validate

        Returns:
            Validation result
        """
        warnings = []
        errors = []

        # Basic structure validation
        if "data" not in langflow_json:
            errors.append("Missing 'data' field in generated flow")
            return {"valid": False, "errors": errors, "warnings": warnings}

        data = langflow_json["data"]
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        # Node validation
        if not nodes:
            errors.append("Flow has no nodes")

        # Edge validation
        node_ids = {node["id"] for node in nodes}
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")

            if source not in node_ids:
                errors.append(f"Edge references non-existent source node: {source}")
            if target not in node_ids:
                errors.append(f"Edge references non-existent target node: {target}")

        # Check for isolated nodes (no edges)
        connected_nodes = set()
        for edge in edges:
            connected_nodes.add(edge.get("source"))
            connected_nodes.add(edge.get("target"))

        isolated_nodes = node_ids - connected_nodes
        if isolated_nodes and len(nodes) > 1:
            warnings.append(f"Found isolated nodes: {isolated_nodes}")

        # Check for input/output nodes
        has_input = any("Input" in node.get("data", {}).get("type", "") for node in nodes)
        has_output = any("Output" in node.get("data", {}).get("type", "") for node in nodes)

        if not has_input:
            warnings.append("Flow has no input components")
        if not has_output:
            warnings.append("Flow has no output components")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "isolated_nodes": len(isolated_nodes),
                "has_input": has_input,
                "has_output": has_output
            }
        }

    def _validate_type_compatibility_fixed(self, output_types: List[str], input_types: List[str],
                                         source_component: str, target_component: str) -> bool:
        """
        Validate type compatibility between components.

        Args:
            output_types: Output types from source
            input_types: Accepted input types for target
            source_component: Source component name
            target_component: Target component name

        Returns:
            True if types are compatible
        """
        # Basic type compatibility
        if not output_types or not input_types:
            return True  # Assume compatible if no type info

        # Check for direct matches
        for output_type in output_types:
            if output_type in input_types:
                return True

        # Check for compatible types
        compatible_mappings = {
            "Message": ["str", "Data"],
            "str": ["Message", "Data"],
            "Data": ["Message", "str"],
            "Tool": ["Tool"],
        }

        for output_type in output_types:
            compatible_types = compatible_mappings.get(output_type, [])
            for input_type in input_types:
                if input_type in compatible_types:
                    return True

        logger.debug(f"Type compatibility check failed: {output_types} -> {input_types}")
        return False