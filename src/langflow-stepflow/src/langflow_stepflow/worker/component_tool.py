"""Component for creating tool wrappers from Langflow components."""

from typing import Any

from stepflow_py.worker import StepflowContext


async def _resolve_step_references(inputs: dict[str, Any], context: StepflowContext) -> dict[str, Any]:
    """Resolve any step references in inputs to actual values.

    Args:
        inputs: Input dictionary that may contain step references
        context: StepflowContext to resolve references

    Returns:
        Dictionary with step references resolved to actual values
    """
    resolved = {}

    # TODO: Implement proper step reference resolution
    # For now, we'll need to identify step references and resolve them
    # This is complex because we need to understand the Value API
    for key, value in inputs.items():
        if hasattr(value, "__dict__") and hasattr(value, "step_id"):
            # This looks like a step reference - for now just store a placeholder
            # In a real implementation, we'd need to resolve this through context
            resolved[key] = f"<resolved:{getattr(value, 'step_id', 'unknown')}>"
        else:
            # Regular value, keep as-is
            resolved[key] = value

    return resolved


async def component_tool_executor(input_data: dict[str, Any], context: StepflowContext) -> dict[str, Any]:
    """Create a tool wrapper from Langflow component code and inputs.

    This component takes a Langflow component's code/JSON and static inputs,
    then creates a serializable tool wrapper that can be used by agents.

    Args:
        input_data: Contains:
            - code: Component JSON/code blob
            - inputs: Static input values to apply to component
            - component_type: Type of the component
            - session_id: Session ID for the workflow execution

    Returns:
        Tool wrapper dict with component code, static inputs, tool metadata, and
        session_id
    """
    try:
        component_code = input_data.get("code", {})
        static_inputs = input_data.get("inputs", {})
        component_type = input_data.get("component_type", "unknown")
        session_id = input_data.get("session_id", "default_session")

        # Store component code as a blob and get the ID
        code_blob_id = await context.put_blob(component_code)

        # Resolve any step references in static_inputs to actual values
        resolved_inputs = await _resolve_step_references(static_inputs, context)

        # Extract tool metadata from component template
        tool_metadata = _extract_tool_metadata(component_code)

        # Extract tool input schema from component template
        tool_input_schema = _extract_tool_input_schema(component_code)

        # Create tool wrapper - now includes session_id for proper message tracking
        tool_wrapper = {
            "__tool_wrapper__": True,
            "code_blob_id": code_blob_id,  # Store blob ID instead of full code
            "static_inputs": resolved_inputs,  # Store resolved values
            "component_type": component_type,
            "tool_metadata": tool_metadata,
            "tool_input_schema": tool_input_schema,
            "session_id": session_id,  # Store session ID for component execution
        }

        # Return in the same format as UDF executor - wrapped in "result" field
        return {"result": tool_wrapper}

    except Exception as e:
        return {
            "error": f"Failed to create tool wrapper: {str(e)}",
            "component_type": input_data.get("component_type", "unknown"),
        }


def _extract_tool_metadata(component_code: dict[str, Any]) -> dict[str, Any]:
    """Extract tool metadata from component's tools_metadata field.

    Args:
        component_code: Component JSON containing template and tools_metadata

    Returns:
        Dict with tool name, description, and other metadata
    """
    try:
        template = component_code.get("template", {})
        tools_metadata = template.get("tools_metadata", {}).get("value", [])

        if tools_metadata and len(tools_metadata) > 0:
            # Use first tool metadata entry
            tool_meta = tools_metadata[0]
            return {
                "name": tool_meta.get("name", "unknown_tool"),
                "description": tool_meta.get("description", ""),
                "display_name": tool_meta.get("display_name", ""),
                "display_description": tool_meta.get("display_description", ""),
            }
        else:
            # Fallback to component info if no tools_metadata
            return {
                "name": component_code.get("display_name", "unknown_tool"),
                "description": component_code.get("description", ""),
                "display_name": component_code.get("display_name", ""),
                "display_description": component_code.get("description", ""),
            }

    except Exception:
        return {
            "name": "unknown_tool",
            "description": "",
            "display_name": "Unknown Tool",
            "display_description": "",
        }


def _extract_tool_input_schema(component_code: dict[str, Any]) -> dict[str, Any]:
    """Extract tool input schema from component template fields with tool_mode=True.

    Args:
        component_code: Component JSON containing template

    Returns:
        JSONSchema-style dict describing tool input parameters
    """
    try:
        template = component_code.get("template", {})
        properties = {}
        required = []

        # Find fields with tool_mode=True
        for field_name, field_data in template.items():
            if isinstance(field_data, dict) and field_data.get("tool_mode", False):
                # This field should be exposed as a tool parameter
                field_type = field_data.get("type", "str")
                field_info = field_data.get("info", "")
                field_required = field_data.get("required", False)
                default_value = field_data.get("value", "")

                # Convert to JSON Schema format
                properties[field_name] = {
                    "type": _map_langflow_type_to_json_schema(field_type),
                    "description": field_info,
                    "default": default_value,
                }

                if field_required:
                    required.append(field_name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    except Exception:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }


def _map_langflow_type_to_json_schema(langflow_type: str) -> str:
    """Map Langflow field types to JSON Schema types.

    Args:
        langflow_type: Langflow field type (e.g., "str", "int", "bool")

    Returns:
        JSON Schema type string
    """
    type_mapping = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
    }
    return type_mapping.get(langflow_type, "string")
