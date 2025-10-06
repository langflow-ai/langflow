"""Helpers module for the lfx package.

This module automatically chooses between the full langflow implementation
(when available) and the lfx implementation (when standalone).
"""

from lfx.utils.langflow_utils import has_langflow_memory

# Import the appropriate implementation
if has_langflow_memory():
    try:
        # Import full langflow implementation
        from langflow.helpers.flow import (
            build_schema_from_inputs,
            get_arg_names,
            get_flow_inputs,
            list_flows,
            load_flow,
            run_flow,
        )
    except (ImportError, ModuleNotFoundError):
        # Fallback to lfx implementation if langflow import fails
        from lfx.helpers.flow import (
            build_schema_from_inputs,
            get_arg_names,
            get_flow_inputs,
            list_flows,
            load_flow,
            run_flow,
        )
else:
    # Use lfx implementation
    from lfx.helpers.flow import (
        build_schema_from_inputs,
        get_arg_names,
        get_flow_inputs,
        list_flows,
        load_flow,
        run_flow,
    )

# Export the available functions
__all__ = ["build_schema_from_inputs", "get_arg_names", "get_flow_inputs", "list_flows", "load_flow", "run_flow"]
