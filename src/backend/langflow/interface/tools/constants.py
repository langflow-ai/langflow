from langchain.agents import Tool
from langchain.agents.load_tools import get_all_tool_names
from langchain.tools.json.tool import JsonSpec

from langflow.interface.custom.types import PythonFunction

FILE_TOOLS = {"JsonSpec": JsonSpec}
CUSTOM_TOOLS = {"Tool": Tool, "PythonFunction": PythonFunction}
ALL_TOOLS_NAMES = set(
    get_all_tool_names() + list(CUSTOM_TOOLS.keys()) + list(FILE_TOOLS.keys())
)
