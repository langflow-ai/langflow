"""Configuration validator for YAML specifications.

Validates that each component's `config` keys exist in the component's
catalog template and that provided values match expected types and list
shapes. Uses the shared ComponentResolver cache (no direct JSON reads).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .component_resolver import ComponentResolver

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validates per-component config keys and types against catalog templates."""

    def __init__(self, resolver: ComponentResolver):
        self.resolver = resolver

    async def validate(self, yaml_content: str) -> List[str]:
        """Validate configuration blocks in the YAML spec.

        Checks (only for provided keys, no missing-key enforcement):
        - `config` must be an object when present
        - Each provided `config` key must exist in the component's template
        - Types of provided values must match the template `type`
        - If template field has `list: true`, provided value must be a list;
          non-list when `list: false`

        Notes:
        - Special-case: skip type/list validation for keys 'headers' and 'body'.
          These keys often accept flexible structures.

        Returns list of error messages (empty if valid).
        """
        errors: List[str] = []
        IGNORED_TYPE_KEYS = {"headers", "body"}

        # Parse YAML
        try:
            spec_dict = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            return [f"YAML parsing error: {str(e)}"]

        if not isinstance(spec_dict, dict) or not spec_dict:
            return ["Empty or invalid YAML content"]

        # Ensure catalog is loaded (prefer cache, fetch if empty)
        try:
            if not self.resolver.get_cached_components():
                await self.resolver.fetch_all_components()
        except Exception as e:
            logger.error(f"Failed to load component catalog: {e}")
            return [f"Failed to load component catalog: {str(e)}"]

        components = spec_dict.get("components", [])
        if not isinstance(components, list):
            return ["'components' must be a list"]

        for comp in components:
            if not isinstance(comp, dict):
                errors.append("Each item in 'components' must be an object")
                continue

            comp_id = comp.get("id", "unknown")
            comp_type = comp.get("type")
            comp_cfg = comp.get("config", {})

            if not comp_type:
                errors.append(f"Component '{comp_id}' missing required field 'type'")
                continue

            # Lookup component in catalog
            lookup = self.resolver.find_component(comp_type)
            if not lookup:
                # Component existence is validated elsewhere; skip config checks
                logger.debug(f"Skipping config validation for unknown component type: {comp_type}")
                continue

            _category, _catalog_name, comp_data = lookup
            template = comp_data.get("template")
            if not isinstance(template, dict):
                # No template means no config validation context
                logger.debug(f"No template found for component type: {comp_type}")
                continue

            # config must be dict if present
            if comp_cfg is None:
                comp_cfg = {}
            if not isinstance(comp_cfg, dict):
                errors.append(
                    f"Component '{comp_id}' (type: '{comp_type}') has invalid 'config': expected object"
                )
                continue

            # Allowed keys are template field names excluding internal marker keys
            internal_keys = {"_type"}
            allowed_keys = {k for k in template.keys() if k not in internal_keys}

            # Unknown keys
            for key in comp_cfg.keys():
                if key not in allowed_keys:
                    errors.append(
                        f"Unknown config key '{key}' for component '{comp_id}' (type: '{comp_type}')."
                    )

            # Type checks for provided keys
            for key, value in comp_cfg.items():
                # Skip type/list validation for flexible keys
                if key in IGNORED_TYPE_KEYS:
                    continue
                t_cfg = template.get(key)
                if not isinstance(t_cfg, dict):
                    # If template missing details, skip strict type checking
                    continue

                list_expected = bool(t_cfg.get("list", False))
                field_type = self._normalize_field_type(t_cfg.get("type"))

                # List shape validation
                if list_expected and not isinstance(value, list):
                    errors.append(
                        f"Config key '{key}' on component '{comp_id}' expects a list, got {type(value).__name__}."
                    )
                    continue
                if not list_expected and isinstance(value, list):
                    errors.append(
                        f"Config key '{key}' on component '{comp_id}' expects a non-list value, got list."
                    )
                    continue

                # Base type validation
                def is_type_ok(v: Any, expected: Optional[str]) -> bool:
                    if expected is None or expected == "any":
                        return True
                    if expected == "str":
                        return isinstance(v, str)
                    if expected == "int":
                        return isinstance(v, int)
                    if expected == "float":
                        return isinstance(v, (float, int))
                    if expected == "bool":
                        return isinstance(v, bool)
                    if expected == "dict":
                        return isinstance(v, dict)
                    # For types like 'code', 'query', treat as string
                    if expected in {"code", "query", "password", "secret", "file"}:
                        return isinstance(v, str)
                    # Fallback: accept any
                    return True

                if list_expected:
                    for idx, item in enumerate(value):
                        if not is_type_ok(item, field_type):
                            errors.append(
                                f"Config key '{key}[{idx}]' on component '{comp_id}' has wrong type: "
                                f"expected {field_type}, got {type(item).__name__}."
                            )
                else:
                    if not is_type_ok(value, field_type):
                        errors.append(
                            f"Config key '{key}' on component '{comp_id}' has wrong type: "
                            f"expected {field_type}, got {type(value).__name__}."
                        )

        return errors

    @staticmethod
    def _normalize_field_type(t: Any) -> Optional[str]:
        """Normalize template field 'type' values to basic Python types.

        Returns one of: 'str', 'int', 'float', 'bool', 'dict', 'code', 'query', 'file', 'any', or None.
        """
        if not isinstance(t, str) or not t:
            return None
        t_lower = t.strip().lower()
        if t_lower in {"str", "string"}:
            return "str"
        if t_lower in {"int", "integer"}:
            return "int"
        if t_lower in {"float", "double"}:
            return "float"
        if t_lower in {"bool", "boolean"}:
            return "bool"
        if t_lower in {"dict", "object"}:
            return "dict"
        if t_lower in {"code", "query", "file", "password", "secret"}:
            return t_lower
        if t_lower in {"other", "any"}:
            return "any"
        # Unknown types: be permissive
        return None