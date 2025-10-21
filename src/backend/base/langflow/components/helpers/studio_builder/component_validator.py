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
from langflow.custom.genesis.spec.mapper import ComponentMapper


class ComponentValidator(Component):
    """Validates that specifications use only valid genesis components."""

    display_name = "Component Validator"
    description = "Validates components and connections in agent specifications"
    icon = "check-square"
    name = "ComponentValidator"
    category = "Helpers"

    # Valid components cache
    _valid_components_cache = None
    _component_mapper = None

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

    def _get_component_mapper(self) -> ComponentMapper:
        """Get component mapper instance."""
        if self._component_mapper is None:
            self._component_mapper = ComponentMapper()
        return self._component_mapper

    def _get_valid_components(self) -> set:
        """Get valid components from ComponentMapper and API."""
        if self._valid_components_cache is None:
            try:
                # Get available components from ComponentMapper
                mapper = self._get_component_mapper()
                available_components = mapper.get_available_components()

                # Combine genesis mapped types
                genesis_mapped = set(available_components.get("genesis_mapped", {}).keys())

                # Try to get additional components from API
                try:
                    async def _fetch_api_components():
                        async with SpecAPIClient() as client:
                            components = await client.get_available_components()
                            return set(components.keys())

                    api_components = asyncio.run(_fetch_api_components())
                    genesis_mapped.update(api_components)
                except Exception as e:
                    logger.debug(f"Could not fetch from API: {e}")

                self._valid_components_cache = genesis_mapped

            except Exception as e:
                logger.error(f"Failed to get components: {e}")
                # Fallback to essential components from ComponentMapper
                mapper = self._get_component_mapper()
                self._valid_components_cache = {
                    "genesis:chat_input",
                    "genesis:chat_output",
                    "genesis:agent",
                    "genesis:autonomize_agent",
                    "genesis:language_model",
                    "genesis:prompt_template",
                    "genesis:mcp_tool",
                    "genesis:api_request",
                    "genesis:knowledge_hub_search",
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

        # Get available components from ComponentMapper
        mapper = self._get_component_mapper()
        valid_components = self._get_valid_components()

        # Common mistakes and corrections (use ComponentMapper when possible)
        corrections = {
            "input": "genesis:chat_input",
            "output": "genesis:chat_output",
            "llm": "genesis:agent",
            "ai": "genesis:agent",
            "model": "genesis:autonomize_model",
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
            if key in invalid_lower and value in valid_components:
                return value

        # Check if it's missing the genesis: prefix
        if not invalid_type.startswith("genesis:"):
            potential = f"genesis:{invalid_type}"
            if potential in valid_components:
                return potential

        # Use ComponentMapper's intelligent fallback
        try:
            suggestion = mapper._handle_unknown_type(invalid_type)
            suggested_component = suggestion.get("component")
            if suggested_component:
                # Find the genesis type that maps to this component
                available_components = mapper.get_available_components()
                for genesis_type, mapping in available_components.get("genesis_mapped", {}).items():
                    if mapping.get("component") == suggested_component:
                        return genesis_type
        except Exception as e:
            logger.debug(f"Error getting suggestion from ComponentMapper: {e}")

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

        # Get valid components from ComponentMapper
        mapper = self._get_component_mapper()
        valid_components = self._get_valid_components()

        # Define pattern requirements using available components
        input_types = {"genesis:chat_input", "genesis:text_input"} & valid_components
        output_types = {"genesis:chat_output", "genesis:text_output"} & valid_components
        agent_types = {"genesis:agent", "genesis:autonomize_agent", "genesis:language_model"} & valid_components
        tool_types = {"genesis:mcp_tool", "genesis:api_request", "genesis:knowledge_hub_search"} & valid_components
        prompt_types = {"genesis:prompt_template", "genesis:genesis_prompt"} & valid_components

        # Identify pattern and missing components
        has_input = bool(component_types & input_types)
        has_output = bool(component_types & output_types)
        has_agent = bool(component_types & agent_types)
        has_tools = bool(component_types & tool_types)
        has_prompt = bool(component_types & prompt_types)

        if has_input and has_output:
            if has_agent:
                # Basic agent pattern
                pattern = "simple_linear"
                missing = []

                # Check for enhancements
                if has_tools:
                    pattern = "agent_with_tools"
                elif has_prompt:
                    pattern = "agent_with_prompt"

                return {"pattern": pattern, "missing": missing}
            else:
                missing_agents = list(agent_types - component_types) if agent_types else ["genesis:agent"]
                return {"pattern": "incomplete", "missing": missing_agents[:1]}  # Suggest just one
        else:
            missing = []
            if not has_input:
                missing_inputs = list(input_types) if input_types else ["genesis:chat_input"]
                missing.append(missing_inputs[0])
            if not has_output:
                missing_outputs = list(output_types) if output_types else ["genesis:chat_output"]
                missing.append(missing_outputs[0])
            if not has_agent:
                missing_agents = list(agent_types) if agent_types else ["genesis:agent"]
                missing.append(missing_agents[0])

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