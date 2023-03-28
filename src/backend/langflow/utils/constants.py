from langchain.agents import Tool
from langflow.interface.custom_types import PythonFunction
from langchain.agents.load_tools import get_all_tool_names

OPENAI_MODELS = [
    "text-davinci-003",
    "text-davinci-002",
    "text-curie-001",
    "text-babbage-001",
    "text-ada-001",
]
CHAT_OPENAI_MODELS = ["gpt-3.5-turbo", "gpt-4", "gpt-4-32k"]

CUSTOM_TOOLS = {"Tool": Tool, "PythonFunction": PythonFunction}

DEFAULT_PYTHON_FUNCTION = """
def python_function(text: str) -> str:
    return text
"""

ALL_TOOLS_NAMES = set(get_all_tool_names() + list(CUSTOM_TOOLS.keys()))
