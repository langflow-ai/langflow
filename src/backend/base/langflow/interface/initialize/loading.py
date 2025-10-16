from __future__ import annotations

# Re-export everything from lfx.interface.initialize.loading for backwards compatibility
from lfx.interface.initialize.loading import (
    build_component,
    build_custom_component,
    convert_kwargs,
    convert_params_to_sets,
    get_instance_results,
    get_params,
    instantiate_class,
    update_params_with_load_from_db_fields,
    update_table_params_with_load_from_db_fields,
)

# Make re-exported functions available at module level
__all__ = [
    "build_component",
    "build_custom_component",
    "convert_kwargs",
    "convert_params_to_sets",
    "get_instance_results",
    "get_params",
    "instantiate_class",
    "update_params_with_load_from_db_fields",
    "update_table_params_with_load_from_db_fields",
]
