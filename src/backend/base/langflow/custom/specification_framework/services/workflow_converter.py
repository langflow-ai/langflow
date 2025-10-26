"""
Professional Workflow Converter Service for the Dynamic Agent Specification Framework.

This service handles the conversion of validated agent specifications into Langflow-compatible
workflows with comprehensive error handling, performance optimization, and healthcare compliance.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from ..models.processing_context import ProcessingContext
from ..models.workflow_models import WorkflowConversionResult
from ..utils.variable_resolver import VariableResolver
from ..utils.langflow_compatibility import LangflowCompatibilityHelper
from ..utils.logging_config import FrameworkLogger, log_performance, LoggingMiddleware
from .connection_builder import ConnectionBuilder

# Use standardized framework logger
logger = FrameworkLogger("WorkflowConverter")


class WorkflowConverter:
    """
    Professional workflow converter that transforms agent specifications into Langflow workflows.

    This service provides:
    - Specification to Langflow JSON conversion
    - Component-to-node mapping with professional naming
    - Relationship-to-edge generation using ConnectionBuilder
    - Variable resolution and templating
    - Performance optimization and metrics collection
    - Healthcare compliance validation integration
    """

    def __init__(self,
                 variable_resolver: Optional[VariableResolver] = None,
                 compatibility_helper: Optional[LangflowCompatibilityHelper] = None,
                 connection_builder: Optional[ConnectionBuilder] = None):
        """
        Initialize the workflow converter.

        Args:
            variable_resolver: Service for resolving template variables
            compatibility_helper: Helper for Langflow format compatibility
            connection_builder: Service for building component connections
        """
        self.variable_resolver = variable_resolver or VariableResolver()
        self.compatibility_helper = compatibility_helper or LangflowCompatibilityHelper()
        self.connection_builder = connection_builder or ConnectionBuilder()

    async def convert_to_workflow(self,
                                specification: Dict[str, Any],
                                component_mappings: Dict[str, Any],
                                context: ProcessingContext) -> WorkflowConversionResult:
        """
        Convert an agent specification to a Langflow workflow.

        Args:
            specification: Validated agent specification
            component_mappings: Discovered component mappings from ComponentDiscoveryService
            context: Processing context with metadata and configuration

        Returns:
            WorkflowConversionResult with success status and workflow data
        """
        conversion_start = time.time()

        try:
            logger.info("Starting workflow conversion process")

            # Extract specification metadata
            workflow_metadata = self._extract_workflow_metadata(specification)

            # Initialize Langflow workflow structure
            workflow = self._initialize_workflow_structure(workflow_metadata)

            # Phase 1: Convert components to nodes
            logger.debug("Phase 1: Converting components to workflow nodes")
            nodes, node_conversion_errors = await self._convert_components_to_nodes(
                specification, component_mappings, context
            )

            if not nodes:
                return WorkflowConversionResult.create_error(
                    "No valid nodes could be created from specification components",
                    conversion_errors=node_conversion_errors
                )

            workflow["data"]["nodes"] = nodes

            # Phase 2: Generate connections between nodes
            logger.debug("Phase 2: Generating workflow connections")
            edges, edge_generation_errors = await self._generate_workflow_connections(
                specification, nodes, component_mappings, context
            )

            workflow["data"]["edges"] = edges

            # Phase 3: Apply Langflow compatibility optimizations
            logger.debug("Phase 3: Applying Langflow compatibility optimizations")
            workflow = self.compatibility_helper.optimize_workflow(workflow)

            # Phase 4: Calculate conversion metrics
            conversion_time = time.time() - conversion_start
            metrics = self._calculate_conversion_metrics(
                specification, workflow, conversion_time, context
            )

            # Validate final workflow structure
            validation_errors = self.compatibility_helper.validate_workflow_structure(workflow)

            # Determine success status
            all_errors = node_conversion_errors + edge_generation_errors + validation_errors
            success = len(all_errors) == 0

            logger.info(f"Workflow conversion completed in {conversion_time:.3f}s - Success: {success}")

            return WorkflowConversionResult(
                success=success,
                workflow=workflow,
                conversion_time_seconds=conversion_time,
                node_count=len(nodes),
                edge_count=len(edges),
                conversion_errors=all_errors,
                performance_metrics=metrics,
                langflow_compatibility_score=self.compatibility_helper.calculate_compatibility_score(workflow)
            )

        except Exception as e:
            conversion_time = time.time() - conversion_start
            error_message = f"Workflow conversion failed: {str(e)}"
            logger.error(error_message, exc_info=True)

            return WorkflowConversionResult.create_error(
                error_message,
                conversion_time=conversion_time,
                conversion_errors=[error_message]
            )

    def _extract_workflow_metadata(self, specification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract workflow metadata from specification.

        Args:
            specification: Agent specification dictionary

        Returns:
            Dictionary containing workflow metadata
        """
        return {
            "name": specification.get("name", "Untitled Workflow"),
            "description": specification.get("description", "Generated from agent specification"),
            "version": specification.get("version", "1.0.0"),
            "domain": specification.get("domain", "general"),
            "agent_goal": specification.get("agentGoal", ""),
            "kind": specification.get("kind", "Single Agent"),
            "specification_id": specification.get("id", "")
        }

    def _initialize_workflow_structure(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize the base Langflow workflow structure.

        Args:
            metadata: Workflow metadata dictionary

        Returns:
            Base workflow structure with Langflow-compatible format
        """
        workflow_id = f"workflow_{metadata['name'].lower().replace(' ', '_')}_{int(time.time())}"

        return {
            "description": metadata["description"],
            "name": metadata["name"],
            "id": workflow_id,
            "data": {
                "edges": [],
                "nodes": [],
                "viewport": {"x": 0, "y": 0, "zoom": 1}
            },
            "endpoint_name": None,
            "is_component": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "folder_id": None,
            "flows": [],
            "last_tested_version": None,
            "status": None,
            "tags": ["genesis", "specification_framework", metadata.get("domain", "general")],
            "metadata": {
                "converted_by": "SpecificationFramework.WorkflowConverter",
                "conversion_timestamp": datetime.now(timezone.utc).isoformat(),
                "genesis_specification_version": metadata.get("version", "1.0.0"),
                "agent_goal": metadata.get("agent_goal", ""),
                "specification_kind": metadata.get("kind", "Single Agent"),
                "specification_id": metadata.get("specification_id", "")
            }
        }

    async def _convert_components_to_nodes(self,
                                         specification: Dict[str, Any],
                                         component_mappings: Dict[str, Any],
                                         context: ProcessingContext) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Convert specification components to Langflow workflow nodes.

        Args:
            specification: Agent specification
            component_mappings: Component mapping information
            context: Processing context

        Returns:
            Tuple of (nodes list, conversion errors list)
        """
        components = specification.get("components", {})
        nodes = []
        conversion_errors = []

        # Handle both dict and list component formats
        if isinstance(components, dict):
            component_items = components.items()
        elif isinstance(components, list):
            component_items = [(comp.get("id", f"comp_{i}"), comp) for i, comp in enumerate(components)]
        else:
            return [], ["Invalid components format - must be dict or list"]

        # Position tracking for visual layout
        node_position_x = 100
        node_position_y = 100
        nodes_per_row = 4
        current_row_count = 0

        for component_id, component_definition in component_items:
            try:
                # Get component mapping
                component_type = component_definition.get("type", "")
                mapping_info = component_mappings.get(component_id) or component_mappings.get(component_type)

                if not mapping_info:
                    conversion_errors.append(f"No mapping found for component: {component_id} ({component_type})")
                    continue

                # Create workflow node
                node = await self._create_workflow_node(
                    component_id,
                    component_definition,
                    mapping_info,
                    node_position_x,
                    node_position_y,
                    context
                )

                if node:
                    nodes.append(node)

                    # Update position for next node
                    current_row_count += 1
                    if current_row_count >= nodes_per_row:
                        node_position_x = 100
                        node_position_y += 250
                        current_row_count = 0
                    else:
                        node_position_x += 300

                else:
                    conversion_errors.append(f"Failed to create node for component: {component_id}")

            except Exception as e:
                error_message = f"Error converting component {component_id}: {str(e)}"
                logger.warning(error_message)
                conversion_errors.append(error_message)
                continue

        logger.info(f"Converted {len(nodes)} components to nodes with {len(conversion_errors)} errors")
        return nodes, conversion_errors

    async def _create_workflow_node(self,
                                  component_id: str,
                                  component_definition: Dict[str, Any],
                                  mapping_info: Dict[str, Any],
                                  position_x: int,
                                  position_y: int,
                                  context: ProcessingContext) -> Optional[Dict[str, Any]]:
        """
        Create a Langflow workflow node from a component definition.

        Args:
            component_id: Unique component identifier
            component_definition: Component configuration
            mapping_info: Component mapping information
            position_x, position_y: Node position coordinates
            context: Processing context

        Returns:
            Langflow node dictionary or None if creation fails
        """
        try:
            component_type = component_definition.get("type", "")
            langflow_component = mapping_info.get("langflow_component", "CustomComponent")

            # Resolve variables in component configuration
            resolved_config = self.variable_resolver.resolve_component_variables(
                component_definition.get("config", {}),
                context.variables
            )

            # Create node template with resolved configuration
            template = self._create_node_template(
                component_definition,
                resolved_config,
                mapping_info,
                context
            )

            # Build the Langflow node structure
            node = {
                "id": component_id,
                "type": "genericNode",
                "position": {"x": position_x, "y": position_y},
                "data": {
                    "type": langflow_component,
                    "display_name": component_definition.get("name", component_id),
                    "description": component_definition.get("description", ""),
                    "template": template,
                    "node": {
                        "base_classes": mapping_info.get("base_classes", ["Component"]),
                        "display_name": component_definition.get("name", component_id),
                        "documentation": component_definition.get("description", ""),
                        "template": template,
                        "custom_fields": {},
                        "output_types": mapping_info.get("output_types", ["Message", "Data"]),
                        "input_types": mapping_info.get("input_types", ["Message", "Data"])
                    },
                    "metadata": {
                        "genesis_component_id": component_id,
                        "genesis_component_type": component_type,
                        "component_kind": component_definition.get("kind", "Component"),
                        "as_tools": component_definition.get("asTools", False),
                        "conversion_timestamp": datetime.now(timezone.utc).isoformat()
                    }
                },
                "selected": False,
                "width": 384,
                "height": self._calculate_node_height(template),
                "z_index": 1
            }

            return node

        except Exception as e:
            logger.error(f"Failed to create node for component {component_id}: {e}")
            return None

    def _create_node_template(self,
                            component_definition: Dict[str, Any],
                            resolved_config: Dict[str, Any],
                            mapping_info: Dict[str, Any],
                            context: ProcessingContext) -> Dict[str, Any]:
        """
        Create Langflow node template from component configuration.

        Args:
            component_definition: Original component definition
            resolved_config: Configuration with resolved variables
            mapping_info: Component mapping information
            context: Processing context

        Returns:
            Langflow-compatible node template
        """
        template = {}

        # Basic template metadata
        langflow_component = mapping_info.get("langflow_component", "CustomComponent")
        template["_type"] = {
            "type": "str",
            "value": langflow_component,
            "show": False,
            "advanced": False
        }

        # Add default input types for frontend compatibility
        default_input_types = mapping_info.get("input_types", ["Message", "Data"])

        # Process configuration fields
        for field_name, field_value in resolved_config.items():
            template_field = self._create_template_field(
                field_name,
                field_value,
                default_input_types,
                context
            )
            template[field_name] = template_field

        # Add component-specific template fields based on mapping
        component_specific_template = mapping_info.get("template_fields", {})
        for field_name, field_config in component_specific_template.items():
            if field_name not in template:  # Don't override existing config
                field_config = field_config.copy()
                field_config["input_types"] = default_input_types
                template[field_name] = field_config

        # Add healthcare compliance fields if enabled
        if context.healthcare_compliance:
            template.update(self._add_healthcare_compliance_fields(default_input_types))

        return template

    def _create_template_field(self,
                             field_name: str,
                             field_value: Any,
                             input_types: List[str],
                             context: ProcessingContext) -> Dict[str, Any]:
        """
        Create a Langflow template field from a configuration value.

        Args:
            field_name: Configuration field name
            field_value: Configuration field value
            input_types: Valid input types for the field
            context: Processing context

        Returns:
            Langflow template field dictionary
        """
        field_type = self._infer_langflow_field_type(field_value)
        is_multiline = isinstance(field_value, str) and len(str(field_value)) > 100
        is_password = field_name.lower() in ["password", "api_key", "secret", "token"]

        return {
            "type": field_type,
            "value": field_value,
            "show": True,
            "multiline": is_multiline,
            "input_types": input_types,
            "required": False,
            "placeholder": f"Enter {field_name.replace('_', ' ')}",
            "password": is_password,
            "name": field_name,
            "advanced": field_name.startswith("_") or field_name in ["debug", "verbose"],
            "list": isinstance(field_value, list),
            "field_type": field_type
        }

    def _infer_langflow_field_type(self, value: Any) -> str:
        """
        Infer Langflow field type from Python value.

        Args:
            value: Python value to analyze

        Returns:
            Langflow field type string
        """
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

    def _calculate_node_height(self, template: Dict[str, Any]) -> int:
        """
        Calculate appropriate node height based on template complexity.

        Args:
            template: Node template dictionary

        Returns:
            Calculated height in pixels
        """
        base_height = 200
        field_height = 40
        multiline_bonus = 60

        visible_fields = sum(1 for field in template.values()
                           if isinstance(field, dict) and field.get("show", True))
        multiline_fields = sum(1 for field in template.values()
                             if isinstance(field, dict) and field.get("multiline", False))

        calculated_height = base_height + (visible_fields * field_height) + (multiline_fields * multiline_bonus)

        # Ensure reasonable bounds
        return max(200, min(800, calculated_height))

    async def _generate_workflow_connections(self,
                                           specification: Dict[str, Any],
                                           nodes: List[Dict[str, Any]],
                                           component_mappings: Dict[str, Any],
                                           context: ProcessingContext) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Generate workflow connections (edges) from component relationships.

        Args:
            specification: Agent specification
            nodes: Generated workflow nodes
            component_mappings: Component mappings
            context: Processing context

        Returns:
            Tuple of (edges list, generation errors list)
        """
        try:
            # Extract components from specification for ConnectionBuilder
            components = specification.get("components", {})

            # Use ConnectionBuilder to generate professional connections
            edges = await self.connection_builder.build_connections(
                components,
                component_mappings,
                context
            )

            return edges, []  # No errors for successful generation

        except Exception as e:
            error_message = f"Failed to generate workflow connections: {str(e)}"
            logger.error(error_message, exc_info=True)
            return [], [error_message]

    def _add_healthcare_compliance_fields(self, input_types: List[str]) -> Dict[str, Any]:
        """
        Add healthcare compliance fields to template.

        Args:
            input_types: Valid input types

        Returns:
            Dictionary of healthcare compliance template fields
        """
        return {
            "hipaa_compliance": {
                "type": "bool",
                "value": True,
                "show": True,
                "input_types": input_types,
                "required": False,
                "name": "hipaa_compliance",
                "advanced": True,
                "description": "Enable HIPAA compliance validation"
            },
            "phi_handling": {
                "type": "str",
                "value": "secure",
                "show": True,
                "input_types": input_types,
                "required": False,
                "name": "phi_handling",
                "advanced": True,
                "options": ["secure", "audit", "encrypt"],
                "description": "PHI data handling mode"
            }
        }

    def _calculate_conversion_metrics(self,
                                    specification: Dict[str, Any],
                                    workflow: Dict[str, Any],
                                    conversion_time: float,
                                    context: ProcessingContext) -> Dict[str, Any]:
        """
        Calculate comprehensive conversion performance metrics.

        Args:
            specification: Original specification
            workflow: Generated workflow
            conversion_time: Total conversion time in seconds
            context: Processing context

        Returns:
            Dictionary of performance metrics
        """
        components = specification.get("components", {})
        nodes = workflow.get("data", {}).get("nodes", [])
        edges = workflow.get("data", {}).get("edges", [])

        # Component analysis
        if isinstance(components, dict):
            component_count = len(components)
            provides_count = sum(1 for comp in components.values()
                               if comp.get("provides"))
        else:
            component_count = len(components)
            provides_count = sum(1 for comp in components
                               if comp.get("provides"))

        # Performance calculations
        components_per_second = component_count / max(conversion_time, 0.001)
        estimated_memory_mb = self._estimate_workflow_memory_usage(workflow)

        # Automation metrics
        explicit_connections = provides_count
        implicit_connections = max(0, len(edges) - explicit_connections)
        automation_percentage = (implicit_connections / len(edges) * 100) if len(edges) > 0 else 0

        return {
            "conversion_time_seconds": round(conversion_time, 6),
            "components_processed": component_count,
            "nodes_created": len(nodes),
            "edges_created": len(edges),
            "components_per_second": round(components_per_second, 2),
            "estimated_memory_mb": round(estimated_memory_mb, 1),
            "automation_percentage": round(automation_percentage, 1),
            "explicit_connections": explicit_connections,
            "implicit_connections": implicit_connections,
            "performance_target_met": conversion_time < 2.0,
            "complexity_score": len(nodes) + (len(edges) * 0.5),
            "variables_resolved": len(context.variables),
            "healthcare_compliance_enabled": context.healthcare_compliance
        }

    def _estimate_workflow_memory_usage(self, workflow: Dict[str, Any]) -> float:
        """
        Estimate memory usage for the generated workflow.

        Args:
            workflow: Generated Langflow workflow

        Returns:
            Estimated memory usage in MB
        """
        base_memory = 10.0  # Base workflow overhead

        nodes = workflow.get("data", {}).get("nodes", [])
        edges = workflow.get("data", {}).get("edges", [])

        # Memory per component type
        node_memory = len(nodes) * 2.0  # 2MB per node base
        edge_memory = len(edges) * 0.1  # 0.1MB per edge

        # Additional memory for complex components
        complex_components = 0
        for node in nodes:
            node_data = node.get("data", {})
            template = node_data.get("template", {})

            # Check for memory-intensive components
            if any(field.get("multiline", False) for field in template.values()
                   if isinstance(field, dict)):
                complex_components += 1

            # Model components use more memory
            component_type = node_data.get("type", "")
            if any(term in component_type.lower() for term in ["model", "embedding", "llm"]):
                complex_components += 2

        complex_memory = complex_components * 5.0  # 5MB per complex component

        return base_memory + node_memory + edge_memory + complex_memory

    async def validate_workflow_structure(self, workflow: Dict[str, Any]) -> List[str]:
        """
        Validate the generated workflow structure for Langflow compatibility.

        Args:
            workflow: Generated workflow to validate

        Returns:
            List of validation error messages
        """
        return self.compatibility_helper.validate_workflow_structure(workflow)