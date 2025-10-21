"""
FlowToSpecConverter - Public converter for Langflow to Genesis specifications.

This module provides a public interface for converting Langflow flows back to
Genesis specifications, exposing the private conversion methods from LangflowConverter.
"""

from typing import Dict, Any, List, Optional, Set
import logging
import json
from datetime import datetime, timezone

from .langflow_converter import LangflowConverter
from .base_converter import RuntimeType, ConversionResult, ConversionError

logger = logging.getLogger(__name__)


class FlowToSpecConverter:
    """
    Public converter for Langflow flows to Genesis specifications.

    Provides a clean interface for reverse conversion with support for:
    - Variable preservation from original flows
    - Metadata extraction and enhancement
    - Batch conversion capabilities
    - Custom naming and domain assignment
    """

    def __init__(self):
        """Initialize the converter with Langflow converter backend."""
        self.langflow_converter = LangflowConverter(RuntimeType.LANGFLOW)
        self._conversion_cache = {}

    def convert_flow_to_spec(
        self,
        flow_data: Dict[str, Any],
        preserve_variables: bool = True,
        include_metadata: bool = False,
        name_override: Optional[str] = None,
        description_override: Optional[str] = None,
        domain_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert a Langflow flow to Genesis specification.

        Args:
            flow_data: Langflow flow JSON data
            preserve_variables: Whether to preserve original variable values
            include_metadata: Whether to include extended metadata
            name_override: Override flow name in specification
            description_override: Override flow description
            domain_override: Override domain (default: converted)

        Returns:
            Dict containing the Genesis specification

        Raises:
            ConversionError: If conversion fails
        """
        try:
            # Validate input
            if not self._validate_flow_data(flow_data):
                raise ConversionError("Invalid flow data structure")

            # Extract flow components
            data = flow_data.get("data", flow_data)
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])

            if not nodes:
                raise ConversionError("Flow contains no nodes")

            logger.info(f"Converting flow with {len(nodes)} nodes and {len(edges)} edges")

            # Use the private conversion method from LangflowConverter
            genesis_spec = self.langflow_converter._convert_langflow_to_genesis(
                flow_data, nodes, edges
            )

            # Apply overrides
            if name_override:
                genesis_spec["name"] = name_override
                # Update ID to match new name
                genesis_spec["id"] = self._generate_spec_id(name_override, domain_override or "converted")

            if description_override:
                genesis_spec["description"] = description_override

            if domain_override:
                genesis_spec["domain"] = domain_override
                # Update ID to match new domain
                genesis_spec["id"] = self._generate_spec_id(
                    genesis_spec.get("name", "converted-flow"), domain_override
                )

            # Preserve variables if requested
            if preserve_variables:
                variables = self._extract_variables_from_flow(flow_data)
                if variables:
                    genesis_spec["variables"] = variables

            # Include extended metadata if requested
            if include_metadata:
                metadata = self._extract_extended_metadata(flow_data)
                genesis_spec.update(metadata)

            # Add conversion metadata
            genesis_spec["_conversion"] = {
                "convertedAt": datetime.now(timezone.utc).isoformat(),
                "converterVersion": "1.0.0",
                "sourceType": "langflow",
                "preservedVariables": preserve_variables,
                "includedMetadata": include_metadata
            }

            return genesis_spec

        except Exception as e:
            logger.error(f"Flow to spec conversion failed: {e}")
            raise ConversionError(f"Conversion failed: {e}") from e

    def convert_flows_batch(
        self,
        flows: List[Dict[str, Any]],
        preserve_variables: bool = True,
        include_metadata: bool = False,
        domain_override: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert multiple Langflow flows to Genesis specifications.

        Args:
            flows: List of Langflow flow JSON data
            preserve_variables: Whether to preserve original variable values
            include_metadata: Whether to include extended metadata
            domain_override: Override domain for all specifications

        Returns:
            List of Genesis specifications

        Raises:
            ConversionError: If any conversion fails
        """
        results = []
        failed_conversions = []

        for i, flow_data in enumerate(flows):
            try:
                spec = self.convert_flow_to_spec(
                    flow_data=flow_data,
                    preserve_variables=preserve_variables,
                    include_metadata=include_metadata,
                    domain_override=domain_override
                )
                results.append(spec)
                logger.info(f"Successfully converted flow {i + 1}/{len(flows)}")

            except Exception as e:
                flow_name = flow_data.get("name", f"flow_{i}")
                failed_conversions.append({"flow": flow_name, "error": str(e)})
                logger.error(f"Failed to convert flow {i + 1}/{len(flows)}: {e}")

        if failed_conversions:
            error_summary = "; ".join([f"{fc['flow']}: {fc['error']}" for fc in failed_conversions])
            raise ConversionError(f"Batch conversion partially failed: {error_summary}")

        return results

    def validate_flow_for_conversion(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate if a flow can be converted to Genesis specification.

        Args:
            flow_data: Langflow flow JSON data

        Returns:
            Dict with validation results and recommendations
        """
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": [],
            "statistics": {}
        }

        try:
            # Basic structure validation
            if not self._validate_flow_data(flow_data):
                validation_result["valid"] = False
                validation_result["errors"].append("Invalid flow data structure")
                return validation_result

            # Extract components
            data = flow_data.get("data", flow_data)
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])

            # Statistics
            validation_result["statistics"] = {
                "nodes_count": len(nodes),
                "edges_count": len(edges),
                "convertible_nodes": 0,
                "unknown_components": []
            }

            # Validate components
            convertible_count = 0
            unknown_components = []

            for node in nodes:
                node_data = node.get("data", {})
                node_type = node_data.get("type")

                if not node_type:
                    validation_result["warnings"].append(f"Node {node.get('id')} has no type")
                    continue

                # Check if component can be mapped
                genesis_type = self.langflow_converter._map_langflow_to_genesis_type(node_type)
                if genesis_type and genesis_type != "unknown":
                    convertible_count += 1
                else:
                    unknown_components.append(node_type)

            validation_result["statistics"]["convertible_nodes"] = convertible_count
            validation_result["statistics"]["unknown_components"] = list(set(unknown_components))

            # Add recommendations
            if unknown_components:
                validation_result["recommendations"].append(
                    f"Consider updating component mappings for: {', '.join(set(unknown_components))}"
                )

            if convertible_count == 0:
                validation_result["valid"] = False
                validation_result["errors"].append("No convertible components found")

            # Check for complex patterns
            if len(nodes) > 20:
                validation_result["recommendations"].append(
                    "Large flow detected - consider breaking into smaller workflows"
                )

        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation failed: {e}")

        return validation_result

    def _validate_flow_data(self, flow_data: Dict[str, Any]) -> bool:
        """Validate basic flow data structure."""
        if not isinstance(flow_data, dict):
            return False

        # Check for direct data or nested data
        data = flow_data.get("data", flow_data)

        if not isinstance(data, dict):
            return False

        nodes = data.get("nodes")
        edges = data.get("edges")

        if not isinstance(nodes, list) or not isinstance(edges, list):
            return False

        return True

    def _generate_spec_id(self, name: str, domain: str) -> str:
        """Generate a proper Genesis specification ID."""
        clean_name = name.lower().replace(" ", "-").replace("_", "-")
        return f"urn:agent:genesis:{domain}:{clean_name}:1.0.0"

    def _extract_variables_from_flow(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract variable definitions from flow data."""
        variables = {}

        # Check for global variables in flow
        if "variables" in flow_data:
            variables.update(flow_data["variables"])

        # Extract from nodes that might contain variables
        data = flow_data.get("data", flow_data)
        nodes = data.get("nodes", [])

        for node in nodes:
            node_data = node.get("data", {})
            template = node_data.get("node", {}).get("template", {})

            # Look for variable-like fields
            for field_name, field_data in template.items():
                if isinstance(field_data, dict):
                    value = field_data.get("value")
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        var_name = value[2:-1]  # Remove ${ and }
                        if var_name not in variables:
                            variables[var_name] = {
                                "type": "string",
                                "description": f"Variable extracted from {node_data.get('display_name', node.get('id'))}",
                                "default": ""
                            }

        return variables

    def _extract_extended_metadata(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract extended metadata for Genesis specification."""
        metadata = {}

        # Try to infer agent characteristics
        data = flow_data.get("data", flow_data)
        nodes = data.get("nodes", [])

        # Count different component types
        component_types = {}
        has_agents = False
        has_tools = False
        has_prompts = False

        for node in nodes:
            node_data = node.get("data", {})
            node_type = node_data.get("type", "unknown")
            component_types[node_type] = component_types.get(node_type, 0) + 1

            # Classify components
            if "agent" in node_type.lower():
                has_agents = True
            elif "tool" in node_type.lower() or "search" in node_type.lower():
                has_tools = True
            elif "prompt" in node_type.lower():
                has_prompts = True

        # Infer workflow characteristics
        if has_agents and has_tools:
            metadata["toolsUse"] = True
            metadata["agencyLevel"] = "ModelBasedReflexAgent"
        elif has_agents:
            metadata["agencyLevel"] = "ReflexiveAgent"
        else:
            metadata["agencyLevel"] = "KnowledgeDrivenWorkflow"

        # Infer interaction mode
        if len(nodes) > 10:
            metadata["interactionMode"] = "Batch"
        else:
            metadata["interactionMode"] = "RequestResponse"

        # Add tags based on components
        tags = []
        if has_agents:
            tags.append("agent-based")
        if has_tools:
            tags.append("tool-enabled")
        if has_prompts:
            tags.append("prompt-driven")

        if tags:
            metadata["tags"] = tags

        # Estimate complexity
        complexity_score = len(nodes) + len(data.get("edges", [])) * 0.5
        if complexity_score > 30:
            metadata["complexity"] = "high"
        elif complexity_score > 15:
            metadata["complexity"] = "medium"
        else:
            metadata["complexity"] = "low"

        return metadata