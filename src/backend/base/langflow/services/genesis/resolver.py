"""VariableResolver for Genesis specification framework."""

import logging
from typing import Dict, Any, Optional, List
import re

logger = logging.getLogger(__name__)


class VariableResolver:
    """Resolves variables and applies tweaks to Genesis specifications."""

    def __init__(self):
        """Initialize the VariableResolver."""
        self.variable_pattern = re.compile(r'\{\{([^}]+)\}\}')

    def resolve_variables(self, data: Dict[str, Any], variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve variables in the specification data.

        Args:
            data: Specification data containing variables
            variables: Variable values to substitute

        Returns:
            Data with variables resolved
        """
        if not variables:
            return data

        resolved_data = self._deep_resolve(data, variables)
        return resolved_data

    def _deep_resolve(self, obj: Any, variables: Dict[str, Any]) -> Any:
        """
        Recursively resolve variables in nested data structures.

        Args:
            obj: Object to resolve variables in
            variables: Variable values

        Returns:
            Object with variables resolved
        """
        if isinstance(obj, dict):
            return {k: self._deep_resolve(v, variables) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_resolve(item, variables) for item in obj]
        elif isinstance(obj, str):
            return self._resolve_string(obj, variables)
        else:
            return obj

    def _resolve_string(self, text: str, variables: Dict[str, Any]) -> str:
        """
        Resolve variables in a string.

        Args:
            text: String containing variables
            variables: Variable values

        Returns:
            String with variables resolved
        """
        def replace_variable(match):
            var_name = match.group(1).strip()
            return str(variables.get(var_name, match.group(0)))

        return self.variable_pattern.sub(replace_variable, text)

    def apply_tweaks(self, flow_data: Dict[str, Any], tweaks: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply component field tweaks to the flow data.

        Args:
            flow_data: Langflow flow data
            tweaks: Component field tweaks to apply

        Returns:
            Flow data with tweaks applied
        """
        if not tweaks:
            return flow_data

        # Apply tweaks to flow data
        modified_flow = flow_data.copy()

        if "data" in modified_flow and "nodes" in modified_flow["data"]:
            for node in modified_flow["data"]["nodes"]:
                node_id = node.get("id")
                if node_id in tweaks:
                    node_tweaks = tweaks[node_id]
                    self._apply_node_tweaks(node, node_tweaks)

        return modified_flow

    def _apply_node_tweaks(self, node: Dict[str, Any], tweaks: Dict[str, Any]) -> None:
        """
        Apply tweaks to a specific node.

        Args:
            node: Node data to modify
            tweaks: Tweaks to apply to the node
        """
        if "data" not in node:
            return

        node_data = node["data"]

        # Apply template tweaks
        if "template" in node_data and isinstance(tweaks, dict):
            for field_name, field_value in tweaks.items():
                if field_name in node_data["template"]:
                    if "value" in node_data["template"][field_name]:
                        node_data["template"][field_name]["value"] = field_value
                        logger.debug(f"Applied tweak {field_name}={field_value} to node {node.get('id')}")

    def validate_variables(self, spec_data: Dict[str, Any], variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate that all required variables are provided.

        Args:
            spec_data: Specification data
            variables: Provided variables

        Returns:
            Validation result
        """
        required_vars = self._find_required_variables(spec_data)
        provided_vars = set(variables.keys()) if variables else set()
        missing_vars = required_vars - provided_vars

        return {
            "valid": len(missing_vars) == 0,
            "required_variables": list(required_vars),
            "provided_variables": list(provided_vars),
            "missing_variables": list(missing_vars)
        }

    def _find_required_variables(self, obj: Any) -> set:
        """
        Find all variables used in the specification.

        Args:
            obj: Object to search for variables

        Returns:
            Set of variable names
        """
        variables = set()

        if isinstance(obj, dict):
            for value in obj.values():
                variables.update(self._find_required_variables(value))
        elif isinstance(obj, list):
            for item in obj:
                variables.update(self._find_required_variables(item))
        elif isinstance(obj, str):
            matches = self.variable_pattern.findall(obj)
            variables.update(var.strip() for var in matches)

        return variables

    def get_variable_info(self, spec_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get information about variables used in the specification.

        Args:
            spec_data: Specification data

        Returns:
            Variable information
        """
        variables = self._find_required_variables(spec_data)
        variable_locations = self._find_variable_locations(spec_data)

        return {
            "total_variables": len(variables),
            "variable_names": list(variables),
            "variable_locations": variable_locations,
            "variable_usage": {var: len(locations) for var, locations in variable_locations.items()}
        }

    def _find_variable_locations(self, obj: Any, path: str = "") -> Dict[str, List[str]]:
        """
        Find locations where variables are used.

        Args:
            obj: Object to search
            path: Current path in the object

        Returns:
            Dictionary mapping variable names to their locations
        """
        locations = {}

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                child_locations = self._find_variable_locations(value, new_path)
                for var, locs in child_locations.items():
                    locations.setdefault(var, []).extend(locs)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                child_locations = self._find_variable_locations(item, new_path)
                for var, locs in child_locations.items():
                    locations.setdefault(var, []).extend(locs)
        elif isinstance(obj, str):
            matches = self.variable_pattern.findall(obj)
            for var in matches:
                var_name = var.strip()
                locations.setdefault(var_name, []).append(path)

        return locations