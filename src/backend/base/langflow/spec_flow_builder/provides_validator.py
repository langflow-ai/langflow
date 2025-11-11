"""Validator for 'provides' connections in YAML specs.

This module provides a validation routine, optionally exposed as a FastAPI
dependency, to validate the "provides" connections in incoming YAML payloads. It ensures:
- All referenced components exist
- Each target component can accept the provided input type
- The YAML structure for connections is well-formed

On validation failure, it raises an HTTPException with status 400 and detailed errors.
"""

import logging
import re
from typing import Any, Dict, List, Tuple, Optional

import yaml
from fastapi import HTTPException, Body
from .models import ValidateSpecRequest

from .component_resolver import ComponentResolver

logger = logging.getLogger(__name__)


class ProvidesConnectionValidator:
    """Validates 'provides' connections using catalog and component schemas."""

    def __init__(self, resolver: ComponentResolver):
        self.resolver = resolver
        self._components_catalog: Optional[Dict[str, Any]] = None

    def _load_components_catalog(self) -> Dict[str, Any]:
        """Load component catalog from resolver cache to access tool_mode flags and I/O details.

        Returns an empty dict if cache is unavailable.
        """
        if self._components_catalog is not None:
            return self._components_catalog

        try:
            cached = self.resolver.get_cached_components()
            self._components_catalog = cached or {}
        except Exception:
            self._components_catalog = {}
        return self._components_catalog

    def _find_comp_data_by_class(self, class_name: str) -> Optional[Dict[str, Any]]:
        """Find and return component data in the catalog by Python class name.

        This scans the catalog categories, reads `template.code.value`, and matches
        the first `class <Name>` occurrence against `class_name` (case-insensitive).
        Returns the matching component's data dict if found, else None.
        """
        catalog = self._load_components_catalog()
        try:
            for _category, comps in catalog.items():
                if not isinstance(comps, dict):
                    continue
                for _comp_name, comp_data in comps.items():
                    try:
                        template = comp_data.get("template", {})
                        code_field = template.get("code", {})
                        code_value = code_field.get("value", "")
                        if not isinstance(code_value, str) or not code_value:
                            continue
                        # Extract the first class name declaration
                        match = re.search(r"class\s+(\w+)", code_value)
                        if not match:
                            continue
                        found_class = match.group(1)
                        if isinstance(found_class, str) and found_class.lower() == class_name.lower():
                            return comp_data
                    except Exception:
                        # Ignore malformed entries and keep scanning
                        continue
        except Exception:
            return None
        return None

    def _find_tool_mode_output(self, component_class: str) -> Optional[str]:
        """Find an output field marked with tool_mode=true for the given component.

        Returns the output name if found, else None.
        """
        try:
            comp_data = self._find_comp_data_by_class(component_class)
            if not isinstance(comp_data, dict):
                return None
            outputs = comp_data.get("outputs", [])
            for out in outputs:
                if out.get("tool_mode") is True:
                    name = out.get("name")
                    if isinstance(name, str) and name:
                        return name
        except Exception:
            return None
        return None

    def _template_supports_tool_mode(self, component_class: str) -> bool:
        """Return True if any item inside the component's template has tool_mode=true.

        This checks the catalog's `template` object for fields whose config includes
        `tool_mode: true`. If none are present (or template missing), returns False.
        """
        try:
            comp_data = self._find_comp_data_by_class(component_class)
            if not isinstance(comp_data, dict):
                return False
            template = comp_data.get("template")
            if not isinstance(template, dict):
                return False
            for _field_name, field_cfg in template.items():
                if isinstance(field_cfg, dict) and field_cfg.get("tool_mode") is True:
                    return True
        except Exception:
            return False
        return False

    def _preferred_system_prompt_input(self, component_class: str) -> Optional[str]:
        """Return preferred system prompt input name if present on target.

        Prefers 'system_message', falls back to 'system_prompt'. Returns None if neither.
        """
        catalog = self._load_components_catalog()
        try:
            for category, comps in catalog.items():
                comp_data = comps.get(component_class)
                if not isinstance(comp_data, dict):
                    continue
                inputs = comp_data.get("template", {})
                # Inputs in all_components.json are under the 'template' key
                if isinstance(inputs, dict):
                    if "system_message" in inputs:
                        return "system_message"
                    if "system_prompt" in inputs:
                        return "system_prompt"
        except Exception:
            return None
        return None

    async def _get_class_name_for_yaml_type(self, yaml_type: str) -> Tuple[str, str, Dict[str, Any]] | None:
        """Find component info in catalog for a given YAML type (class name).

        Returns tuple (category, catalog_name, comp_data) or None.
        """
        return self.resolver.find_component(yaml_type)

    async def _validate_yaml_structure(self, spec: Dict[str, Any]) -> List[str]:
        """Basic structural validation for components and provides blocks."""
        errors: List[str] = []

        components = spec.get("components")
        if components is None:
            errors.append("Missing 'components' in YAML specification")
            return errors

        if not isinstance(components, list):
            errors.append("'components' must be a list")
            return errors

        for idx, comp in enumerate(components):
            if not isinstance(comp, dict):
                errors.append(f"Component at index {idx} must be a dictionary")
                continue

            # Required fields for component identification
            if "id" not in comp or not comp.get("id"):
                errors.append(f"Component at index {idx} missing required field 'id'")
            if "type" not in comp or not comp.get("type"):
                errors.append(f"Component '{comp.get('id', idx)}' missing required field 'type'")

            # Validate provides structure if present
            provides = comp.get("provides", [])
            if provides is None:
                # Allows explicit null but warns
                errors.append(f"Component '{comp.get('id', idx)}' has null 'provides'; expected list")
                continue
            if not isinstance(provides, list):
                errors.append(f"Component '{comp.get('id', idx)}' 'provides' must be a list")
                continue

            for p_idx, pr in enumerate(provides):
                if not isinstance(pr, dict):
                    errors.append(
                        f"Component '{comp.get('id', idx)}' provides[{p_idx}] must be a dictionary"
                    )
                    continue
                if "useAs" not in pr or not pr.get("useAs"):
                    errors.append(
                        f"Component '{comp.get('id', idx)}' provides[{p_idx}] missing required field 'useAs'"
                    )
                if "in" not in pr or not pr.get("in"):
                    errors.append(
                        f"Component '{comp.get('id', idx)}' provides[{p_idx}] missing required field 'in'"
                    )

        return errors

    async def validate(self, yaml_content: str) -> List[str]:
        """Run full provides validation. Returns list of error messages (empty if valid)."""
        errors: List[str] = []

        # Parse YAML
        try:
            spec_dict = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            return [f"YAML parsing error: {str(e)}"]

        if not isinstance(spec_dict, dict) or not spec_dict:
            return ["Empty or invalid YAML content"]

        # Structural validation
        struct_errors = await self._validate_yaml_structure(spec_dict)
        if struct_errors:
            errors.extend(struct_errors)

        # If structure invalid, no need to proceed further
        if errors:
            return errors

        # Load component catalog, preferring existing cache from the shared resolver
        try:
            if not self.resolver.get_cached_components():
                await self.resolver.fetch_all_components()
        except Exception as e:
            logger.error(f"Failed to load component catalog: {e}")
            return [f"Failed to load component catalog: {str(e)}"]

        components = spec_dict.get("components", [])
        comp_by_id: Dict[str, Dict[str, Any]] = {c.get("id"): c for c in components if isinstance(c, dict)}

        # Validate that all components exist in catalog by type
        for comp in components:
            comp_type = comp.get("type")
            if not self.resolver.find_component(comp_type):
                errors.append(
                    f"Component '{comp.get('id', 'unknown')}' (type: '{comp_type}') not found in catalog"
                )

        # Early return if we already have missing components
        if errors:
            return errors

        # Import the inspector lazily to avoid heavy import on app start
        try:
            from langflow.services.spec.component_schema_inspector import ComponentSchemaInspector
            inspector = ComponentSchemaInspector()
        except Exception as e:
            logger.error(f"Failed to initialize ComponentSchemaInspector: {e}")
            return ["Internal validator setup error"]

        # Build helper: class name per component (based on YAML type)
        def get_class_name_from_yaml_type(yaml_type: str) -> str:
            # The YAML 'type' is already the class name for most components
            return yaml_type

        # Preliminary check: disallow asTools when template does not support tool-mode
        for comp in components:
            comp_id = comp.get("id", "unknown")
            comp_type = comp.get("type", "")
            comp_class = get_class_name_from_yaml_type(comp_type)
            try:
                supports_tools = self._template_supports_tool_mode(comp_class)
            except Exception:
                supports_tools = False
            if bool(comp.get("asTools", False)) and not supports_tools:
                errors.append(
                    (
                        f"Component '{comp_id}' declares asTools: true but its catalog template has no items "
                        f"with tool_mode: true (component class: '{comp_class}')."
                    )
                )

        # Additional rule: if a component is declared as a tool (asTools: true),
        # all its provides connections must use useAs: 'tools'. Mixing non-tool useAs
        # is disallowed to avoid ambiguous semantics.
        for comp in components:
            comp_id = comp.get("id", "unknown")
            if bool(comp.get("asTools", False)):
                provides_list = comp.get("provides", []) or []
                for pr in provides_list:
                    if isinstance(pr, dict):
                        pr_use_as = pr.get("useAs")
                        pr_target = pr.get("in")
                        if pr_use_as and pr_use_as != "tools":
                            errors.append(
                                (
                                    f"Component '{comp_id}' is declared as a tool (asTools: true) but declares a "
                                    f"connection to '{pr_target}' using useAs: '{pr_use_as}'. Components declared as tools "
                                    f"must only use useAs: 'tools'."
                                )
                            )

        # Validate provides connections
        for comp in components:
            source_id = comp.get("id", "unknown")
            source_type = comp.get("type", "")
            source_class = get_class_name_from_yaml_type(source_type)

            provides_list = comp.get("provides", [])
            for pr in provides_list:
                target_id = pr.get("in")
                use_as = pr.get("useAs")

                # If connection declares tools usage, enforce template-based support and declaration
                if use_as == "tools":
                    # First: component must support tool-mode via template
                    if not self._template_supports_tool_mode(source_class):
                        errors.append(
                            (
                                f"Component '{source_id}' ({source_class}) does not support tool mode via template: "
                                f"no template items with tool_mode: true; cannot use 'useAs: tools' to '{target_id}'."
                            )
                        )
                        continue

                    # Second: require explicit asTools: true declaration
                    source_is_tools = bool(comp.get("asTools", False))
                    if not source_is_tools:
                        errors.append(
                            (
                                f"Component '{source_id}' supports tool mode via template but is not declared as a tool "
                                f"(missing asTools: true); cannot use 'useAs: tools' to '{target_id}'."
                            )
                        )
                        continue

                # Target existence by id
                if target_id not in comp_by_id:
                    errors.append(
                        f"Component '{source_id}' provides to unknown target id '{target_id}'"
                    )
                    continue

                target_comp = comp_by_id[target_id]
                target_type = target_comp.get("type", "")
                target_class = get_class_name_from_yaml_type(target_type)

                # Check that inspector knows both classes
                if inspector.get_component_schema(source_class) is None:
                    errors.append(
                        f"Source component class '{source_class}' not recognized in Langflow"
                    )
                    continue
                if inspector.get_component_schema(target_class) is None:
                    errors.append(
                        f"Target component class '{target_class}' not recognized in Langflow"
                    )
                    continue

                # Determine default fields via IO mapping
                io_map = inspector.get_component_io_mapping()
                src_map = io_map.get(source_class)
                tgt_map = io_map.get(target_class)

                # Fallbacks
                source_output = (src_map or {}).get("output_field") or "output"
                target_input = (tgt_map or {}).get("input_field") or "input_value"

                # Adjust fields based on useAs semantics and tool_mode flags
                if use_as == "tools":
                    # Target agents should receive tools on the 'tools' input
                    target_input = "tools"
                    # Do not rely on outputs for tool-mode validation; keep default source output
                elif use_as == "system_prompt":
                    # Prefer explicit system prompt inputs if available
                    preferred_input = self._preferred_system_prompt_input(target_class)
                    if isinstance(preferred_input, str) and preferred_input:
                        target_input = preferred_input

                # Verify chosen fields exist on source/target; if not, keep fallbacks
                source_schema = inspector.get_component_schema(source_class)
                target_schema = inspector.get_component_schema(target_class)
                try:
                    src_outputs = {out.get("name") for out in (source_schema.outputs if source_schema else [])}
                    tgt_inputs = {inp.get("name") for inp in (target_schema.inputs if target_schema else [])}
                    if source_output not in src_outputs:
                        source_output = (src_map or {}).get("output_field") or "output"
                    # For tool connections, require explicit 'tools' input on target; do not fallback
                    if use_as == "tools":
                        if "tools" not in tgt_inputs:
                            errors.append(
                                f"Target '{target_id}' ({target_class}) does not expose a 'tools' input to receive tools"
                            )
                            continue
                        # Keep target_input as 'tools' if present
                    else:
                        # For other useAs types, if chosen input is missing, fallback to default input
                        if target_input not in tgt_inputs:
                            target_input = (tgt_map or {}).get("input_field") or "input_value"
                except Exception:
                    # On any introspection error, retain original fallbacks
                    source_output = (src_map or {}).get("output_field") or source_output
                    target_input = (tgt_map or {}).get("input_field") or target_input

                # Additional semantic checks based on useAs (prioritize specific messages)
                if use_as == "system_prompt":
                    # Expect str input or a dedicated 'system_message' input field on target
                    target_schema = inspector.get_component_schema(target_class)
                    target_inputs = {i.get("name") for i in (target_schema.inputs if target_schema else [])}
                    target_types = set((target_schema.input_types if target_schema else []))
                    # Accept both common field names: 'system_message' (models) and 'system_prompt' (agents)
                    if (
                        "str" not in target_types
                        and "system_message" not in target_inputs
                        and "system_prompt" not in target_inputs
                    ):
                        errors.append(
                            f"Target '{target_id}' ({target_class}) does not accept system prompts"
                        )
                        continue
                elif use_as == "tools":
                    # Tools should generally connect into agents; enforce agent-like target
                    target_schema = inspector.get_component_schema(target_class)
                    class_name = (target_schema.class_name if target_schema else "").lower()
                    module_path = (target_schema.module_path if target_schema else "").lower()
                    if "agent" not in class_name and "agents" not in module_path:
                        errors.append(
                            f"Target '{target_id}' ({target_class}) is not an agent and cannot receive tools"
                        )
                        continue
                elif use_as == "input":
                    # Generic input should be accepted; minimal check is that target has any inputs
                    target_schema = inspector.get_component_schema(target_class)
                    if not target_schema or not target_schema.inputs:
                        errors.append(
                            f"Target '{target_id}' ({target_class}) cannot accept inputs"
                        )
                        continue

                # Validate I/O field existence and type compatibility
                result = inspector.validate_component_connection(
                    source_comp=source_class,
                    target_comp=target_class,
                    source_output=source_output,
                    target_input=target_input,
                )

                if not result.get("valid"):
                    # Enhance error based on useAs for better messaging
                    base_error = result.get("error") or "Invalid connection"
                    errors.append(
                        f"Invalid provides connection: {source_id} ({source_class}) → {target_id} ({target_class})"
                        f" as '{use_as}': {base_error}"
                    )
                    continue

        return errors


async def validate_provides_validator(request_model: ValidateSpecRequest = Body(...)) -> ValidateSpecRequest:
    """FastAPI dependency to validate 'provides' connections before handler.

    Args:
        request_model: Pydantic model with `yaml_content` field (e.g., ValidateSpecRequest)

    Raises:
        HTTPException(400): If any validation error is found
    """
    try:
        yaml_content = getattr(request_model, "yaml_content", None)
        if yaml_content is None:
            raise HTTPException(status_code=400, detail={"errors": ["Missing 'yaml_content' in request body"]})

        resolver = ComponentResolver()
        validator = ProvidesConnectionValidator(resolver)
        errors = await validator.validate(yaml_content)

        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})

        return request_model

    except HTTPException:
        # Propagate HTTP 400 raised above
        raise
    except Exception as e:
        logger.error(f"Provides validation error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail={"errors": [f"Validation error: {str(e)}"]})