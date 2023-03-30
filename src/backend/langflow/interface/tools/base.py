from langflow.custom import customs
from langflow.interface.listing import ALL_TOOLS_NAMES, CUSTOM_TOOLS
from langflow.template.template import Field, Template
from langflow.utils import util
from langflow.settings import settings
from langflow.interface.base import LangChainTypeCreator
from typing import Dict, List
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)


class ToolCreator(LangChainTypeCreator):
    type_name: str = "tools"

    @property
    def type_to_loader_dict(self) -> Dict:
        return ALL_TOOLS_NAMES

    def get_signature(self, name: str) -> Dict | None:
        """Get the signature of a tool."""

        NODE_INPUTS = ["llm", "func"]
        base_classes = ["Tool"]
        all_tools = {}
        for tool in ALL_TOOLS_NAMES:
            if tool_params := util.get_tool_params(util.get_tool_by_name(tool)):
                tool_name = tool_params.get("name") or str(tool)
                all_tools[tool_name] = {"type": tool, "params": tool_params}

        # Raise error if name is not in tools
        if name not in all_tools.keys():
            raise ValueError("Tool not found")

        type_dict = {
            "str": Field(
                field_type="str",
                required=True,
                is_list=False,
                show=True,
                placeholder="",
                value="",
            ),
            "llm": Field(field_type="BaseLLM", required=True, is_list=False, show=True),
            "func": Field(
                field_type="function",
                required=True,
                is_list=False,
                show=True,
                multiline=True,
            ),
            "code": Field(
                field_type="str",
                required=True,
                is_list=False,
                show=True,
                value="",
                multiline=True,
            ),
        }

        tool_type: str = all_tools[name]["type"]  # type: ignore

        if tool_type in _BASE_TOOLS:
            params = []
        elif tool_type in _LLM_TOOLS:
            params = ["llm"]
        elif tool_type in _EXTRA_LLM_TOOLS:
            _, extra_keys = _EXTRA_LLM_TOOLS[tool_type]
            params = ["llm"] + extra_keys
        elif tool_type in _EXTRA_OPTIONAL_TOOLS:
            _, extra_keys = _EXTRA_OPTIONAL_TOOLS[tool_type]
            params = extra_keys
        elif tool_type == "Tool":
            params = ["name", "description", "func"]
        elif tool_type in CUSTOM_TOOLS:
            # Get custom tool params
            params = all_tools[name]["params"]  # type: ignore
            base_classes = ["function"]
            if node := customs.get_custom_nodes("tools").get(tool_type):
                return node

        else:
            params = []

        # Copy the field and add the name
        fields = []
        for param in params:
            if param in NODE_INPUTS:
                field = type_dict[param].copy()
            else:
                field = type_dict["str"].copy()
            field.name = param
            if param == "aiosession":
                field.show = False
                field.required = False
            fields.append(field)

        template = Template(fields=fields, type_name=tool_type)

        tool_params = util.get_tool_params(util.get_tool_by_name(tool_type))
        if tool_params is None:
            tool_params = {}
        return {
            "template": util.format_dict(template.to_dict()),
            **tool_params,
            "base_classes": base_classes,
        }

    def to_list(self) -> List[str]:
        """List all load tools"""

        tools = []

        for tool in ALL_TOOLS_NAMES:
            tool_params = util.get_tool_params(util.get_tool_by_name(tool))
            if tool_params and (
                tool_params.get("name") in settings.tools
                or (tool_params.get("name") and settings.dev)
            ):
                tools.append(tool_params["name"])

        # Add Tool
        custom_tools = customs.get_custom_nodes("tools")
        return tools + list(custom_tools.keys())
