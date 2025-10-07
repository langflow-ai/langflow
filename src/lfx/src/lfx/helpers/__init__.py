"""Helpers module for the lfx package.

This module automatically chooses between the full langflow implementation
(when available) and the lfx implementation (when standalone).
"""

from lfx.utils.langflow_utils import has_langflow_memory

# Import the appropriate implementation
if has_langflow_memory():
    try:
        # Import full langflow implementation
        # Base Model
        from langflow.helpers.base_model import (
            BaseModel,
            SchemaField,
            build_model_from_schema,
            coalesce_bool,
        )

        # Custom
        from langflow.helpers.custom import (
            format_type,
        )

        # Data
        from langflow.helpers.data import (
            clean_string,
            data_to_text,
            data_to_text_list,
            docs_to_data,
            safe_convert,
        )

        # Flow
        from langflow.helpers.flow import (
            build_schema_from_inputs,
            get_arg_names,
            get_flow_inputs,
            list_flows,
            load_flow,
            run_flow,
        )
    except ImportError:
        # Fallback to lfx implementation if langflow import fails
        # Base Model
        from lfx.helpers.base_model import (
            BaseModel,
            SchemaField,
            build_model_from_schema,
            coalesce_bool,
        )

        # Custom
        from lfx.helpers.custom import (
            format_type,
        )

        # Data
        from lfx.helpers.data import (
            clean_string,
            data_to_text,
            data_to_text_list,
            docs_to_data,
            safe_convert,
        )

        # Flow
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
    # Base Model
    from lfx.helpers.base_model import (
        BaseModel,
        SchemaField,
        build_model_from_schema,
        coalesce_bool,
    )

    # Custom
    from lfx.helpers.custom import (
        format_type,
    )

    # Data
    from lfx.helpers.data import (
        clean_string,
        data_to_text,
        data_to_text_list,
        docs_to_data,
        safe_convert,
    )

    # Flow
    from lfx.helpers.flow import (
        build_schema_from_inputs,
        get_arg_names,
        get_flow_inputs,
        list_flows,
        load_flow,
        run_flow,
    )

# Export the available functions
__all__ = [
    "BaseModel",
    "SchemaField",
    "build_model_from_schema",
    "build_schema_from_inputs",
    "clean_string",
    "coalesce_bool",
    "data_to_text",
    "data_to_text_list",
    "docs_to_data",
    "format_type",
    "get_arg_names",
    "get_flow_inputs",
    "list_flows",
    "load_flow",
    "run_flow",
    "safe_convert",
]
