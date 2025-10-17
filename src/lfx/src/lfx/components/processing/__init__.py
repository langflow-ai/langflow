"""Processing components for LangFlow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.processing.alter_metadata import AlterMetadataComponent
    from lfx.components.processing.batch_run import BatchRunComponent
    from lfx.components.processing.combine_text import CombineTextComponent
    from lfx.components.processing.converter import TypeConverterComponent
    from lfx.components.processing.create_data import CreateDataComponent
    from lfx.components.processing.data_operations import DataOperationsComponent
    from lfx.components.processing.data_to_dataframe import DataToDataFrameComponent
    from lfx.components.processing.dataframe_operations import DataFrameOperationsComponent
    from lfx.components.processing.dataframe_to_toolset import DataFrameToToolsetComponent
    from lfx.components.processing.dynamic_create_data import DynamicCreateDataComponent
    from lfx.components.processing.extract_key import ExtractDataKeyComponent
    from lfx.components.processing.filter_data import FilterDataComponent
    from lfx.components.processing.filter_data_values import DataFilterComponent
    from lfx.components.processing.json_cleaner import JSONCleaner
    from lfx.components.processing.lambda_filter import LambdaFilterComponent
    from lfx.components.processing.llm_router import LLMRouterComponent
    from lfx.components.processing.merge_data import MergeDataComponent
    from lfx.components.processing.message_to_data import MessageToDataComponent
    from lfx.components.processing.parse_data import ParseDataComponent
    from lfx.components.processing.parse_dataframe import ParseDataFrameComponent
    from lfx.components.processing.parse_json_data import ParseJSONDataComponent
    from lfx.components.processing.parser import ParserComponent
    from lfx.components.processing.prompt import PromptComponent
    from lfx.components.processing.python_repl_core import PythonREPLComponent
    from lfx.components.processing.regex import RegexExtractorComponent
    from lfx.components.processing.select_data import SelectDataComponent
    from lfx.components.processing.split_text import SplitTextComponent
    from lfx.components.processing.structured_output import StructuredOutputComponent
    from lfx.components.processing.update_data import UpdateDataComponent

_dynamic_imports = {
    "AlterMetadataComponent": "alter_metadata",
    "BatchRunComponent": "batch_run",
    "CombineTextComponent": "combine_text",
    "TypeConverterComponent": "converter",
    "CreateDataComponent": "create_data",
    "DataOperationsComponent": "data_operations",
    "DataToDataFrameComponent": "data_to_dataframe",
    "DataFrameOperationsComponent": "dataframe_operations",
    "DataFrameToToolsetComponent": "dataframe_to_toolset",
    "DynamicCreateDataComponent": "dynamic_create_data",
    "ExtractDataKeyComponent": "extract_key",
    "FilterDataComponent": "filter_data",
    "DataFilterComponent": "filter_data_values",
    "JSONCleaner": "json_cleaner",
    "LambdaFilterComponent": "lambda_filter",
    "LLMRouterComponent": "llm_router",
    "MergeDataComponent": "merge_data",
    "MessageToDataComponent": "message_to_data",
    "ParseDataComponent": "parse_data",
    "ParseDataFrameComponent": "parse_dataframe",
    "ParseJSONDataComponent": "parse_json_data",
    "ParserComponent": "parser",
    "PromptComponent": "prompt",
    "PythonREPLComponent": "python_repl_core",
    "RegexExtractorComponent": "regex",
    "SelectDataComponent": "select_data",
    "SplitTextComponent": "split_text",
    "StructuredOutputComponent": "structured_output",
    "UpdateDataComponent": "update_data",
}

__all__ = [
    "AlterMetadataComponent",
    "BatchRunComponent",
    "CombineTextComponent",
    "CreateDataComponent",
    "DataFilterComponent",
    "DataFrameOperationsComponent",
    "DataFrameToToolsetComponent",
    "DataOperationsComponent",
    "DataToDataFrameComponent",
    "DynamicCreateDataComponent",
    "ExtractDataKeyComponent",
    "FilterDataComponent",
    "JSONCleaner",
    "LLMRouterComponent",
    "LambdaFilterComponent",
    "MergeDataComponent",
    "MessageToDataComponent",
    "ParseDataComponent",
    "ParseDataFrameComponent",
    "ParseJSONDataComponent",
    "ParserComponent",
    "PromptComponent",
    "PythonREPLComponent",
    "RegexExtractorComponent",
    "SelectDataComponent",
    "SplitTextComponent",
    "StructuredOutputComponent",
    "TypeConverterComponent",
    "UpdateDataComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import processing components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
