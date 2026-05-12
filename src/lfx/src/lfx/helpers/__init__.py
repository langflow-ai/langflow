"""Helpers module for the lfx package.

This module automatically chooses between the full langflow implementation
(when available) and the lfx implementation (when standalone).

Imports are deferred until first access to avoid loading heavy dependencies
(pandas, torch, database models) at package import time.
"""

from __future__ import annotations

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
    "get_flow_by_id_or_name",
    "get_flow_inputs",
    "list_flows",
    "list_flows_by_flow_folder",
    "list_flows_by_folder_id",
    "load_flow",
    "run_flow",
    "safe_convert",
]

# Maps each export to (langflow_module, lfx_module)
_SOURCE: dict[str, tuple[str, str]] = {
    "BaseModel": ("langflow.helpers.base_model", "lfx.helpers.base_model"),
    "SchemaField": ("langflow.helpers.base_model", "lfx.helpers.base_model"),
    "build_model_from_schema": ("langflow.helpers.base_model", "lfx.helpers.base_model"),
    "coalesce_bool": ("langflow.helpers.base_model", "lfx.helpers.base_model"),
    "format_type": ("langflow.helpers.custom", "lfx.helpers.custom"),
    "clean_string": ("langflow.helpers.data", "lfx.helpers.data"),
    "data_to_text": ("langflow.helpers.data", "lfx.helpers.data"),
    "data_to_text_list": ("langflow.helpers.data", "lfx.helpers.data"),
    "docs_to_data": ("langflow.helpers.data", "lfx.helpers.data"),
    "safe_convert": ("langflow.helpers.data", "lfx.helpers.data"),
    "build_schema_from_inputs": ("langflow.helpers.flow", "lfx.helpers.flow"),
    "get_arg_names": ("langflow.helpers.flow", "lfx.helpers.flow"),
    "get_flow_by_id_or_name": ("langflow.helpers.flow", "lfx.helpers.flow"),
    "get_flow_inputs": ("langflow.helpers.flow", "lfx.helpers.flow"),
    "list_flows": ("langflow.helpers.flow", "lfx.helpers.flow"),
    "list_flows_by_flow_folder": ("langflow.helpers.flow", "lfx.helpers.flow"),
    "list_flows_by_folder_id": ("langflow.helpers.flow", "lfx.helpers.flow"),
    "load_flow": ("langflow.helpers.flow", "lfx.helpers.flow"),
    "run_flow": ("langflow.helpers.flow", "lfx.helpers.flow"),
}

_EXPORTS = frozenset(__all__)


def __getattr__(name: str):
    if name not in _EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    import importlib

    from lfx.utils.langflow_utils import has_langflow_memory

    langflow_mod, lfx_mod = _SOURCE[name]

    if has_langflow_memory():
        try:
            mod = importlib.import_module(langflow_mod)
            val = getattr(mod, name)
        except (ImportError, AttributeError):
            pass
        else:
            globals()[name] = val
            return val

    mod = importlib.import_module(lfx_mod)
    val = getattr(mod, name)
    globals()[name] = val
    return val
