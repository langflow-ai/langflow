from langchain.agents import Tool
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)
from langchain.tools.json.tool import JsonSpec
from langchain.tools.sql_database.tool import QuerySQLDataBaseTool

from langflow.interface.tools.custom import PythonFunction

FILE_TOOLS = {"JsonSpec": JsonSpec}
CUSTOM_TOOLS = {"Tool": Tool, "PythonFunction": PythonFunction}
OTHER_TOOLS = {"QuerySQLDataBaseTool": QuerySQLDataBaseTool}
ALL_TOOLS_NAMES = {
    **_BASE_TOOLS,
    **_LLM_TOOLS,  # type: ignore
    **{k: v[0] for k, v in _EXTRA_LLM_TOOLS.items()},  # type: ignore
    **{k: v[0] for k, v in _EXTRA_OPTIONAL_TOOLS.items()},
    **CUSTOM_TOOLS,
    **FILE_TOOLS,  # type: ignore
    **OTHER_TOOLS,
}
