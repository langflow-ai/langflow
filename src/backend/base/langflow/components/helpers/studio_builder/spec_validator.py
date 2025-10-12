"""Spec Validator Tool for Agent Builder."""

import json
import yaml
from typing import Dict, Any, List

from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger


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

            # Try to use the SpecService if available
            try:
                from langflow.services.spec.service import SpecService

                service = SpecService()
                validation_result = service.validate_spec(self.spec_yaml)

                # Add suggestions based on common issues
                if not validation_result.get("valid"):
                    validation_result["suggestions"] = self._generate_suggestions(
                        validation_result.get("errors", []),
                        spec_data
                    )

                return Data(data=validation_result)

            except ImportError:
                logger.info("SpecService not available, using built-in validation")
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

        return suggestions