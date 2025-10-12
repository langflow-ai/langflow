"""Component Validator for AI Studio Agent Builder - Validates component usage."""

import asyncio
import yaml
from typing import Dict, List, Any, Optional
from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger
from langflow.components.helpers.studio_builder.api_client import SpecAPIClient


class ComponentValidator(Component):
    """Validates that specifications use only valid genesis components."""

    display_name = "Component Validator"
    description = "Validates components and connections in agent specifications"
    icon = "check-square"
    name = "ComponentValidator"
    category = "Helpers"

    # Valid components cache
    _valid_components_cache = None

    # Valid connection types
    VALID_CONNECTION_TYPES = {
        "input", "output", "prompt", "tools", "agent", "task", "agents", "tasks"
    }

    inputs = [
        MessageTextInput(
            name="specification",
            display_name="Specification",
            info="YAML specification or component list to validate",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Validation Result", name="result", method="validate"),
    ]

    def _get_valid_components(self) -> set:
        """Get valid components from API if not cached."""
        if self._valid_components_cache is None:
            try:
                async def _fetch_components():
                    async with SpecAPIClient() as client:
                        components = await client.get_available_components()
                        return set(components.keys())

                self._valid_components_cache = asyncio.run(_fetch_components())
            except Exception as e:
                logger.error(f"Failed to get components from API: {e}")
                # Fallback to essential components
                self._valid_components_cache = {
                    "genesis:chat_input",
                    "genesis:chat_output",
                    "genesis:agent",
                    "genesis:language_model"
                }
        return self._valid_components_cache

    def validate(self) -> Data:
        """Validate the components in a specification."""
        try:
            # Parse input - could be YAML or JSON
            if isinstance(self.specification, str):
                try:
                    spec_data = yaml.safe_load(self.specification)
                except yaml.YAMLError:
                    # Try as a simple component list
                    spec_data = {"components": self.specification.split(",")}
            else:
                spec_data = self.specification

            errors = []
            warnings = []
            suggestions = []
            validated_components = []

            # Get components from spec
            components = spec_data.get("components", [])

            if not components:
                errors.append("No components found in specification")
                return self._create_response(False, errors, warnings, suggestions)

            # Validate each component
            for component in components:
                if isinstance(component, dict):
                    comp_type = component.get("type", "")
                    comp_id = component.get("id", "unknown")
                    comp_name = component.get("name", "")
                else:
                    comp_type = str(component).strip()
                    comp_id = comp_type
                    comp_name = comp_type

                # Check if component type is valid
                valid_components = self._get_valid_components()
                if comp_type not in valid_components:
                    errors.append(f"Invalid component type '{comp_type}' for '{comp_id}'")

                    # Suggest corrections
                    suggestion = self._suggest_component(comp_type, comp_name)
                    if suggestion:
                        suggestions.append(f"Replace '{comp_type}' with '{suggestion}'")
                else:
                    validated_components.append({
                        "id": comp_id,
                        "type": comp_type,
                        "valid": True
                    })

                # Validate connections if present
                if isinstance(component, dict) and "provides" in component:
                    connection_errors = self._validate_connections(component)
                    errors.extend(connection_errors)

            # Check for required components based on pattern
            pattern_check = self._check_pattern_requirements(validated_components)
            if pattern_check["missing"]:
                warnings.append(f"Missing typical components: {', '.join(pattern_check['missing'])}")
                suggestions.append(f"Consider adding: {', '.join(pattern_check['missing'])}")

            # Determine overall validity
            is_valid = len(errors) == 0

            return self._create_response(
                is_valid,
                errors,
                warnings,
                suggestions,
                validated_components=validated_components,
                pattern=pattern_check.get("pattern", "unknown")
            )

        except Exception as e:
            logger.error(f"Error validating components: {e}")
            return self._create_response(
                False,
                [f"Validation error: {str(e)}"],
                [],
                []
            )

    def _suggest_component(self, invalid_type: str, name: str) -> Optional[str]:
        """Suggest a valid component type based on the invalid one."""
        invalid_lower = invalid_type.lower()

        # Common mistakes and corrections
        corrections = {
            "input": "genesis:chat_input",
            "output": "genesis:chat_output",
            "llm": "genesis:agent",
            "ai": "genesis:agent",
            "model": "genesis:agent",
            "prompt": "genesis:prompt_template",
            "template": "genesis:prompt_template",
            "tool": "genesis:mcp_tool",
            "api": "genesis:api_request",
            "http": "genesis:api_request",
            "rest": "genesis:api_request",
            "search": "genesis:knowledge_hub_search",
            "knowledge": "genesis:knowledge_hub_search",
            "rag": "genesis:knowledge_hub_search",
            "crew": "genesis:crewai_sequential_crew",
            "task": "genesis:crewai_sequential_task"
        }

        # Check for partial matches
        for key, value in corrections.items():
            if key in invalid_lower:
                return value

        # Check if it's missing the genesis: prefix
        if not invalid_type.startswith("genesis:"):
            potential = f"genesis:{invalid_type}"
            valid_components = self._get_valid_components()
            if potential in valid_components:
                return potential

        return None

    def _validate_connections(self, component: Dict) -> List[str]:
        """Validate the connections in a component."""
        errors = []
        provides = component.get("provides", [])

        for connection in provides:
            if isinstance(connection, dict):
                use_as = connection.get("useAs", "")
                if use_as and use_as not in self.VALID_CONNECTION_TYPES:
                    errors.append(
                        f"Invalid connection type '{use_as}' in component '{component.get('id', 'unknown')}'. "
                        f"Valid types: {', '.join(self.VALID_CONNECTION_TYPES)}"
                    )

                # Check if 'in' field references a valid component
                target = connection.get("in", "")
                if not target:
                    errors.append(
                        f"Connection in component '{component.get('id', 'unknown')}' missing 'in' field"
                    )

        return errors

    def _check_pattern_requirements(self, components: List[Dict]) -> Dict:
        """Check if components match a known pattern."""
        component_types = {c["type"] for c in components}

        # Identify pattern and missing components
        if "genesis:chat_input" in component_types and "genesis:chat_output" in component_types:
            if "genesis:agent" in component_types or "genesis:language_model" in component_types:
                # Basic agent pattern
                pattern = "simple_linear"
                missing = []

                # Check for enhancements
                if any(t in component_types for t in ["genesis:mcp_tool", "genesis:api_request"]):
                    pattern = "agent_with_tools"
                elif "genesis:prompt_template" in component_types:
                    pattern = "agent_with_prompt"

                return {"pattern": pattern, "missing": missing}
            else:
                return {"pattern": "incomplete", "missing": ["genesis:agent or genesis:language_model"]}
        else:
            missing = []
            if "genesis:chat_input" not in component_types:
                missing.append("genesis:chat_input")
            if "genesis:chat_output" not in component_types:
                missing.append("genesis:chat_output")
            if "genesis:agent" not in component_types and "genesis:language_model" not in component_types:
                missing.append("genesis:agent or genesis:language_model")

            return {"pattern": "incomplete", "missing": missing}

    def _create_response(self, valid: bool, errors: List[str],
                        warnings: List[str], suggestions: List[str],
                        validated_components: List[Dict] = None,
                        pattern: str = None) -> Data:
        """Create a structured validation response."""
        response = {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "message": "Validation successful" if valid else "Validation failed"
        }

        if validated_components:
            response["validated_components"] = validated_components
            response["total_components"] = len(validated_components)

        if pattern:
            response["detected_pattern"] = pattern

        return Data(data=response)