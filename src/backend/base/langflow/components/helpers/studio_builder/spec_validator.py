"""Spec Validator Tool for Agent Builder."""

import asyncio
import json
import yaml
from typing import Dict, Any, List

from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger
from langflow.components.helpers.studio_builder.api_client import SpecAPIClient


class SpecValidatorTool(Component):
    """Tool for validating agent specifications."""

    display_name = "Spec Validator"
    description = "Validate agent specifications using the validation service"
    icon = "check-circle"
    name = "SpecValidatorTool"
    category = "Helpers"

    inputs = [
        MessageTextInput(
            name="spec_yaml",
            display_name="Specification YAML",
            info="YAML specification to validate",
            placeholder="Paste or provide the YAML specification here",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="validation_mode",
            display_name="Validation Mode",
            info="Level of validation: 'basic' or 'comprehensive'",
            value="comprehensive",
            advanced=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Validation Result", name="result", method="validate"),
    ]

    def validate(self) -> Data:
        """Validate the agent specification."""
        try:
            # Parse the YAML specification
            try:
                spec_data = yaml.safe_load(self.spec_yaml)
            except yaml.YAMLError as e:
                return Data(data={
                    "valid": False,
                    "errors": [f"YAML parsing error: {str(e)}"],
                    "warnings": [],
                    "suggestions": ["Fix the YAML syntax errors before validation"]
                })

            # Use the API client to validate
            try:
                async def _validate_via_api():
                    async with SpecAPIClient() as client:
                        return await client.validate_spec(self.spec_yaml)

                validation_result = asyncio.run(_validate_via_api())

                # Add suggestions based on common issues
                if not validation_result.get("valid"):
                    validation_result["suggestions"] = self._generate_suggestions(
                        validation_result.get("errors", []),
                        spec_data
                    )

                return Data(data=validation_result)

            except Exception as api_error:
                logger.warning(f"API validation failed, using built-in validation: {api_error}")
                # Fall back to built-in validation
                return self._builtin_validate(spec_data)

        except Exception as e:
            logger.error(f"Error validating specification: {e}")
            return Data(data={
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "suggestions": []
            })

    def _builtin_validate(self, spec_data: Dict[str, Any]) -> Data:
        """Built-in validation when SpecService is not available."""
        errors = []
        warnings = []
        suggestions = []

        # Required fields validation
        required_fields = ["id", "name", "description", "kind", "components"]
        for field in required_fields:
            if field not in spec_data:
                errors.append(f"Required field '{field}' is missing")
                suggestions.append(f"Add the '{field}' field to your specification")

        # Validate ID format
        if "id" in spec_data:
            spec_id = spec_data["id"]
            if not spec_id.startswith("urn:agent:genesis:"):
                warnings.append(f"ID should follow the format: urn:agent:genesis:[domain]:[name]:[version]")
                suggestions.append(f"Update ID to: urn:agent:genesis:{spec_data.get('domain', 'domain')}:{spec_data.get('name', 'name').lower().replace(' ', '-')}:1.0.0")

        # Validate kind
        if "kind" in spec_data:
            valid_kinds = ["Single Agent", "Multi Agent"]
            if spec_data["kind"] not in valid_kinds:
                errors.append(f"Invalid kind: {spec_data['kind']}. Must be one of: {valid_kinds}")
                suggestions.append(f"Change 'kind' to either 'Single Agent' or 'Multi Agent'")

        # Validate components
        if "components" in spec_data:
            if not isinstance(spec_data["components"], list):
                errors.append("Components must be a list")
                suggestions.append("Ensure 'components' is a list of component definitions")
            else:
                for i, component in enumerate(spec_data["components"]):
                    if not isinstance(component, dict):
                        errors.append(f"Component {i} is not a dictionary")
                        continue

                    # Check component required fields
                    comp_required = ["id", "type", "name"]
                    for field in comp_required:
                        if field not in component:
                            errors.append(f"Component '{component.get('id', f'index-{i}')}' is missing required field '{field}'")
                            suggestions.append(f"Add '{field}' to component {component.get('id', f'index-{i}')}")

                    # Check component type format
                    if "type" in component:
                        comp_type = component["type"]
                        if not comp_type.startswith("genesis:"):
                            warnings.append(f"Component type '{comp_type}' should start with 'genesis:' prefix")
                            suggestions.append(f"Update component type to 'genesis:{comp_type}'")

                        # **NEW: MCP Tool Detection and Warning**
                        if comp_type == "genesis:mcp_tool":
                            errors.append(f"Component '{component.get('id', f'index-{i}')}' uses deprecated 'genesis:mcp_tool' type")
                            suggestions.append(f"Replace 'genesis:mcp_tool' with appropriate healthcare connector:")
                            suggestions.append("  - Use 'genesis:ehr_connector' for EHR/patient data")
                            suggestions.append("  - Use 'genesis:eligibility_connector' for insurance eligibility")
                            suggestions.append("  - Use 'genesis:autonomize' with Clinical LLM for medical text analysis")
                            suggestions.append("  - Use 'genesis:quality_metrics_connector' for HEDIS/quality data")
                            suggestions.append("  - Use 'genesis:pharmacy_benefits_connector' for PBM/formulary")
                            suggestions.append("  - Use 'genesis:provider_network_connector' for provider directories")
                            suggestions.append("  - Use 'genesis:compliance_data_connector' for regulatory compliance")
                            suggestions.append("  - Use 'genesis:assemblyai_start_transcript' for clinical speech-to-text")
                            suggestions.append("  - Use 'genesis:medical_terminology_connector' for medical coding")
                            suggestions.append("  - Use 'genesis:api_request' for simple HTTP API integrations")
                            suggestions.append("  - Create specialized healthcare agents for complex workflows")

        # Additional metadata validation
        if self.validation_mode == "comprehensive":
            # Check for recommended fields
            recommended_fields = ["domain", "version", "agentGoal", "targetUser"]
            for field in recommended_fields:
                if field not in spec_data:
                    warnings.append(f"Recommended field '{field}' is missing")
                    suggestions.append(f"Consider adding '{field}' for better documentation")

            # Check provides relationships if present
            if "provides" in spec_data:
                self._validate_provides(spec_data, errors, warnings, suggestions)

            # **NEW: Comprehensive MCP Tool Analysis**
            self._analyze_mcp_usage(spec_data, errors, warnings, suggestions)

        # Determine overall validity
        valid = len(errors) == 0

        return Data(data={
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "spec_summary": {
                "name": spec_data.get("name", "Unknown"),
                "kind": spec_data.get("kind", "Unknown"),
                "components_count": len(spec_data.get("components", [])),
                "has_metadata": all(field in spec_data for field in ["domain", "version", "agentGoal"])
            }
        })

    def _validate_provides(self, spec_data: Dict[str, Any],
                          errors: List[str], warnings: List[str],
                          suggestions: List[str]) -> None:
        """Validate provides relationships between components."""
        components = spec_data.get("components", [])
        component_ids = {comp.get("id") for comp in components if "id" in comp}

        for provide in spec_data.get("provides", []):
            if isinstance(provide, dict):
                # Check if referenced components exist
                for field in ["from", "to", "in"]:
                    if field in provide:
                        comp_id = provide[field]
                        if comp_id not in component_ids:
                            errors.append(f"Provides relationship references non-existent component: {comp_id}")
                            suggestions.append(f"Ensure component '{comp_id}' exists or fix the reference")

    def _analyze_mcp_usage(self, spec_data: Dict[str, Any],
                          errors: List[str], warnings: List[str],
                          suggestions: List[str]) -> None:
        """Analyze and provide guidance on MCP tool usage patterns."""
        components = spec_data.get("components", [])
        mcp_tools_found = []

        # Collect all MCP tools and their configurations
        for component in components:
            if component.get("type") == "genesis:mcp_tool":
                tool_config = component.get("config", {})
                tool_name = tool_config.get("tool_name", "unknown")
                mcp_tools_found.append({
                    "id": component.get("id"),
                    "name": component.get("name"),
                    "tool_name": tool_name,
                    "description": component.get("description", "")
                })

        if mcp_tools_found:
            # Add comprehensive guidance for each MCP tool found
            warnings.append(f"Found {len(mcp_tools_found)} MCP tool(s) that should be replaced with healthcare connectors")
            suggestions.append("=== MCP TOOL REPLACEMENT GUIDE ===")

            for tool in mcp_tools_found:
                suggestions.append(f"")
                suggestions.append(f"Component '{tool['id']}' (tool: {tool['tool_name']}):")
                replacement = self._get_mcp_replacement_suggestion(tool['tool_name'], tool['description'])
                suggestions.append(f"  → {replacement}")

            # Add general replacement strategy
            suggestions.append("")
            suggestions.append("=== ENHANCED DECISION FRAMEWORK ===")
            suggestions.append("Priority 1: Autonomize Models (Clinical LLM, Medical Coding)")
            suggestions.append("Priority 2: Healthcare Connectors (PREFERRED)")
            suggestions.append("Priority 3: API Requests (for simple HTTP integrations)")
            suggestions.append("Priority 4: Specialized Agents (for complex workflows)")
            suggestions.append("")
            suggestions.append("All healthcare connectors include:")
            suggestions.append("  ✓ HIPAA compliance and audit logging")
            suggestions.append("  ✓ Comprehensive mock data for development")
            suggestions.append("  ✓ Healthcare-specific error handling")
            suggestions.append("  ✓ PHI protection and security controls")

    def _get_mcp_replacement_suggestion(self, tool_name: str, description: str) -> str:
        """Get specific replacement suggestion based on MCP tool name and description."""
        tool_name_lower = tool_name.lower()
        desc_lower = description.lower()

        # Healthcare data access tools
        if any(keyword in tool_name_lower for keyword in ["ehr", "patient", "medical_record", "clinical_data"]):
            return "Replace with 'genesis:ehr_connector' for HIPAA-compliant EHR integration"
        elif any(keyword in tool_name_lower for keyword in ["eligibility", "insurance", "coverage", "benefits"]):
            return "Replace with 'genesis:eligibility_connector' for insurance eligibility verification"
        elif any(keyword in tool_name_lower for keyword in ["claims", "adjudication", "claim_processing"]):
            return "Replace with 'genesis:claims_connector' for claims processing workflows"
        elif any(keyword in tool_name_lower for keyword in ["pharmacy", "drug", "medication", "formulary", "pbm"]):
            return "Replace with 'genesis:pharmacy_benefits_connector' for PBM and formulary operations"
        elif any(keyword in tool_name_lower for keyword in ["provider", "network", "directory", "npi"]):
            return "Replace with 'genesis:provider_network_connector' for provider directory services"
        elif any(keyword in tool_name_lower for keyword in ["hedis", "quality", "measure", "benchmark"]):
            return "Replace with 'genesis:quality_metrics_connector' for HEDIS and quality analytics"
        elif any(keyword in tool_name_lower for keyword in ["appeals", "grievance", "case_management"]):
            return "Replace with 'genesis:appeals_data_connector' for appeals and grievances"
        elif any(keyword in tool_name_lower for keyword in ["compliance", "audit", "regulatory", "hipaa"]):
            return "Replace with 'genesis:compliance_data_connector' for regulatory compliance"

        # AI/NLP processing tools
        elif any(keyword in tool_name_lower for keyword in ["nlp", "clinical_nlp", "text_analysis", "entity_extraction"]):
            return "Replace with 'genesis:autonomize' using Clinical LLM for medical text analysis"
        elif any(keyword in tool_name_lower for keyword in ["speech", "transcription", "audio", "voice"]):
            return "Replace with 'genesis:assemblyai_start_transcript' for clinical speech-to-text"
        elif any(keyword in tool_name_lower for keyword in ["terminology", "coding", "icd", "cpt", "snomed"]):
            return "Replace with 'genesis:medical_terminology_connector' for medical coding validation"

        # Check description for additional context
        elif any(keyword in desc_lower for keyword in ["ehr", "electronic health", "patient record"]):
            return "Replace with 'genesis:ehr_connector' based on description context"
        elif any(keyword in desc_lower for keyword in ["insurance", "eligibility", "coverage"]):
            return "Replace with 'genesis:eligibility_connector' based on description context"
        elif any(keyword in desc_lower for keyword in ["quality", "hedis", "measure"]):
            return "Replace with 'genesis:quality_metrics_connector' based on description context"

        # Default recommendations
        elif "api" in tool_name_lower or "http" in tool_name_lower:
            return "Replace with 'genesis:api_request' for simple HTTP API integration"
        else:
            return "Replace with appropriate healthcare connector or create specialized agent with custom prompt"

    def _generate_suggestions(self, errors: List[str], spec_data: Dict[str, Any]) -> List[str]:
        """Generate helpful suggestions based on validation errors."""
        suggestions = []

        for error in errors:
            if "Required field" in error:
                field = error.split("'")[1]
                suggestions.append(f"Add '{field}' field with appropriate value")
            elif "component type" in error.lower():
                suggestions.append("Check component type spelling and ensure it starts with 'genesis:'")
            elif "provides" in error.lower():
                suggestions.append("Verify all component IDs in 'provides' relationships exist")
            elif "mcp_tool" in error.lower():
                suggestions.append("Use the Enhanced Decision Framework to select appropriate replacement components")

        return suggestions