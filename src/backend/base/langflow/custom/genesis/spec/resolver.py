"""Variable Resolver for runtime configuration."""

import os
import re
from typing import Dict, Any, Union, Optional
import logging

logger = logging.getLogger(__name__)


class VariableResolver:
    """Resolves variables in specifications at runtime."""

    def __init__(self, variables: Optional[Dict[str, Any]] = None):
        """Initialize with optional variables."""
        self.variables = variables or {}
        self.env_vars = os.environ.copy()

    def resolve(self, data: Any, variables: Optional[Dict[str, Any]] = None) -> Any:
        """
        Resolve variables in data structure.

        Args:
            data: Data to resolve (can be dict, list, string, etc.)
            variables: Additional variables to use for resolution

        Returns:
            Data with variables resolved
        """
        # Merge variables
        resolver_vars = {**self.variables, **(variables or {})}

        return self._resolve_recursive(data, resolver_vars)

    def _resolve_recursive(self, data: Any, variables: Dict[str, Any]) -> Any:
        """Recursively resolve variables in data structures."""
        if isinstance(data, dict):
            return {
                key: self._resolve_recursive(value, variables)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [
                self._resolve_recursive(item, variables)
                for item in data
            ]
        elif isinstance(data, str):
            return self._resolve_string(data, variables)
        else:
            return data

    def _resolve_string(self, text: str, variables: Dict[str, Any]) -> Any:
        """
        Resolve variables in a string.

        Supports:
        - {variable} syntax for runtime variables
        - ${ENV_VAR} syntax for environment variables
        - Nested access with dot notation {config.api_key}
        """
        # Check if entire string is a variable reference
        if text.startswith("{") and text.endswith("}") and text.count("{") == 1:
            var_name = text[1:-1]
            value = self._get_variable_value(var_name, variables)
            if value is not None:
                # Return the actual value type (not stringified)
                return value
            else:
                # Keep as variable reference for Langflow to resolve
                logger.debug(f"Keeping unresolved variable: {text}")
                return text

        # Check for environment variable
        if text.startswith("${") and text.endswith("}"):
            env_var = text[2:-1]
            value = self.env_vars.get(env_var)
            if value is not None:
                return value
            else:
                logger.warning(f"Environment variable not found: {env_var}")
                return text

        # Replace variables within string
        def replace_var(match):
            var_name = match.group(1)
            value = self._get_variable_value(var_name, variables)
            if value is not None:
                return str(value)
            else:
                # Keep unresolved
                return match.group(0)

        # Replace {variable} patterns
        text = re.sub(r'\{([^}]+)\}', replace_var, text)

        # Replace ${ENV_VAR} patterns
        def replace_env(match):
            env_var = match.group(1)
            value = self.env_vars.get(env_var)
            if value is not None:
                return value
            else:
                return match.group(0)

        text = re.sub(r'\$\{([^}]+)\}', replace_env, text)

        return text

    def _get_variable_value(self, var_name: str, variables: Dict[str, Any]) -> Any:
        """Get variable value, supporting dot notation for nested access."""
        # Handle dot notation
        if "." in var_name:
            parts = var_name.split(".")
            value = variables
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return None
            return value
        else:
            return variables.get(var_name)

    def apply_tweaks(self, flow: Dict[str, Any], tweaks: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply tweaks to a flow after conversion.

        Tweaks format: {"component_id.field": value}
        """
        if not tweaks:
            return flow

        nodes = flow.get("data", {}).get("nodes", [])

        for tweak_key, tweak_value in tweaks.items():
            if "." not in tweak_key:
                logger.warning(f"Invalid tweak format: {tweak_key}")
                continue

            component_id, field_name = tweak_key.rsplit(".", 1)

            # Find the component
            for node in nodes:
                if node.get("id") == component_id:
                    # Apply tweak to template
                    template = node.get("data", {}).get("node", {}).get("template", {})
                    if field_name in template:
                        template[field_name]["value"] = tweak_value
                        logger.info(f"Applied tweak: {tweak_key} = {tweak_value}")
                    else:
                        logger.warning(f"Field not found for tweak: {tweak_key}")
                    break
            else:
                logger.warning(f"Component not found for tweak: {component_id}")

        return flow

    def resolve_flow(self, flow: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve all variables in a flow."""
        return self._resolve_recursive(flow, self.variables)