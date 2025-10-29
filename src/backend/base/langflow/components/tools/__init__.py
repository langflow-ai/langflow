from .split_to_images import SplitToImagesComponent

# Import other tools with error handling
try:
    from .calculator import CalculatorToolComponent
except ImportError:
    CalculatorToolComponent = None

try:
    from .python_code_structured_tool import PythonCodeStructuredTool
except ImportError:
    PythonCodeStructuredTool = None

try:
    from .python_repl import PythonREPLToolComponent
except ImportError:
    PythonREPLToolComponent = None

try:
    from .search_api import SearchAPIComponent
except ImportError:
    SearchAPIComponent = None

try:
    from .searxng import SearXNGToolComponent
except ImportError:
    SearXNGToolComponent = None

try:
    from .serp_api import SerpAPIComponent
except ImportError:
    SerpAPIComponent = None

try:
    from .tavily_search_tool import TavilySearchToolComponent
except ImportError:
    TavilySearchToolComponent = None

try:
    from .wikidata_api import WikidataAPIComponent
except ImportError:
    WikidataAPIComponent = None

try:
    from .wikipedia_api import WikipediaAPIComponent
except ImportError:
    WikipediaAPIComponent = None

try:
    from .yahoo_finance import YfinanceToolComponent
except ImportError:
    YfinanceToolComponent = None

# Only include components that imported successfully
__all__ = [
    name for name in [
        "CalculatorToolComponent",
        "PythonCodeStructuredTool",
        "PythonREPLToolComponent",
        "SearchAPIComponent",
        "SearXNGToolComponent",
        "SerpAPIComponent",
        "SplitToImagesComponent",
        "TavilySearchToolComponent",
        "WikidataAPIComponent",
        "WikipediaAPIComponent",
        "YfinanceToolComponent",
    ] if globals().get(name) is not None
]