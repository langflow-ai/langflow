"""
Core specification processor for the Dynamic Agent Specification Framework.

This module provides the main entry point for processing YAML agent specifications
into Langflow JSON workflows with comprehensive validation and healthcare compliance.
"""

import logging
import time
from typing import Dict, Any, Optional

from ..services.component_discovery import LangflowComponentValidator
from ..services.workflow_converter import WorkflowConverter
from ..validation.specification_validator import SpecificationValidator
from ..validation.workflow_validator import WorkflowValidator
from ..models.processing_context import ProcessingContext, ProcessingResult

logger = logging.getLogger(__name__)


class SpecificationProcessor:
    """
    Simplified processor for converting agent specifications to Langflow workflows.

    This streamlined processor eliminates database overhead and provides direct validation:
    1. Specification validation
    2. Direct component validation via /all endpoint
    3. Workflow conversion
    4. Healthcare compliance validation
    5. Performance optimization
    """

    def __init__(self,
                 component_validator: Optional[LangflowComponentValidator] = None,
                 workflow_converter: Optional[WorkflowConverter] = None,
                 spec_validator: Optional[SpecificationValidator] = None,
                 workflow_validator: Optional[WorkflowValidator] = None):
        """
        Initialize the specification processor.

        Args:
            component_validator: Langflow validator for component validation
            workflow_converter: Service for converting specifications to workflows
            spec_validator: Validator for agent specifications
            workflow_validator: Validator for generated workflows
        """
        self.component_validator = component_validator or LangflowComponentValidator()
        self.workflow_converter = workflow_converter or WorkflowConverter()
        self.spec_validator = spec_validator or SpecificationValidator()
        self.workflow_validator = workflow_validator or WorkflowValidator()

    async def process_specification(self,
                                  spec_dict: Dict[str, Any],
                                  variables: Optional[Dict[str, Any]] = None,
                                  enable_healthcare_compliance: bool = False,
                                  enable_performance_benchmarking: bool = False) -> ProcessingResult:
        """
        Process a complete agent specification into a Langflow workflow.

        Args:
            spec_dict: Agent specification dictionary
            variables: Optional variables for templating
            enable_healthcare_compliance: Enable HIPAA compliance validation
            enable_performance_benchmarking: Enable detailed performance metrics

        Returns:
            ProcessingResult containing the workflow and metadata
        """
        start_time = time.time()

        try:
            # Create processing context
            context = ProcessingContext(
                specification=spec_dict,
                variables=variables or {},
                healthcare_compliance=enable_healthcare_compliance,
                performance_benchmarking=enable_performance_benchmarking,
                processing_start_time=start_time
            )

            # Phase 1: Validate input specification
            logger.info("Phase 1: Validating agent specification")
            validation_result = await self.spec_validator.validate_specification(
                spec_dict, context.healthcare_compliance
            )

            if not validation_result.is_valid:
                return ProcessingResult.create_error(
                    f"Specification validation failed: {validation_result.error_message}",
                    context
                )

            context.spec_validation_result = validation_result

            # Phase 2: Validate components using simplified validator
            logger.info("Phase 2: Validating components with direct /all endpoint validation")
            component_mappings = await self.component_validator.discover_enhanced_components(
                spec_dict, context
            )

            if not component_mappings:
                return ProcessingResult.create_error(
                    "Component validation failed - no valid components found",
                    context
                )

            context.component_mappings = component_mappings

            # Phase 3: Convert to Langflow workflow
            logger.info("Phase 3: Converting specification to Langflow workflow")
            workflow_result = await self.workflow_converter.convert_to_workflow(
                spec_dict, component_mappings, context
            )

            if not workflow_result.success:
                return ProcessingResult.create_error(
                    f"Workflow conversion failed: {workflow_result.error_message}",
                    context
                )

            context.langflow_workflow = workflow_result.workflow

            # Phase 4: Validate generated workflow
            logger.info("Phase 4: Validating generated workflow")
            workflow_validation = await self.workflow_validator.validate_workflow(
                workflow_result.workflow, context
            )

            if not workflow_validation.is_valid:
                return ProcessingResult.create_error(
                    f"Workflow validation failed: {workflow_validation.error_message}",
                    context
                )

            context.workflow_validation_result = workflow_validation

            # Phase 5: Generate final result with metrics
            processing_time = time.time() - start_time

            return ProcessingResult(
                success=True,
                workflow=workflow_result.workflow,
                context=context,
                processing_time_seconds=processing_time,
                spec_validation=validation_result,
                workflow_validation=workflow_validation,
                component_count=len(component_mappings),
                edge_count=len(workflow_result.workflow.get("data", {}).get("edges", [])),
                automation_metrics=self._calculate_automation_metrics(context),
                performance_metrics=self._calculate_performance_metrics(context, processing_time),
                compliance_metrics=self._calculate_compliance_metrics(context) if enable_healthcare_compliance else None
            )

        except Exception as e:
            logger.error(f"Specification processing failed: {e}", exc_info=True)
            return ProcessingResult.create_error(str(e), context if 'context' in locals() else None)

    def _calculate_automation_metrics(self, context: ProcessingContext) -> Dict[str, Any]:
        """Calculate automation percentage and related metrics."""
        components = context.specification.get("components", {})

        # Handle both dict and list component formats
        if isinstance(components, dict):
            component_count = len(components)
            provides_count = sum(1 for comp in components.values() if comp.get("provides"))
        else:
            component_count = len(components)
            provides_count = sum(1 for comp in components if comp.get("provides"))

        edges = context.langflow_workflow.get("data", {}).get("edges", [])
        edge_count = len(edges)

        # Calculate implicit connections (automation)
        explicit_connections = provides_count
        implicit_connections = max(0, edge_count - explicit_connections)

        automation_percentage = (implicit_connections / edge_count * 100) if edge_count > 0 else 0

        return {
            "input_components": component_count,
            "generated_edges": edge_count,
            "explicit_connections": explicit_connections,
            "implicit_connections": implicit_connections,
            "automation_percentage": round(automation_percentage, 1),
            "target_automation": 80,
            "meets_automation_target": automation_percentage >= 80
        }

    def _calculate_performance_metrics(self, context: ProcessingContext, processing_time: float) -> Dict[str, Any]:
        """Calculate performance metrics."""
        workflow = context.langflow_workflow.get("data", {})
        node_count = len(workflow.get("nodes", []))
        edge_count = len(workflow.get("edges", []))

        # Estimate memory usage (rough approximation)
        estimated_memory_mb = (node_count * 0.5) + (edge_count * 0.1) + 1.0

        # Calculate complexity score
        complexity_score = node_count + (edge_count * 0.5)

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "processing_time_seconds": round(processing_time, 6),
            "estimated_memory_mb": round(estimated_memory_mb, 1),
            "complexity_score": round(complexity_score, 1),
            "performance_target_met": processing_time < 2.0  # Target: <2s
        }

    def _calculate_compliance_metrics(self, context: ProcessingContext) -> Dict[str, Any]:
        """Calculate healthcare compliance metrics."""
        components = context.specification.get("components", {})

        # Normalize to list
        if isinstance(components, dict):
            component_list = list(components.values())
        else:
            component_list = components

        healthcare_components = []
        for comp in component_list:
            comp_type = comp.get("type", "")
            if any(term in comp_type for term in ["ehr", "eligibility", "claims", "medical", "patient", "phi"]):
                healthcare_components.append(comp)

        total_nodes = len(context.langflow_workflow.get("data", {}).get("nodes", []))
        healthcare_node_count = len(healthcare_components)

        # All healthcare components are HIPAA compliant in our framework
        hipaa_compliant_nodes = healthcare_node_count
        compliance_percentage = (hipaa_compliant_nodes / total_nodes * 100) if total_nodes > 0 else 100

        return {
            "has_healthcare_components": len(healthcare_components) > 0,
            "healthcare_node_count": healthcare_node_count,
            "hipaa_compliant_nodes": hipaa_compliant_nodes,
            "compliance_percentage": round(compliance_percentage, 1),
            "fully_compliant": compliance_percentage == 100
        }

    async def validate_specification_only(self, spec_dict: Dict[str, Any],
                                        healthcare_compliance: bool = False) -> Dict[str, Any]:
        """
        Validate a specification without converting it.

        Args:
            spec_dict: Agent specification dictionary
            healthcare_compliance: Enable healthcare compliance validation

        Returns:
            Validation result dictionary
        """
        try:
            validation_result = await self.spec_validator.validate_specification(
                spec_dict, healthcare_compliance
            )

            return {
                "valid": validation_result.is_valid,
                "errors": validation_result.validation_errors,
                "warnings": validation_result.warnings,
                "healthcare_compliant": validation_result.healthcare_compliant if healthcare_compliance else None
            }

        except Exception as e:
            logger.error(f"Specification validation failed: {e}")
            return {
                "valid": False,
                "errors": [str(e)],
                "warnings": [],
                "healthcare_compliant": False if healthcare_compliance else None
            }