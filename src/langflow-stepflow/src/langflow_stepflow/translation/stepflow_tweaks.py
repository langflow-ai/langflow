"""Stepflow-level tweaks for Langflow component configuration.

This module provides utilities for applying tweaks to Stepflow workflows
that were translated from Langflow. Tweaks are applied by modifying the
input fields of Langflow UDF executor steps before execution.

Key features:
- Apply tweaks to translated Stepflow workflows at execution time
- Target UDF executor steps using original Langflow node IDs
- Modify step input fields directly (not blob data)
- Compatible with Langflow API tweak format

Note: Test utilities and environment variable integration are in
tests/helpers/tweaks_builder.py to keep this production code lean.
"""

import copy
from typing import Any


def apply_stepflow_tweaks_to_dict(
    workflow_dict: dict[str, Any],
    tweaks: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply tweaks to a Stepflow workflow dict.

    Args:
        workflow_dict: Stepflow workflow as dict (from YAML)
        tweaks: Dict mapping langflow_node_id -> {field_name: new_value}

    Returns:
        Modified workflow dict with tweaks applied

    Examples:
        >>> tweaks = {
        ...     "LanguageModelComponent-kBOja": {
        ...         "api_key": "new_test_key",
        ...         "temperature": 0.8,
        ...     }
        ... }
        >>> modified_dict = apply_stepflow_tweaks_to_dict(workflow_dict, tweaks)
    """
    if not tweaks:
        return workflow_dict

    # Deep copy to avoid mutating original
    modified_dict = copy.deepcopy(workflow_dict)

    for step_dict in modified_dict.get("steps", []):
        step_id = step_dict.get("id", "")
        component = step_dict.get("component", "")

        # Check if this is a Langflow executor step (custom_code or core)
        is_langflow_step = (
            step_id.startswith("langflow_")
            and not step_id.endswith("_blob")
            and (component == "/langflow/custom_code" or component.startswith("/langflow/core/"))
        )

        if is_langflow_step:
            # Extract Langflow node ID
            langflow_node_id = step_id[len("langflow_") :]

            if langflow_node_id in tweaks:
                # Ensure step has input section
                if "input" not in step_dict:
                    step_dict["input"] = {}
                if "input" not in step_dict["input"]:
                    step_dict["input"]["input"] = {}

                # Apply tweaks
                for field_name, new_value in tweaks[langflow_node_id].items():
                    step_dict["input"]["input"][field_name] = new_value

    return modified_dict


def convert_tweaks_to_overrides(
    tweaks: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]] | None:
    """Convert Langflow tweaks format to Stepflow overrides format.

    This function transforms tweaks from the early binding format (modifying flow)
    to the late binding format (runtime overrides). Instead of modifying the flow
    directly, we create overrides that are applied at execution time.

    Args:
        tweaks: Dict mapping langflow_node_id -> {field_name: new_value}

    Returns:
        Dict mapping step_id to merge_patch format with field overrides
        or None if no tweaks provided

    Examples:
        >>> tweaks = {
        ...     "LanguageModelComponent-kBOja": {
        ...         "api_key": "new_test_key",
        ...         "temperature": 0.8,
        ...     }
        ... }
        >>> overrides = convert_tweaks_to_overrides(tweaks)
        >>> print(overrides)
        {
            "langflow_LanguageModelComponent-kBOja": {
                "$type": "merge_patch",
                "value": {
                    "input": {
                        "api_key": "new_test_key",
                        "temperature": 0.8,
                    }
                }
            }
        }
    """
    if not tweaks:
        return None

    overrides = {}

    for langflow_node_id, field_tweaks in tweaks.items():
        # Convert Langflow node ID to Stepflow step ID format
        step_id = f"langflow_{langflow_node_id}"

        # Create the override value structure that matches step.input structure
        # We need to wrap the field tweaks in an "input.input" key to match how
        # the current tweaks modify step.input["input"][field_name]
        override_value = {"input": {"input": field_tweaks}}

        # Create the override entry with merge patch type (snake_case for API)
        overrides[step_id] = {"$type": "merge_patch", "value": override_value}

    return overrides


# Export main functions for easy importing
__all__ = [
    "apply_stepflow_tweaks_to_dict",
    "convert_tweaks_to_overrides",
]
