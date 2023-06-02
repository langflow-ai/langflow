from langchain import tools
from langchain.agents import Tool
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)
from langchain.tools.json.tool import JsonSpec

from langflow.interface.importing.utils import import_class
from langflow.interface.tools.custom import PythonFunctionTool

FILE_TOOLS = {"JsonSpec": JsonSpec}
CUSTOM_TOOLS = {"Tool": Tool, "PythonFunctionTool": PythonFunctionTool}

OTHER_TOOLS = {tool: import_class(f"langchain.tools.{tool}") for tool in tools.__all__}

ALL_TOOLS_NAMES = {
    **_BASE_TOOLS,
    **_LLM_TOOLS,  # type: ignore
    **{k: v[0] for k, v in _EXTRA_LLM_TOOLS.items()},  # type: ignore
    **{k: v[0] for k, v in _EXTRA_OPTIONAL_TOOLS.items()},
    **CUSTOM_TOOLS,
    **FILE_TOOLS,  # type: ignore
    **OTHER_TOOLS,
}
