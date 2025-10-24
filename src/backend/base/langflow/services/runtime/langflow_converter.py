"""
Enhanced Langflow Converter implementation.

This module implements the Langflow-specific converter with Phase 3 enhancements:
- Enhanced type compatibility validation
- Comprehensive edge validation and connection rules
- Performance optimization capabilities
- Integration with existing FlowConverter
"""

from typing import Dict, Any, List, Optional, Set
import logging
import json
import asyncio
from datetime import datetime, timezone

from .base_converter import (
    RuntimeConverter,
    RuntimeType,
    ConversionResult,
    ComponentCompatibility,
    EdgeValidationResult,
    ValidationOptions,
    ConversionError,
    ConverterValidationError
)
# Legacy Genesis implementation removed during consolidation cleanup
# from langflow.custom.genesis.spec import FlowConverter, ComponentMapper, VariableResolver

logger = logging.getLogger(__name__)


class LangflowConverter(RuntimeConverter):
    """
    Enhanced Langflow converter with Phase 3 improvements.

    Integrates with the existing FlowConverter while adding:
    - Enhanced validation with type compatibility checking
    - Comprehensive edge validation and connection rules
    - Performance optimization capabilities
    - Better error handling and metadata collection
    """

    def __init__(self, runtime_type: RuntimeType = RuntimeType.LANGFLOW):
        """Initialize the Langflow converter."""
        super().__init__(runtime_type)
        # Legacy Genesis components removed during consolidation cleanup
        # self.mapper = ComponentMapper()
        # self.flow_converter = FlowConverter(self.mapper)
        # self.resolver = VariableResolver()
        self.mapper = None  # TODO: Replace with current implementation
        self.flow_converter = None  # TODO: Replace with current implementation
        self.resolver = None  # TODO: Replace with current implementation
        self._supported_components_cache = None

    def get_runtime_info(self) -> Dict[str, Any]:
        """Return Langflow runtime capabilities and metadata."""
        return {
            "name": "Langflow",
            "version": "1.0.0",
            "runtime_type": self.runtime_type.value,
            "capabilities": [
                "visual_flow_design",
                "component_library",
                "real_time_execution",
                "streaming_support",
                "api_integration",
                "custom_components"
            ],
            "supported_components": list(self.get_supported_components()),
            "bidirectional_support": True,  # Both spec -> flow and flow -> spec
            "streaming_support": True,
            "performance_modes": ["fast", "balanced", "thorough"],
            "validation_features": [
                "type_compatibility",
                "edge_validation",
                "component_existence",
                "tool_connections",
                "configuration_validation"
            ],
            "export_formats": ["json"],
            "import_formats": ["json", "yaml"],
            "metadata": {
                "description": "Enhanced Langflow converter with comprehensive validation",
                "integration": "FlowConverter",
                "performance_optimizations": True,
                "edge_validation": True,
                "component_count": len(self.get_supported_components())
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

    async def convert_to_runtime(self,
                               spec: Dict[str, Any],
                               variables: Optional[Dict[str, Any]] = None,
                               validation_options: Optional[ValidationOptions] = None) -> ConversionResult:
        """Convert Genesis specification to Langflow format with enhanced validation."""
        conversion_start = datetime.utcnow()
        options = validation_options or ValidationOptions()

        try:
            # Pre-conversion validation
            if self.validation_enabled and options.enable_type_checking:
                validation_result = await self.pre_conversion_validation(spec, options)
                if not validation_result["valid"]:
                    return ConversionResult(
                        success=False,
                        runtime_type=self.runtime_type,
                        errors=validation_result["errors"],
                        warnings=validation_result["warnings"],
                        metadata={
                            "validation_failed": True,
                            "validation_result": validation_result
                        }
                    )

            # Convert using existing FlowConverter
            flow_data = await self.flow_converter.convert(spec, variables)

            # Add Langflow-specific metadata
            flow_data["converted_by"] = "LangflowConverter"
            flow_data["conversion_timestamp"] = datetime.now(timezone.utc).isoformat()
            flow_data["genesis_spec_version"] = spec.get("version", "1.0.0")

            # Calculate performance metrics
            conversion_duration = (datetime.utcnow() - conversion_start).total_seconds()
            components_count = len(self._get_components_list(spec))

            return ConversionResult(
                success=True,
                runtime_type=self.runtime_type,
                flow_data=flow_data,
                metadata={
                    "conversion_method": "FlowConverter.convert",
                    "components_processed": components_count,
                    "variables_applied": len(variables) if variables else 0,
                    "langflow_metadata": {
                        "flow_id": flow_data.get("id"),
                        "node_count": len(flow_data.get("data", {}).get("nodes", [])),
                        "edge_count": len(flow_data.get("data", {}).get("edges", []))
                    }
                },
                performance_metrics={
                    "conversion_duration_seconds": conversion_duration,
                    "components_per_second": components_count / max(conversion_duration, 0.001),
                    "memory_estimate_mb": self._estimate_memory_usage(spec)
                }
            )

        except Exception as e:
            logger.error(f"Langflow conversion failed: {e}")
            return ConversionResult(
                success=False,
                runtime_type=self.runtime_type,
                errors=[f"Conversion failed: {e}"],
                metadata={
                    "conversion_duration_seconds": (datetime.utcnow() - conversion_start).total_seconds(),
                    "error_type": type(e).__name__
                }
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
        """Check if component type is supported by Langflow."""
        return component_type in self.get_supported_components()

    def get_supported_components(self) -> Set[str]:
        """Get set of Genesis component types supported by Langflow."""
        if self._supported_components_cache is None:
            # Get all mapped components from ComponentMapper
            supported = set()

            # Standard mappings
            supported.update(self.mapper.STANDARD_MAPPINGS.keys())
            supported.update(self.mapper.MCP_MAPPINGS.keys())
            supported.update(self.mapper.AUTONOMIZE_MODELS.keys())

            # Add any database-mapped components
            try:
                available_components = self.mapper.get_available_components()
                if "genesis_mapped" in available_components:
                    supported.update(available_components["genesis_mapped"].keys())
            except Exception as e:
                logger.warning(f"Could not get database-mapped components: {e}")

            self._supported_components_cache = supported

        return self._supported_components_cache

    def validate_component_compatibility(self, component: Dict[str, Any]) -> ComponentCompatibility:
        """Validate component compatibility with Langflow."""
        comp_type = component.get("type", "")
        comp_id = component.get("id", "unknown")

        # Get mapping information
        mapping = self.mapper.map_component(comp_type)
        langflow_component = mapping.get("component", "CustomComponent")

        # Get I/O mapping
        io_mapping = self.mapper.get_component_io_mapping(langflow_component)

        # Determine constraints
        constraints = []
        performance_hints = {}

        # Component-specific constraints
        if comp_type.startswith("genesis:crewai"):
            constraints.append("Requires CrewAI library for execution")
            performance_hints["memory"] = "CrewAI components use additional memory"

        if comp_type == "genesis:mcp_tool":
            constraints.append("Requires MCP server configuration")
            performance_hints["startup"] = "MCP tools may have initialization delay"

        if comp_type.startswith("genesis:autonomize"):
            constraints.append("Requires Autonomize model access")
            performance_hints["api"] = "External API calls may affect performance"

        # Tool capability validation
        if component.get("asTools", False):
            if comp_type not in ["genesis:mcp_tool", "genesis:knowledge_hub_search", "genesis:api_request"]:
                constraints.append("Component may not be optimized for tool usage")

        return ComponentCompatibility(
            genesis_type=comp_type,
            runtime_component=langflow_component,
            supported_inputs=io_mapping.get("input_fields", []),
            supported_outputs=io_mapping.get("output_fields", []),
            configuration_schema=mapping.get("config", {}),
            constraints=constraints,
            performance_hints=performance_hints
        )

    def get_runtime_constraints(self) -> Dict[str, Any]:
        """Get Langflow-specific constraints and limitations."""
        return {
            "max_components": 50,  # Reasonable limit for UI performance
            "max_memory_mb": 4096,  # 4GB memory limit
            "max_concurrent_tasks": 10,  # Concurrent execution limit
            "supported_file_types": ["json", "yaml"],
            "max_flow_size_mb": 100,  # Maximum flow file size
            "component_limits": {
                "max_agents": 10,
                "max_tools_per_agent": 5,
                "max_nested_depth": 3
            },
            "performance_constraints": {
                "max_edges_per_component": 5,
                "max_total_edges": 100,
                "recommended_components": 20
            }
        }

    async def validate_edge_connection(self,
                                     source_comp: Dict[str, Any],
                                     target_comp: Dict[str, Any],
                                     connection: Dict[str, Any]) -> EdgeValidationResult:
        """Enhanced edge validation with Langflow-specific rules."""
        errors = []
        warnings = []
        suggestions = []

        source_id = source_comp.get("id", "unknown")
        target_id = target_comp.get("id", "unknown")
        source_type = source_comp.get("type", "")
        target_type = target_comp.get("type", "")
        use_as = connection.get("useAs", "")

        try:
            # Basic connection validation
            if not use_as:
                errors.append("Missing 'useAs' field in connection")

            if not connection.get("in"):
                errors.append("Missing 'in' field in connection")

            # Type compatibility validation using FlowConverter logic
            compatibility_score = await self._calculate_langflow_compatibility(
                source_comp, target_comp, connection
            )

            # Tool connection validation
            if use_as == "tools":
                tool_validation = self._validate_tool_connection(source_comp, target_comp)
                errors.extend(tool_validation["errors"])
                warnings.extend(tool_validation["warnings"])
                suggestions.extend(tool_validation["suggestions"])

            # Agent input validation
            elif use_as == "input":
                input_validation = self._validate_input_connection(source_comp, target_comp)
                errors.extend(input_validation["errors"])
                warnings.extend(input_validation["warnings"])

            # System prompt validation
            elif use_as == "system_prompt":
                prompt_validation = self._validate_prompt_connection(source_comp, target_comp)
                errors.extend(prompt_validation["errors"])
                warnings.extend(prompt_validation["warnings"])

            # Performance suggestions
            if compatibility_score < 0.7:
                suggestions.append(f"Consider optimizing connection {source_id} -> {target_id}")

            # Langflow-specific validations
            if len(source_comp.get("provides", [])) > 5:
                warnings.append(f"Component {source_id} has many outgoing connections, may impact UI performance")

            return EdgeValidationResult(
                valid=len(errors) == 0,
                source_component=source_id,
                target_component=target_id,
                connection_type=use_as,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                compatibility_score=compatibility_score
            )

        except Exception as e:
            logger.error(f"Edge validation failed: {e}")
            return EdgeValidationResult(
                valid=False,
                source_component=source_id,
                target_component=target_id,
                connection_type=use_as,
                errors=[f"Edge validation error: {e}"],
                warnings=[],
                suggestions=[],
                compatibility_score=0.0
            )

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

    # Phase 3 Langflow-specific validation methods

    def _validate_tool_connection(self,
                                source_comp: Dict[str, Any],
                                target_comp: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate tool connection using FlowConverter logic."""
        errors = []
        warnings = []
        suggestions = []

        source_type = source_comp.get("type", "")
        target_type = target_comp.get("type", "")

        # Check if source is marked as tool-capable
        if not source_comp.get("asTools", False):
            if source_type not in ["genesis:mcp_tool", "genesis:knowledge_hub_search", "genesis:api_request"]:
                errors.append(f"Component {source_comp.get('id')} not marked as tool (asTools: true)")

        # Check if target can accept tools
        if "agent" not in target_type.lower():
            warnings.append(f"Component {target_comp.get('id')} may not support tool connections")

        # Use FlowConverter's tool validation logic
        try:
            is_valid = self.flow_converter._validate_tool_connection_capability(
                source_type, target_type, source_comp
            )
            if not is_valid:
                errors.append(f"Tool connection not supported: {source_type} -> {target_type}")

        except Exception as e:
            warnings.append(f"Could not validate tool connection capability: {e}")

        return {"errors": errors, "warnings": warnings, "suggestions": suggestions}

    def _validate_input_connection(self,
                                 source_comp: Dict[str, Any],
                                 target_comp: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate input connection."""
        errors = []
        warnings = []

        source_type = source_comp.get("type", "")
        target_type = target_comp.get("type", "")

        # Check valid input sources
        valid_input_types = ["genesis:chat_input", "genesis:prompt"]
        if source_type not in valid_input_types:
            warnings.append(f"Unusual input source type: {source_type}")

        # Check valid input targets
        valid_target_types = ["genesis:agent", "genesis:crewai_agent"]
        if not any(target in target_type for target in valid_target_types):
            warnings.append(f"Component {target_comp.get('id')} may not accept input connections")

        return {"errors": errors, "warnings": warnings}

    def _validate_prompt_connection(self,
                                  source_comp: Dict[str, Any],
                                  target_comp: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate system prompt connection."""
        errors = []
        warnings = []

        source_type = source_comp.get("type", "")
        target_type = target_comp.get("type", "")

        # Check valid prompt sources
        if source_type != "genesis:prompt":
            errors.append(f"System prompt must come from genesis:prompt, not {source_type}")

        # Check valid prompt targets
        valid_target_types = ["genesis:agent", "genesis:crewai_agent"]
        if not any(target in target_type for target in valid_target_types):
            errors.append(f"System prompt can only connect to agents, not {target_type}")

        return {"errors": errors, "warnings": warnings}

    async def _calculate_langflow_compatibility(self,
                                              source_comp: Dict[str, Any],
                                              target_comp: Dict[str, Any],
                                              connection: Dict[str, Any]) -> float:
        """Calculate compatibility score using Langflow-specific logic."""
        try:
            score = 1.0

            source_type = source_comp.get("type", "")
            target_type = target_comp.get("type", "")
            use_as = connection.get("useAs", "")

            # Get component mappings
            source_mapping = self.mapper.map_component(source_type)
            target_mapping = self.mapper.map_component(target_type)

            # Check if components exist in Langflow
            if source_mapping["component"] == "CustomComponent":
                score -= 0.2
            if target_mapping["component"] == "CustomComponent":
                score -= 0.2

            # Use FlowConverter's type compatibility logic
            try:
                source_io = self.mapper.get_component_io_mapping(source_mapping["component"])
                target_io = self.mapper.get_component_io_mapping(target_mapping["component"])

                output_types = source_io.get("output_types", ["Message", "Data"])
                input_types = target_io.get("input_types", ["Message", "Data", "str"])

                is_compatible = self.flow_converter._validate_type_compatibility_fixed(
                    output_types, input_types,
                    source_mapping["component"], target_mapping["component"]
                )

                if is_compatible:
                    score += 0.2
                else:
                    score -= 0.3

            except Exception as e:
                logger.debug(f"Type compatibility check failed: {e}")
                # Fallback to basic compatibility
                pass

            # Tool-specific scoring
            if use_as == "tools":
                if source_comp.get("asTools", False):
                    score += 0.1
                else:
                    score -= 0.2

            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Error calculating Langflow compatibility: {e}")
            return 0.5

    def clear_cache(self):
        """Clear cached data."""
        self._supported_components_cache = None