"""
Professional Workflow Validator for the Dynamic Agent Specification Framework.

This module provides comprehensive validation of generated Langflow workflows including
structure validation, node validation, edge validation, and performance optimization validation.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

from ..models.validation_models import ValidationResult, ValidationError, ValidationWarning
from ..models.processing_context import ProcessingContext

logger = logging.getLogger(__name__)


class WorkflowValidator:
    """
    Professional validator for generated Langflow workflows.

    This validator provides:
    - Langflow structure validation
    - Node and edge validation
    - Component compatibility validation
    - Performance and scalability validation
    - Healthcare compliance validation for workflows
    - Frontend compatibility validation
    """

    def __init__(self):
        """Initialize the workflow validator."""
        self.required_workflow_fields = self._get_required_workflow_fields()
        self.required_node_fields = self._get_required_node_fields()
        self.required_edge_fields = self._get_required_edge_fields()
        self.langflow_component_types = self._get_langflow_component_types()

    async def validate_workflow(self,
                              workflow: Dict[str, Any],
                              context: ProcessingContext) -> ValidationResult:
        """
        Perform comprehensive validation of a generated Langflow workflow.

        Args:
            workflow: Generated Langflow workflow dictionary
            context: Processing context with validation settings

        Returns:
            ValidationResult with validation status, errors, and warnings
        """
        validation_start = datetime.utcnow()
        errors = []
        warnings = []

        try:
            logger.debug("Starting comprehensive workflow validation")

            # Phase 1: Basic workflow structure validation
            structure_errors, structure_warnings = self._validate_workflow_structure(workflow)
            errors.extend(structure_errors)
            warnings.extend(structure_warnings)

            if structure_errors:
                # Don't continue if basic structure is invalid
                return ValidationResult.create_invalid(
                    errors, warnings, healthcare_compliance=context.healthcare_compliance
                )

            # Phase 2: Node validation
            node_errors, node_warnings = await self._validate_workflow_nodes(workflow, context)
            errors.extend(node_errors)
            warnings.extend(node_warnings)

            # Phase 3: Edge validation
            edge_errors, edge_warnings = await self._validate_workflow_edges(workflow, context)
            errors.extend(edge_errors)
            warnings.extend(edge_warnings)

            # Phase 4: Langflow compatibility validation
            compatibility_errors, compatibility_warnings = self._validate_langflow_compatibility(workflow)
            errors.extend(compatibility_errors)
            warnings.extend(compatibility_warnings)

            # Phase 5: Performance validation
            performance_warnings = self._validate_workflow_performance(workflow, context)
            warnings.extend(performance_warnings)

            # Phase 6: Healthcare compliance validation (if enabled)
            healthcare_compliant = True
            if context.healthcare_compliance:
                healthcare_errors, healthcare_warnings, healthcare_compliant = self._validate_workflow_healthcare_compliance(
                    workflow, context
                )
                errors.extend(healthcare_errors)
                warnings.extend(healthcare_warnings)

            # Phase 7: Frontend compatibility validation
            frontend_warnings = self._validate_frontend_compatibility(workflow)
            warnings.extend(frontend_warnings)

            validation_time = (datetime.utcnow() - validation_start).total_seconds()
            is_valid = len(errors) == 0

            logger.info(f"Workflow validation completed in {validation_time:.3f}s - Valid: {is_valid}")

            return ValidationResult(
                is_valid=is_valid,
                validation_errors=errors,
                warnings=warnings,
                healthcare_compliant=healthcare_compliant if context.healthcare_compliance else None,
                validation_time_seconds=validation_time,
                components_validated=len(workflow.get("data", {}).get("nodes", [])),
                relationships_validated=len(workflow.get("data", {}).get("edges", []))
            )

        except Exception as e:
            error_message = f"Workflow validation process failed: {str(e)}"
            logger.error(error_message, exc_info=True)

            return ValidationResult.create_invalid(
                [ValidationError(
                    error_type="workflow_validation_failure",
                    message=error_message,
                    field_path="workflow",
                    severity="critical"
                )],
                warnings,
                healthcare_compliance=context.healthcare_compliance
            )

    def _validate_workflow_structure(self, workflow: Dict[str, Any]) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate the basic structure of the Langflow workflow.

        Args:
            workflow: Workflow dictionary to validate

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        try:
            # Check if workflow is a dictionary
            if not isinstance(workflow, dict):
                errors.append(ValidationError(
                    error_type="invalid_workflow_format",
                    message="Workflow must be a dictionary",
                    field_path="workflow",
                    severity="critical"
                ))
                return errors, warnings

            # Validate required top-level fields
            for field in self.required_workflow_fields:
                if field not in workflow:
                    errors.append(ValidationError(
                        error_type="missing_workflow_field",
                        message=f"Required workflow field '{field}' is missing",
                        field_path=field,
                        severity="critical"
                    ))

            # Validate data structure
            data = workflow.get("data", {})
            if not isinstance(data, dict):
                errors.append(ValidationError(
                    error_type="invalid_data_structure",
                    message="Workflow 'data' field must be a dictionary",
                    field_path="data",
                    severity="critical"
                ))
                return errors, warnings

            # Validate nodes and edges arrays
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])

            if not isinstance(nodes, list):
                errors.append(ValidationError(
                    error_type="invalid_nodes_format",
                    message="Workflow nodes must be a list",
                    field_path="data.nodes",
                    severity="critical"
                ))

            if not isinstance(edges, list):
                errors.append(ValidationError(
                    error_type="invalid_edges_format",
                    message="Workflow edges must be a list",
                    field_path="data.edges",
                    severity="critical"
                ))

            # Check for empty workflow
            if len(nodes) == 0:
                errors.append(ValidationError(
                    error_type="empty_workflow",
                    message="Workflow must contain at least one node",
                    field_path="data.nodes",
                    severity="error"
                ))

            # Validate viewport
            viewport = data.get("viewport", {})
            if viewport and not isinstance(viewport, dict):
                warnings.append(ValidationWarning(
                    warning_type="invalid_viewport",
                    message="Viewport should be a dictionary with x, y, zoom fields",
                    field_path="data.viewport",
                    severity="low"
                ))

        except Exception as e:
            errors.append(ValidationError(
                error_type="structure_validation_error",
                message=f"Workflow structure validation failed: {str(e)}",
                field_path="workflow",
                severity="critical"
            ))

        return errors, warnings

    async def _validate_workflow_nodes(self,
                                     workflow: Dict[str, Any],
                                     context: ProcessingContext) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate all nodes in the workflow.

        Args:
            workflow: Workflow dictionary
            context: Processing context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        nodes = workflow.get("data", {}).get("nodes", [])
        node_ids = set()

        for i, node in enumerate(nodes):
            node_path = f"data.nodes[{i}]"

            # Validate individual node
            node_errors, node_warnings = self._validate_single_node(node, node_path, context)
            errors.extend(node_errors)
            warnings.extend(node_warnings)

            # Check for duplicate node IDs
            node_id = node.get("id", f"node_{i}")
            if node_id in node_ids:
                errors.append(ValidationError(
                    error_type="duplicate_node_id",
                    message=f"Duplicate node ID: {node_id}",
                    field_path=f"{node_path}.id",
                    severity="error"
                ))
            else:
                node_ids.add(node_id)

        return errors, warnings

    def _validate_single_node(self,
                            node: Dict[str, Any],
                            node_path: str,
                            context: ProcessingContext) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate a single workflow node.

        Args:
            node: Node dictionary to validate
            node_path: JSON path to the node
            context: Processing context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        # Validate node is a dictionary
        if not isinstance(node, dict):
            errors.append(ValidationError(
                error_type="invalid_node_format",
                message="Node must be a dictionary",
                field_path=node_path,
                severity="error"
            ))
            return errors, warnings

        # Validate required node fields
        for field in self.required_node_fields:
            if field not in node:
                errors.append(ValidationError(
                    error_type="missing_node_field",
                    message=f"Node missing required field: {field}",
                    field_path=f"{node_path}.{field}",
                    severity="error"
                ))

        # Validate node ID format
        node_id = node.get("id", "")
        if not node_id or not isinstance(node_id, str):
            errors.append(ValidationError(
                error_type="invalid_node_id",
                message="Node ID must be a non-empty string",
                field_path=f"{node_path}.id",
                severity="error"
            ))

        # Validate position
        position = node.get("position", {})
        if not isinstance(position, dict) or "x" not in position or "y" not in position:
            errors.append(ValidationError(
                error_type="invalid_node_position",
                message="Node position must be a dictionary with x and y coordinates",
                field_path=f"{node_path}.position",
                severity="error"
            ))

        # Validate node data
        data = node.get("data", {})
        if not isinstance(data, dict):
            errors.append(ValidationError(
                error_type="invalid_node_data",
                message="Node data must be a dictionary",
                field_path=f"{node_path}.data",
                severity="error"
            ))
            return errors, warnings

        # Validate component type
        component_type = data.get("type", "")
        if component_type and component_type not in self.langflow_component_types:
            warnings.append(ValidationWarning(
                warning_type="unknown_component_type",
                message=f"Unknown Langflow component type: {component_type}",
                field_path=f"{node_path}.data.type",
                severity="medium",
                suggestion="Verify component type is supported in Langflow"
            ))

        # Validate node template
        template = data.get("template", {})
        if template:
            template_errors, template_warnings = self._validate_node_template(
                template, f"{node_path}.data.template", context
            )
            errors.extend(template_errors)
            warnings.extend(template_warnings)

        # Validate node metadata
        metadata = data.get("metadata", {})
        if metadata and not isinstance(metadata, dict):
            warnings.append(ValidationWarning(
                warning_type="invalid_metadata_format",
                message="Node metadata should be a dictionary",
                field_path=f"{node_path}.data.metadata",
                severity="low"
            ))

        return errors, warnings

    def _validate_node_template(self,
                              template: Dict[str, Any],
                              template_path: str,
                              context: ProcessingContext) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate a node template structure.

        Args:
            template: Node template dictionary
            template_path: JSON path to the template
            context: Processing context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        if not isinstance(template, dict):
            errors.append(ValidationError(
                error_type="invalid_template_format",
                message="Node template must be a dictionary",
                field_path=template_path,
                severity="error"
            ))
            return errors, warnings

        # Validate template fields
        for field_name, field_config in template.items():
            field_path = f"{template_path}.{field_name}"

            if not isinstance(field_config, dict):
                warnings.append(ValidationWarning(
                    warning_type="invalid_template_field",
                    message=f"Template field '{field_name}' should be a dictionary",
                    field_path=field_path,
                    severity="medium"
                ))
                continue

            # Check for required template field properties
            if "type" not in field_config:
                warnings.append(ValidationWarning(
                    warning_type="missing_field_type",
                    message=f"Template field '{field_name}' missing type specification",
                    field_path=f"{field_path}.type",
                    severity="low"
                ))

            # Validate frontend compatibility fields
            frontend_fields = ["show", "input_types", "name"]
            missing_frontend_fields = [f for f in frontend_fields if f not in field_config]

            if missing_frontend_fields:
                warnings.append(ValidationWarning(
                    warning_type="missing_frontend_fields",
                    message=f"Template field '{field_name}' missing frontend compatibility fields: {missing_frontend_fields}",
                    field_path=field_path,
                    severity="low",
                    suggestion="Add show, input_types, and name fields for frontend compatibility"
                ))

        return errors, warnings

    async def _validate_workflow_edges(self,
                                     workflow: Dict[str, Any],
                                     context: ProcessingContext) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate all edges in the workflow.

        Args:
            workflow: Workflow dictionary
            context: Processing context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        nodes = workflow.get("data", {}).get("nodes", [])
        edges = workflow.get("data", {}).get("edges", [])

        # Build node ID set for validation
        node_ids = {node.get("id") for node in nodes if node.get("id")}

        edge_ids = set()
        for i, edge in enumerate(edges):
            edge_path = f"data.edges[{i}]"

            # Validate individual edge
            edge_errors, edge_warnings = self._validate_single_edge(edge, edge_path, node_ids, context)
            errors.extend(edge_errors)
            warnings.extend(edge_warnings)

            # Check for duplicate edge IDs
            edge_id = edge.get("id", f"edge_{i}")
            if edge_id in edge_ids:
                errors.append(ValidationError(
                    error_type="duplicate_edge_id",
                    message=f"Duplicate edge ID: {edge_id}",
                    field_path=f"{edge_path}.id",
                    severity="error"
                ))
            else:
                edge_ids.add(edge_id)

        return errors, warnings

    def _validate_single_edge(self,
                            edge: Dict[str, Any],
                            edge_path: str,
                            valid_node_ids: Set[str],
                            context: ProcessingContext) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate a single workflow edge.

        Args:
            edge: Edge dictionary to validate
            edge_path: JSON path to the edge
            valid_node_ids: Set of valid node IDs
            context: Processing context

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        # Validate edge is a dictionary
        if not isinstance(edge, dict):
            errors.append(ValidationError(
                error_type="invalid_edge_format",
                message="Edge must be a dictionary",
                field_path=edge_path,
                severity="error"
            ))
            return errors, warnings

        # Validate required edge fields
        for field in self.required_edge_fields:
            if field not in edge:
                errors.append(ValidationError(
                    error_type="missing_edge_field",
                    message=f"Edge missing required field: {field}",
                    field_path=f"{edge_path}.{field}",
                    severity="error"
                ))

        # Validate source and target references
        source_id = edge.get("source")
        target_id = edge.get("target")

        if source_id and source_id not in valid_node_ids:
            errors.append(ValidationError(
                error_type="invalid_edge_source",
                message=f"Edge references non-existent source node: {source_id}",
                field_path=f"{edge_path}.source",
                severity="error"
            ))

        if target_id and target_id not in valid_node_ids:
            errors.append(ValidationError(
                error_type="invalid_edge_target",
                message=f"Edge references non-existent target node: {target_id}",
                field_path=f"{edge_path}.target",
                severity="error"
            ))

        # Validate edge handles
        source_handle = edge.get("sourceHandle")
        target_handle = edge.get("targetHandle")

        if source_handle and not isinstance(source_handle, str):
            warnings.append(ValidationWarning(
                warning_type="invalid_handle_format",
                message="Source handle should be a string",
                field_path=f"{edge_path}.sourceHandle",
                severity="low"
            ))

        if target_handle and not isinstance(target_handle, str):
            warnings.append(ValidationWarning(
                warning_type="invalid_handle_format",
                message="Target handle should be a string",
                field_path=f"{edge_path}.targetHandle",
                severity="low"
            ))

        # Validate edge data for Langflow compatibility
        edge_data = edge.get("data", {})
        if edge_data and not isinstance(edge_data, dict):
            warnings.append(ValidationWarning(
                warning_type="invalid_edge_data",
                message="Edge data should be a dictionary",
                field_path=f"{edge_path}.data",
                severity="medium"
            ))

        # Check for Langflow-specific handle encoding
        if target_handle and "œ" in target_handle:
            try:
                decoded_handle = json.loads(target_handle.replace("œ", '"'))
                if not isinstance(decoded_handle, dict):
                    warnings.append(ValidationWarning(
                        warning_type="invalid_encoded_handle",
                        message="Encoded target handle should decode to a dictionary",
                        field_path=f"{edge_path}.targetHandle",
                        severity="medium"
                    ))
            except json.JSONDecodeError:
                warnings.append(ValidationWarning(
                    warning_type="malformed_encoded_handle",
                    message="Target handle contains invalid encoded JSON",
                    field_path=f"{edge_path}.targetHandle",
                    severity="medium"
                ))

        return errors, warnings

    def _validate_langflow_compatibility(self, workflow: Dict[str, Any]) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate Langflow-specific compatibility requirements.

        Args:
            workflow: Workflow dictionary

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        # Check for required Langflow metadata
        metadata = workflow.get("metadata", {})
        langflow_metadata_fields = ["converted_by", "conversion_timestamp"]

        for field in langflow_metadata_fields:
            if field not in metadata:
                warnings.append(ValidationWarning(
                    warning_type="missing_langflow_metadata",
                    message=f"Missing Langflow metadata field: {field}",
                    field_path=f"metadata.{field}",
                    severity="low",
                    suggestion="Add metadata for better Langflow integration"
                ))

        # Validate workflow format version compatibility
        if "format_version" in workflow:
            format_version = workflow["format_version"]
            if not isinstance(format_version, str) or not format_version.startswith("1."):
                warnings.append(ValidationWarning(
                    warning_type="unsupported_format_version",
                    message=f"Format version {format_version} may not be supported",
                    field_path="format_version",
                    severity="medium",
                    suggestion="Use format version 1.x for best compatibility"
                ))

        # Check node type compatibility
        nodes = workflow.get("data", {}).get("nodes", [])
        unsupported_types = []

        for node in nodes:
            node_type = node.get("data", {}).get("type", "")
            if node_type and node_type not in self.langflow_component_types:
                if node_type not in unsupported_types:
                    unsupported_types.append(node_type)

        if unsupported_types:
            warnings.append(ValidationWarning(
                warning_type="unsupported_component_types",
                message=f"Workflow contains unsupported component types: {unsupported_types}",
                field_path="data.nodes",
                severity="medium",
                suggestion="Verify these components are available in target Langflow version"
            ))

        return errors, warnings

    def _validate_workflow_performance(self,
                                     workflow: Dict[str, Any],
                                     context: ProcessingContext) -> List[ValidationWarning]:
        """
        Validate workflow performance characteristics.

        Args:
            workflow: Workflow dictionary
            context: Processing context

        Returns:
            List of performance warnings
        """
        warnings = []

        nodes = workflow.get("data", {}).get("nodes", [])
        edges = workflow.get("data", {}).get("edges", [])

        node_count = len(nodes)
        edge_count = len(edges)

        # Performance thresholds
        if node_count > 50:
            warnings.append(ValidationWarning(
                warning_type="high_node_count",
                message=f"High node count ({node_count}) may impact Langflow UI performance",
                field_path="data.nodes",
                severity="medium",
                suggestion="Consider breaking into smaller workflows"
            ))

        if edge_count > 100:
            warnings.append(ValidationWarning(
                warning_type="high_edge_count",
                message=f"High edge count ({edge_count}) may impact workflow performance",
                field_path="data.edges",
                severity="medium",
                suggestion="Optimize component connections"
            ))

        # Check for complex templates that might slow rendering
        complex_templates = 0
        for node in nodes:
            template = node.get("data", {}).get("template", {})
            if len(template) > 20:  # Many template fields
                complex_templates += 1

        if complex_templates > 5:
            warnings.append(ValidationWarning(
                warning_type="complex_templates",
                message=f"Multiple nodes ({complex_templates}) have complex templates",
                field_path="data.nodes",
                severity="low",
                suggestion="Consider simplifying node templates for better performance"
            ))

        return warnings

    def _validate_workflow_healthcare_compliance(self,
                                               workflow: Dict[str, Any],
                                               context: ProcessingContext) -> Tuple[List[ValidationError], List[ValidationWarning], bool]:
        """
        Validate healthcare compliance in the generated workflow.

        Args:
            workflow: Workflow dictionary
            context: Processing context

        Returns:
            Tuple of (errors, warnings, is_compliant)
        """
        errors = []
        warnings = []
        is_compliant = True

        nodes = workflow.get("data", {}).get("nodes", [])

        # Check for healthcare-related components
        healthcare_nodes = []
        for node in nodes:
            node_data = node.get("data", {})
            component_type = node_data.get("type", "")
            metadata = node_data.get("metadata", {})
            genesis_type = metadata.get("genesis_component_type", "")

            # Identify healthcare components
            if any(term in component_type.lower() for term in ["ehr", "medical", "patient", "phi"]) or \
               any(term in genesis_type.lower() for term in ["ehr", "eligibility", "claims", "medical"]):
                healthcare_nodes.append(node)

        if not healthcare_nodes:
            return errors, warnings, True  # No healthcare components

        # Validate healthcare nodes have proper configuration
        for node in healthcare_nodes:
            node_id = node.get("id", "unknown")
            template = node.get("data", {}).get("template", {})

            # Check for HIPAA compliance fields
            if "hipaa_compliance" not in template:
                warnings.append(ValidationWarning(
                    warning_type="missing_hipaa_compliance",
                    message=f"Healthcare node {node_id} lacks HIPAA compliance configuration",
                    field_path=f"data.nodes[{node_id}].data.template",
                    severity="high",
                    suggestion="Add hipaa_compliance field to template"
                ))
                is_compliant = False

            # Check for PHI handling configuration
            if "phi_handling" not in template:
                warnings.append(ValidationWarning(
                    warning_type="missing_phi_handling",
                    message=f"Healthcare node {node_id} lacks PHI handling configuration",
                    field_path=f"data.nodes[{node_id}].data.template",
                    severity="high",
                    suggestion="Add phi_handling field to template"
                ))

        return errors, warnings, is_compliant

    def _validate_frontend_compatibility(self, workflow: Dict[str, Any]) -> List[ValidationWarning]:
        """
        Validate frontend compatibility for Langflow UI.

        Args:
            workflow: Workflow dictionary

        Returns:
            List of frontend compatibility warnings
        """
        warnings = []

        nodes = workflow.get("data", {}).get("nodes", [])

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})
            template = node_data.get("template", {})

            # Check for missing display fields
            if "display_name" not in node_data:
                warnings.append(ValidationWarning(
                    warning_type="missing_display_name",
                    message=f"Node {node_id} missing display_name for frontend",
                    field_path=f"data.nodes[{node_id}].data.display_name",
                    severity="low",
                    suggestion="Add display_name for better UI experience"
                ))

            # Check template fields for frontend compatibility
            for field_name, field_config in template.items():
                if isinstance(field_config, dict):
                    if "input_types" not in field_config:
                        warnings.append(ValidationWarning(
                            warning_type="missing_input_types",
                            message=f"Template field {field_name} missing input_types for frontend",
                            field_path=f"data.nodes[{node_id}].data.template.{field_name}",
                            severity="low",
                            suggestion="Add input_types for frontend compatibility"
                        ))

        return warnings

    def _get_required_workflow_fields(self) -> List[str]:
        """Get required fields for Langflow workflows."""
        return ["data", "name", "description"]

    def _get_required_node_fields(self) -> List[str]:
        """Get required fields for Langflow nodes."""
        return ["id", "data", "position", "type"]

    def _get_required_edge_fields(self) -> List[str]:
        """Get required fields for Langflow edges."""
        return ["id", "source", "target"]

    def _get_langflow_component_types(self) -> Set[str]:
        """Get set of known Langflow component types."""
        return {
            # Core Langflow components
            "ChatOpenAI", "PromptTemplate", "ChatInput", "ChatOutput",
            "Tool", "APIRequest", "VectorStoreRetriever", "CustomComponent",

            # CrewAI components
            "CrewAIAgent", "CrewAITask", "CrewAICrew",

            # Data components
            "TextSplitter", "DocumentLoader", "VectorStore",

            # Model components
            "OpenAI", "Anthropic", "HuggingFace", "Ollama",

            # Memory components
            "ConversationBufferMemory", "ConversationSummaryMemory",

            # Custom components from our framework
            "HealthcareConnector", "EHRConnector", "EligibilityConnector",
            "ClaimsConnector", "PharmacyConnector", "MedicalDataStandardizer"
        }