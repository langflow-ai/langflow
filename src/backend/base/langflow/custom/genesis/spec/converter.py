"""
Genesis Flow Converter - Converts agent specifications to AI Studio flows.

This converter:
1. Maps Genesis types to AI Studio components
2. Creates connections using the provides pattern
3. Generates valid Langflow JSON with proper edge encoding
4. Fixes all critical edge connection issues
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging

from .models import AgentSpec, Component
from .mapper import ComponentMapper
from .resolver import VariableResolver
from langflow.services.spec.component_template_service import component_template_service

logger = logging.getLogger(__name__)


class FlowConverter:
    """Converts agent specifications to AI Studio flows with corrected edge logic."""

    def __init__(self, mapper: Optional[ComponentMapper] = None,
                 resolver: Optional[VariableResolver] = None):
        """Initialize the flow converter."""
        self.mapper = mapper or ComponentMapper()
        self.resolver = resolver or VariableResolver()

    async def convert(self, spec_data: Dict[str, Any],
                     variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Convert a specification to AI Studio flow.

        Args:
            spec_data: Parsed YAML specification as dict
            variables: Runtime variables for resolution

        Returns:
            Complete flow structure for AI Studio
        """
        # Create spec object
        spec = AgentSpec.from_dict(spec_data)

        # Resolve variables if provided
        if variables:
            self.resolver.variables.update(variables)

        # Build nodes
        nodes = await self._build_nodes(spec)

        # Build edges using provides pattern
        edges = await self._build_edges(spec, nodes)

        # Create flow structure
        flow = {
            "data": {
                "nodes": nodes,
                "edges": edges,
                "viewport": {"x": 0, "y": 0, "zoom": 0.5}
            },
            "name": spec.name,
            "description": spec.description,
            "is_component": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "folder": None,
            "id": None,
            "user_id": None,
            "webhook": False,
            "endpoint_name": None
        }

        # Add metadata
        flow["metadata"] = {
            "agentGoal": spec.agentGoal,
            "targetUser": spec.targetUser,
            "valueGeneration": spec.valueGeneration,
            "kind": spec.kind,
            "tags": spec.tags or [],
            "kpis": [kpi.model_dump() for kpi in spec.kpis] if spec.kpis else []
        }

        return flow

    async def _build_nodes(self, spec: AgentSpec) -> List[Dict[str, Any]]:
        """Build nodes from specification components."""
        nodes = []

        for i, component in enumerate(spec.components):
            node = await self._build_node(component, i, spec)
            if node:
                nodes.append(node)

        return nodes

    async def _build_node(self, component: Component, index: int,
                         spec: AgentSpec = None) -> Optional[Dict[str, Any]]:
        """Build a single node from component specification."""
        logger.debug(f"Building node for component: {component.id} (type: {component.type})")

        # Map component type
        mapping = self.mapper.map_component(component.type)
        component_type = mapping["component"]
        # Use dataType for edge creation if specified, otherwise use component_type
        data_type = mapping.get("dataType", component_type)
        logger.debug(f"Mapped {component.type} → {component_type} (dataType: {data_type})")

        # Get component template (this would come from component registry in real implementation)
        template = await self._get_component_template(component_type)

        if not template:
            logger.error(f"Component template not found for: {component_type} (original: {component.type})")
            logger.error(f"Available templates: {list((await component_template_service.load_components()) or {})}")
            return None

        # Calculate position based on component kind
        position = self._calculate_position(index, component.kind)

        # Check if this component is used as a tool
        is_tool = self._is_component_used_as_tool(component)

        # Deep copy template to avoid modifying cached version
        import copy
        node_data = copy.deepcopy(template)

        # Handle tool mode
        if is_tool:
            node_data["tool_mode"] = True
            # Ensure component_as_tool output exists
            if "outputs" in node_data:
                has_tool_output = any(o.get("name") == "component_as_tool"
                                    for o in node_data["outputs"])
                if not has_tool_output:
                    node_data["outputs"].append({
                        "types": ["Tool"],
                        "selected": "Tool",
                        "name": "component_as_tool",
                        "display_name": "Toolset",
                        "method": "to_toolkit",
                        "value": "__UNDEFINED__",
                        "cache": True,
                        "allows_loop": False,
                        "tool_mode": True
                    })

        # Build node structure
        node = {
            "id": component.id,
            "type": "genericNode",
            "position": position,
            "data": {
                "id": component.id,
                "type": data_type,
                "description": component.description or "",
                "display_name": component.name,
                "node": node_data,
                "outputs": node_data.get("outputs", [])
            },
            "dragging": False,
            "height": self._get_node_height(component.kind),
            "selected": False,
            "positionAbsolute": position,
            "width": 384
        }

        # Apply component configuration
        if component.config or mapping.get("config"):
            self._apply_config_to_template(
                node["data"]["node"].get("template", {}),
                {**(mapping.get("config") or {}), **(component.config or {})},
                component, spec
            )

        return node

    def _apply_config_to_template(self, template: Dict[str, Any],
                                 config: Dict[str, Any],
                                 component: Component = None,
                                 spec: AgentSpec = None):
        """Apply component config values to the template."""
        # Special handling for Agent components - use agentGoal as system_prompt
        if (component and "agent" in component.type.lower() and
            "system_prompt" not in config and spec and spec.agentGoal):
            config = dict(config)
            config["system_prompt"] = spec.agentGoal

        # Resolve variables in config
        resolved_config = self.resolver.resolve(config)

        for key, value in resolved_config.items():
            if key in template and isinstance(template[key], dict):
                # Keep unresolved variables for Langflow
                if (isinstance(value, str) and value.startswith("{") and
                    value.endswith("}")):
                    template[key]["value"] = value
                else:
                    template[key]["value"] = value

    async def _build_edges(self, spec: AgentSpec,
                          nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build edges from provides declarations with fixed logic."""
        logger.debug(f"Building edges for {len(nodes)} nodes")
        edges = []
        node_map = {node["id"]: node for node in nodes}
        logger.debug(f"Node map created with IDs: {list(node_map.keys())}")

        # Process each component's provides declarations
        for component in spec.components:
            if not component.provides:
                logger.debug(f"Component {component.id} has no provides declarations")
                continue

            source_id = component.id
            if source_id not in node_map:
                logger.warning(f"Source node '{source_id}' not found in node map")
                continue

            logger.debug(f"Processing {len(component.provides)} provides for component {source_id}")

            # Process each provides declaration
            for provide in component.provides:
                logger.debug(f"Creating edge: {source_id} → {provide.in_} (useAs: {provide.useAs})")
                edge = self._create_edge_from_provides(
                    source_id, provide, node_map, component
                )
                if edge:
                    edges.append(edge)
                    logger.debug(f"Edge created: {edge['id']}")
                else:
                    logger.warning(f"Failed to create edge: {source_id} → {provide.in_}")

        logger.info(f"Created {len(edges)} edges from {len(spec.components)} components")
        return edges

    def _create_edge_from_provides(self, source_id: str, provide: Any,
                                  node_map: Dict[str, Dict[str, Any]],
                                  source_component: Component) -> Optional[Dict[str, Any]]:
        """Create an edge from provides declaration with FIXED logic."""
        # CRITICAL FIX: Handle Pydantic field alias correctly
        target_id = getattr(provide, 'in_', None) or getattr(provide, 'in', None)
        use_as = getattr(provide, 'useAs', None)

        # Debug logging for data access
        logger.debug(f"Provides data access: target_id={target_id}, use_as={use_as}")
        logger.debug(f"Provide object type: {type(provide)}")
        logger.debug(f"Provide object attributes: {dir(provide) if hasattr(provide, '__dict__') else 'No attributes'}")

        if not target_id or not use_as:
            logger.error(f"Invalid provides: target_id={target_id}, use_as={use_as}")
            logger.error(f"Provide object dump: {provide}")
            return None

        if target_id not in node_map:
            logger.error(f"Target node '{target_id}' not found for provides connection")
            logger.debug(f"Available nodes: {list(node_map.keys())}")
            return None

        # Get nodes
        source_node = node_map[source_id]
        target_node = node_map[target_id]

        # Get actual component types
        source_type = source_node["data"]["type"]
        target_type = target_node["data"]["type"]

        # FIXED: Determine output field with improved logic
        output_field = self._determine_output_field_fixed(
            use_as, source_node, source_type, provide
        )
        logger.debug(f"Determined output field: {output_field} for {source_type}")

        # FIXED: Map useAs to correct input field
        input_field = self._map_use_as_to_field_fixed(use_as, target_type)
        logger.debug(f"Mapped useAs '{use_as}' to input field: {input_field} for {target_type}")

        # Get output types
        output_types = self._get_output_types_fixed(source_node, output_field, source_type)
        logger.debug(f"Output types: {output_types}")

        # Get input types
        input_types = self._get_input_types_fixed(target_node, input_field)
        logger.debug(f"Input types: {input_types}")

        # Validate type compatibility
        if not self._validate_type_compatibility_fixed(
            output_types, input_types, source_type, target_type
        ):
            logger.warning(
                f"Type mismatch: {source_type}.{output_field} ({output_types}) "
                f"-> {target_type}.{input_field} ({input_types})"
            )
            return None

        # FIXED: Determine handle type correctly
        handle_type = self._determine_handle_type_fixed(input_field, input_types)

        # Create handle objects
        source_handle = {
            "dataType": source_type,
            "id": source_id,
            "name": output_field,
            "output_types": output_types
        }

        target_handle = {
            "fieldName": input_field,
            "id": target_id,
            "inputTypes": input_types,
            "type": handle_type
        }

        # CRITICAL FIX: Different JSON encoding for edge ID vs handle strings
        # Edge ID: Use compact format (no spaces) - for the ID string
        source_handle_id = json.dumps(source_handle, separators=(",", ":")).replace('"', "œ")
        target_handle_id = json.dumps(target_handle, separators=(",", ":")).replace('"', "œ")

        # Handle strings: Use spaced format - for sourceHandle/targetHandle fields
        source_handle_encoded = json.dumps(source_handle, separators=(", ", ": ")).replace('"', "œ")
        target_handle_encoded = json.dumps(target_handle, separators=(", ", ": ")).replace('"', "œ")

        # CRITICAL FIX: Use original working edge ID format with compact encoding
        edge = {
            "className": "",
            "data": {
                "sourceHandle": source_handle,
                "targetHandle": target_handle,
                "label": getattr(provide, 'description', '') or ""
            },
            "id": f"reactflow__edge-{source_id}{source_handle_id}-{target_id}{target_handle_id}",
            "selected": False,
            "source": source_id,
            "sourceHandle": source_handle_encoded,
            "target": target_id,
            "targetHandle": target_handle_encoded
        }

        return edge

    def _determine_output_field_fixed(self, use_as: str, source_node: Dict[str, Any],
                                     source_type: str, provide: Any) -> str:
        """FIXED output field determination logic."""
        # Check if specific output is requested
        if hasattr(provide, 'fromOutput') and provide.fromOutput:
            return provide.fromOutput

        # Special case for tools
        if use_as in ["tool", "tools"]:
            return "component_as_tool"

        # Get actual outputs from node data
        outputs = self._get_component_outputs_fixed(source_node)

        if outputs:
            # For single output, use it
            if len(outputs) == 1:
                return outputs[0].get("name", "output")

            # For multiple outputs, intelligent selection
            if use_as == "input" and any(o.get("name") == "message" for o in outputs):
                return "message"
            elif use_as == "system_prompt" and any(o.get("name") == "prompt" for o in outputs):
                return "prompt"
            elif any(o.get("name") == "response" for o in outputs):
                return "response"
            else:
                return outputs[0].get("name", "output")

        # Component-specific defaults with AutonomizeModel support
        if "ChatInput" in source_type:
            return "message"
        elif "AutonomizeModel" in source_type:
            return "prediction"  # FIXED: AutonomizeModel outputs prediction
        elif "Agent" in source_type:
            return "response"
        elif "Prompt" in source_type or "GenesisPrompt" in source_type:
            return "prompt"
        elif "Memory" in source_type:
            return "memory"
        else:
            return "output"

    def _map_use_as_to_field_fixed(self, use_as: str, target_type: str) -> str:
        """FIXED field mapping with AutonomizeModel support."""
        # Component-specific mappings
        if "AutonomizeModel" in target_type:
            if use_as in ["input", "query", "text"]:
                return "search_query"  # FIXED: AutonomizeModel uses search_query

        # Standard mappings
        field_mappings = {
            "input": "input_value",
            "tool": "tools",
            "tools": "tools",
            "system_prompt": "system_prompt",  # CRITICAL FIX: Agent uses system_prompt, not system_message
            "prompt": "template",
            "query": "search_query",  # For AutonomizeModel
            "llm": "llm",
            "response": "input_value",
            "message": "input_value",
            "text": "input_value",
            "output": "input_value",
            "memory": "memory"
        }

        return field_mappings.get(use_as, use_as)

    def _get_component_outputs_fixed(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """FIXED: Get outputs from correct locations."""
        # Try multiple locations
        outputs = (
            node.get("data", {}).get("outputs", []) or
            node.get("data", {}).get("node", {}).get("outputs", []) or
            []
        )
        return outputs

    def _get_output_types_fixed(self, node: Dict[str, Any], output_field: str,
                               source_type: str) -> List[str]:
        """FIXED output types determination."""
        # Special cases
        if output_field == "component_as_tool":
            return ["Tool"]

        # Check actual outputs
        outputs = self._get_component_outputs_fixed(node)
        for output in outputs:
            if output.get("name") == output_field:
                types = output.get("types", [])
                if types:
                    return types

        # Component-specific defaults
        if "AutonomizeModel" in source_type:
            return ["Data"]  # FIXED: AutonomizeModel outputs Data
        elif "ChatInput" in source_type or "ChatOutput" in source_type:
            return ["Message"]
        elif "Agent" in source_type:
            return ["Message"]
        elif "Prompt" in source_type:
            return ["Message"]
        elif "Tool" in output_field:
            return ["Tool"]
        else:
            return ["Message"]

    def _get_input_types_fixed(self, node: Dict[str, Any], input_field: str) -> List[str]:
        """FIXED input types determination."""
        # Check template for input types
        template = node.get("data", {}).get("node", {}).get("template", {})
        if input_field in template and isinstance(template[input_field], dict):
            input_types = template[input_field].get("input_types", [])
            if input_types:
                return input_types

        # Default types based on field name
        field_type_map = {
            "tools": ["Tool"],
            "input_value": ["Data", "DataFrame", "Message"],  # ChatOutput accepts multiple
            "search_query": ["Message", "str"],  # AutonomizeModel
            "system_message": ["Message"],
            "template": ["Message", "str"],
            "memory": ["Message"]
        }

        return field_type_map.get(input_field, ["Message", "str"])

    def _determine_handle_type_fixed(self, input_field: str, input_types: List[str]) -> str:
        """FIXED handle type determination - CRITICAL FIX."""
        # Tools always use "other"
        if input_field == "tools" or "Tool" in input_types:
            return "other"

        # CRITICAL FIX: ChatOutput input_value accepts multiple types -> "other" not "str"
        if input_field == "input_value" and len(input_types) > 1:
            return "other"

        # Multiple types use "other"
        if len(input_types) > 1:
            return "other"

        # Single Message type uses "str"
        if input_types == ["Message"]:
            return "str"

        # Data/DataFrame use "other"
        if "Data" in input_types or "DataFrame" in input_types:
            return "other"

        # Single type uses the type name
        if len(input_types) == 1:
            return input_types[0].lower()

        return "str"

    def _validate_type_compatibility_fixed(self, output_types: List[str],
                                          input_types: List[str],
                                          source_type: str, target_type: str) -> bool:
        """FIXED type compatibility validation."""
        # Tool connections
        if "Tool" in output_types and "Tool" in input_types:
            return True

        # Direct type matches
        if any(otype in input_types for otype in output_types):
            return True

        # AutonomizeModel Data -> input_value compatibility
        if "Data" in output_types and "input_value" in str(input_types):
            return True

        # Compatible conversions
        compatible = {
            "Message": ["str", "text", "Text", "Data"],
            "str": ["Message", "text", "Text"],
            "Data": ["dict", "object", "any", "Message"],
            "DataFrame": ["Data", "object", "any"]
        }

        for otype in output_types:
            if otype in compatible:
                if any(ctype in input_types for ctype in compatible[otype]):
                    return True

        # Accept any/object inputs
        if "any" in input_types or "object" in input_types:
            return True

        return False

    def _calculate_position(self, index: int, kind: str) -> Dict[str, int]:
        """Calculate node position based on index and kind."""
        kind_positions = {
            "Data": {"x": 50, "y": 200},    # Inputs on left
            "Agent": {"x": 400, "y": 200},   # Agents in center
            "Prompt": {"x": 200, "y": 50},   # Prompts above
            "Tool": {"x": 200, "y": 350},    # Tools below
            "Model": {"x": 200, "y": 350},   # Models below
        }

        base_pos = kind_positions.get(kind, {"x": 300, "y": 300})

        # Offset for multiple components
        offset_x = (index % 4) * 200
        offset_y = (index // 4) * 150

        return {
            "x": base_pos["x"] + offset_x,
            "y": base_pos["y"] + offset_y
        }

    def _get_node_height(self, kind: str) -> int:
        """Get node height based on kind."""
        heights = {
            "Agent": 500,
            "Prompt": 300,
            "Tool": 350,
            "Model": 400,
            "Data": 250
        }
        return heights.get(kind, 350)

    def _is_component_used_as_tool(self, component: Component) -> bool:
        """Check if component is used as a tool."""
        if not component.provides:
            return False

        return any(p.useAs in ["tool", "tools"] for p in component.provides)

    async def _get_component_template(self, component_type: str) -> Optional[Dict[str, Any]]:
        """Get real component template from Langflow component registry."""
        try:
            # Get template from the real component template service
            template = await component_template_service.get_component_template(component_type)

            if template:
                logger.debug(f"Found template for component: {component_type}")
                return template
            else:
                logger.warning(f"No template found for component type: {component_type}, creating fallback")
                # Return a robust fallback template based on component type
                return self._create_fallback_template(component_type)

        except Exception as e:
            logger.error(f"Error getting component template for {component_type}: {e}")
            # Return basic fallback on error
            return self._create_fallback_template(component_type)

    def _create_fallback_template(self, component_type: str) -> Dict[str, Any]:
        """Create a fallback template for unknown components."""
        # Component-specific fallbacks
        if "Input" in component_type:
            return {
                "outputs": [{"name": "message", "types": ["Message"]}],
                "template": {},
                "base_classes": [component_type],
                "description": f"Input component: {component_type}",
                "display_name": component_type
            }
        elif "Output" in component_type:
            return {
                "outputs": [{"name": "message", "types": ["Message"]}],
                "template": {"input_value": {"input_types": ["Message", "Text"]}},
                "base_classes": [component_type],
                "description": f"Output component: {component_type}",
                "display_name": component_type
            }
        elif "Agent" in component_type:
            return {
                "outputs": [{"name": "response", "types": ["Message"]}],
                "template": {
                    "input_value": {"input_types": ["Message"]},
                    "system_message": {"input_types": ["Message"]},
                    "tools": {"input_types": ["Tool"]}
                },
                "base_classes": [component_type],
                "description": f"Agent component: {component_type}",
                "display_name": component_type
            }
        elif "Tool" in component_type or "MCP" in component_type:
            return {
                "outputs": [{"name": "component_as_tool", "types": ["Tool"]}],
                "template": {},
                "base_classes": [component_type],
                "description": f"Tool component: {component_type}",
                "display_name": component_type
            }
        else:
            # Generic fallback
            return {
                "outputs": [{"name": "output", "types": ["Any"]}],
                "template": {"input_value": {"input_types": ["Any"]}},
                "base_classes": [component_type],
                "description": f"Generic component: {component_type}",
                "display_name": component_type
            }