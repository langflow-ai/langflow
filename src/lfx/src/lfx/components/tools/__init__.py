from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from langchain_core._api.deprecation import LangChainDeprecationWarning

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .calculator import CalculatorToolComponent
    from .python_code_structured_tool import PythonCodeStructuredTool
    from .python_repl import PythonREPLToolComponent
    from .search_api import SearchAPIComponent
    from .searxng import SearXNGToolComponent
    from .serp_api import SerpAPIComponent
    from .tavily_search_tool import TavilySearchToolComponent
    from .wikidata_api import WikidataAPIComponent
    from .wikipedia_api import WikipediaAPIComponent
    from .yahoo_finance import YfinanceToolComponent

_dynamic_imports = {
    "CalculatorToolComponent": "calculator",
    "PythonCodeStructuredTool": "python_code_structured_tool",
    "PythonREPLToolComponent": "python_repl",
    "SearchAPIComponent": "search_api",
    "SearXNGToolComponent": "searxng",
    "SerpAPIComponent": "serp_api",
    "TavilySearchToolComponent": "tavily_search_tool",
    "WikidataAPIComponent": "wikidata_api",
    "WikipediaAPIComponent": "wikipedia_api",
    "YfinanceToolComponent": "yahoo_finance",
}

__all__ = [
    "CalculatorToolComponent",
    "PythonCodeStructuredTool",
    "PythonREPLToolComponent",
    "SearXNGToolComponent",
    "SearchAPIComponent",
    "SerpAPIComponent",
    "TavilySearchToolComponent",
    "WikidataAPIComponent",
    "WikipediaAPIComponent",
    "YfinanceToolComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import tool components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", LangChainDeprecationWarning)
            result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
