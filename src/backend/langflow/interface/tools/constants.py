from langchain.agents import Tool
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)
from langchain.tools.bing_search.tool import BingSearchRun
from langchain.tools.google_search.tool import GoogleSearchResults, GoogleSearchRun
from langchain.tools.json.tool import JsonGetValueTool, JsonListKeysTool, JsonSpec
from langchain.tools.python.tool import PythonAstREPLTool, PythonREPLTool
from langchain.tools.requests.tool import (
    RequestsDeleteTool,
    RequestsGetTool,
    RequestsPatchTool,
    RequestsPostTool,
    RequestsPutTool,
)
from langchain.tools.sql_database.tool import (
    InfoSQLDatabaseTool,
    ListSQLDatabaseTool,
    QueryCheckerTool,
    QuerySQLDataBaseTool,
)
from langchain.tools.wikipedia.tool import WikipediaQueryRun
from langchain.tools.wolfram_alpha.tool import WolframAlphaQueryRun

from langflow.interface.tools.custom import PythonFunction

FILE_TOOLS = {"JsonSpec": JsonSpec}
CUSTOM_TOOLS = {"Tool": Tool, "PythonFunction": PythonFunction}
OTHER_TOOLS = {
    "QuerySQLDataBaseTool": QuerySQLDataBaseTool,
    "InfoSQLDatabaseTool": InfoSQLDatabaseTool,
    "ListSQLDatabaseTool": ListSQLDatabaseTool,
    "QueryCheckerTool": QueryCheckerTool,
    "BingSearchRun": BingSearchRun,
    "GoogleSearchRun": GoogleSearchRun,
    "GoogleSearchResults": GoogleSearchResults,
    "JsonListKeysTool": JsonListKeysTool,
    "JsonGetValueTool": JsonGetValueTool,
    "PythonREPLTool": PythonREPLTool,
    "PythonAstREPLTool": PythonAstREPLTool,
    "RequestsGetTool": RequestsGetTool,
    "RequestsPostTool": RequestsPostTool,
    "RequestsPatchTool": RequestsPatchTool,
    "RequestsPutTool": RequestsPutTool,
    "RequestsDeleteTool": RequestsDeleteTool,
    "WikipediaQueryRun": WikipediaQueryRun,
    "WolframAlphaQueryRun": WolframAlphaQueryRun,
}
ALL_TOOLS_NAMES = {
    **_BASE_TOOLS,
    **_LLM_TOOLS,  # type: ignore
    **{k: v[0] for k, v in _EXTRA_LLM_TOOLS.items()},  # type: ignore
    **{k: v[0] for k, v in _EXTRA_OPTIONAL_TOOLS.items()},
    **CUSTOM_TOOLS,
    **FILE_TOOLS,  # type: ignore
    **OTHER_TOOLS,
}
