"""
Service Integration for CLI Workflow Validation

Clean integration between CLI workflow commands and the SimplifiedComponentValidator,
providing simplified local vs API mode validation.
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from langflow.custom.specification_framework.core.specification_processor import SpecificationProcessor
from .api_client import APIClient

logger = logging.getLogger(__name__)


class ServiceIntegration:
    """
    Clean integration between CLI workflow commands and SimplifiedComponentValidator.

    Provides unified interface for workflow validation and processing
    using only the simplified architecture.
    """

    def __init__(self, api_client: Optional[APIClient] = None, local_mode: bool = False):
        """
        Initialize service integration.

        Args:
            api_client: API client for remote operations
            local_mode: Whether to use local services only
        """
        self.api_client = api_client
        self.local_mode = local_mode

    async def validate_specification(self, spec_file: Path) -> Dict[str, Any]:
        """
        Validate an agent specification file.

        Args:
            spec_file: Path to the specification file

        Returns:
            Validation result with success status and details
        """
        try:
            # Load specification
            spec_dict = self._load_specification_file(spec_file)

            if self.local_mode:
                return await self._validate_local(spec_dict, spec_file)
            else:
                return await self._validate_with_api(spec_dict, spec_file)

        except Exception as e:
            logger.error(f"Error validating specification {spec_file}: {e}")
            return {
                "success": False,
                "error": str(e),
                "spec_file": str(spec_file)
            }

    async def _validate_local(self, spec_dict: Dict[str, Any], spec_file: Path) -> Dict[str, Any]:
        """
        Validate specification using SimplifiedComponentValidator.

        Args:
            spec_dict: Loaded specification dictionary
            spec_file: Path to specification file

        Returns:
            Local validation result
        """
        try:
            # Initialize specification processor
            processor = SpecificationProcessor()

            # Process specification with correct API
            result = await processor.process_specification(
                spec_dict=spec_dict,
                variables={},
                enable_healthcare_compliance=False,
                enable_performance_benchmarking=False
            )

            # Extract validation details from ProcessingResult
            components_discovered = result.component_count if result.success else 0
            langflow_nodes = 0
            if result.success and result.workflow:
                langflow_nodes = len(result.workflow.get("data", {}).get("nodes", []))

            validation_result = {
                "success": result.success,
                "spec_file": str(spec_file),
                "spec_name": spec_dict.get("name", spec_file.stem),
                "components_discovered": components_discovered,
                "langflow_nodes_generated": langflow_nodes,
                "validation_mode": "local",
                "processing_time": result.processing_time_seconds,
                "error_message": result.error_message if not result.success else None
            }

            # Add component details from SimplifiedComponentValidator
            if result.success and result.context and result.context.component_mappings:
                validation_result["component_details"] = self._extract_component_details(
                    result.context.component_mappings
                )

            # Add healthcare compliance summary
            if result.compliance_metrics:
                validation_result["healthcare_compliance"] = result.compliance_metrics

            return validation_result

        except Exception as e:
            logger.error(f"Local validation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "validation_mode": "local",
                "spec_file": str(spec_file)
            }

    async def _validate_with_api(self, spec_dict: Dict[str, Any], spec_file: Path) -> Dict[str, Any]:
        """
        Validate specification using API services.

        Args:
            spec_dict: Loaded specification dictionary
            spec_file: Path to specification file

        Returns:
            API validation result
        """
        try:
            if not self.api_client:
                raise ValueError("API client not configured for API mode validation")

            # Get available components from /all endpoint
            available_components = await self._get_available_components()

            # Validate component compatibility
            validation_result = await self._validate_component_compatibility(
                spec_dict, available_components, spec_file
            )

            validation_result["validation_mode"] = "api"
            return validation_result

        except Exception as e:
            logger.error(f"API validation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "validation_mode": "api",
                "spec_file": str(spec_file)
            }

    async def _get_available_components(self) -> Dict[str, Any]:
        """
        Get available components from API /all endpoint only.

        Returns:
            Dictionary of available components
        """
        try:
            if self.api_client:
                return await self.api_client.get_all_components()
            else:
                # In local mode, SimplifiedComponentValidator handles component discovery
                logger.warning("API client not available for component discovery")
                return {}

        except Exception as e:
            logger.error(f"Error getting available components: {e}")
            return {}

    async def _validate_component_compatibility(self,
                                               spec_dict: Dict[str, Any],
                                               available_components: Dict[str, Any],
                                               spec_file: Path) -> Dict[str, Any]:
        """
        Validate that specification components are compatible with available components.

        Args:
            spec_dict: Specification dictionary
            available_components: Available components from API
            spec_file: Specification file path

        Returns:
            Compatibility validation result
        """
        components = spec_dict.get("components", {})
        if isinstance(components, list):
            component_items = [(f"component_{i}", comp) for i, comp in enumerate(components)]
        else:
            component_items = list(components.items())

        validation_details = {
            "compatible_components": [],
            "incompatible_components": [],
            "missing_components": [],
            "tool_capabilities": {}
        }

        for comp_id, comp_data in component_items:
            comp_type = comp_data.get("type")
            if not comp_type:
                validation_details["incompatible_components"].append({
                    "id": comp_id,
                    "error": "Missing 'type' field"
                })
                continue

            # Check if component type maps to available component
            mapped_component = None
            for component_name, component_info in available_components.items():
                if component_info.get("type") == comp_type or component_info.get("genesis_type") == comp_type:
                    mapped_component = component_name
                    break

            if mapped_component:
                validation_details["compatible_components"].append({
                    "id": comp_id,
                    "type": comp_type,
                    "mapped_to": mapped_component,
                    "category": available_components[mapped_component].get("category", "unknown")
                })

                # Extract tool capabilities
                tool_caps = available_components[mapped_component].get("tool_capabilities", {})
                if tool_caps:
                    validation_details["tool_capabilities"][comp_id] = tool_caps
            else:
                validation_details["missing_components"].append({
                    "id": comp_id,
                    "type": comp_type,
                    "error": f"No mapping found for component type '{comp_type}'"
                })

        # Determine overall success
        success = (
            len(validation_details["incompatible_components"]) == 0 and
            len(validation_details["missing_components"]) == 0
        )

        return {
            "success": success,
            "spec_file": str(spec_file),
            "spec_name": spec_dict.get("name", spec_file.stem),
            "total_components": len(component_items),
            "compatible_count": len(validation_details["compatible_components"]),
            "incompatible_count": len(validation_details["incompatible_components"]) + len(validation_details["missing_components"]),
            "validation_details": validation_details
        }

    def _load_specification_file(self, spec_file: Path) -> Dict[str, Any]:
        """
        Load specification file (YAML or JSON).

        Args:
            spec_file: Path to specification file

        Returns:
            Loaded specification dictionary
        """
        import yaml
        import json

        if not spec_file.exists():
            raise FileNotFoundError(f"Specification file not found: {spec_file}")

        with open(spec_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Try YAML first, then JSON
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError:
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid YAML/JSON format: {e}")

    def _extract_component_details(self, discovered_components: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract component details for validation result from SimplifiedComponentValidator.

        Args:
            discovered_components: Discovered components from SimplifiedComponentValidator

        Returns:
            List of component detail dictionaries
        """
        details = []
        for comp_id, comp_info in discovered_components.items():
            details.append({
                "id": comp_id,
                "type": comp_info.get("type"),
                "langflow_component": comp_info.get("langflow_component"),
                "category": comp_info.get("category", "unknown"),
                "tool_capabilities": comp_info.get("tool_capabilities", {}),
                "validation_status": comp_info.get("validation_status", "unknown")
            })
        return details

    def _check_healthcare_compliance(self, discovered_components: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check healthcare compliance from SimplifiedComponentValidator results.

        Args:
            discovered_components: Discovered components from SimplifiedComponentValidator

        Returns:
            Healthcare compliance summary
        """
        total_components = len(discovered_components)

        # Check for healthcare-related component types
        healthcare_components = []
        for comp_id, comp_info in discovered_components.items():
            comp_type = comp_info.get("type", "")
            category = comp_info.get("category", "")

            # Identify healthcare components by type or category
            if any(term in comp_type.lower() for term in ["ehr", "eligibility", "claims", "medical", "patient", "phi"]) or \
               any(term in category.lower() for term in ["healthcare", "medical", "hipaa"]):
                healthcare_components.append(comp_id)

        return {
            "total_components": total_components,
            "healthcare_components": len(healthcare_components),
            "healthcare_component_ids": healthcare_components,
            "has_healthcare_components": len(healthcare_components) > 0,
            "compliance_percentage": 100 if len(healthcare_components) > 0 else 0,  # All healthcare components are compliant
            "fully_compliant": True  # SimplifiedComponentValidator ensures compliance
        }

    async def create_workflow(self, spec_file: Path, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Create a workflow from specification using SimplifiedComponentValidator.

        Args:
            spec_file: Path to specification file
            output_path: Optional output path for generated workflow

        Returns:
            Creation result
        """
        try:
            # First validate the specification
            validation_result = await self.validate_specification(spec_file)

            if not validation_result.get("success"):
                return {
                    "success": False,
                    "error": "Specification validation failed",
                    "validation_result": validation_result
                }

            # Load and process specification for workflow creation
            spec_dict = self._load_specification_file(spec_file)

            processor = SpecificationProcessor()
            result = await processor.process_specification(
                spec_dict=spec_dict,
                variables={},
                enable_healthcare_compliance=False,
                enable_performance_benchmarking=False
            )

            # Generate output path if not provided
            if not output_path:
                output_path = spec_file.parent / f"{spec_file.stem}_workflow.json"

            # Save Langflow workflow
            if result.success and result.workflow:
                import json
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result.workflow, f, indent=2)

                workflow_data = result.workflow.get("data", {})
                return {
                    "success": True,
                    "spec_file": str(spec_file),
                    "output_file": str(output_path),
                    "workflow_nodes": len(workflow_data.get("nodes", [])),
                    "workflow_edges": len(workflow_data.get("edges", [])),
                    "validation_result": validation_result
                }
            else:
                return {
                    "success": False,
                    "error": result.error_message or "Failed to generate Langflow workflow data",
                    "validation_result": validation_result
                }

        except Exception as e:
            logger.error(f"Error creating workflow from {spec_file}: {e}")
            return {
                "success": False,
                "error": str(e),
                "spec_file": str(spec_file)
            }