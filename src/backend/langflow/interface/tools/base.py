from typing import Dict, List, Optional

from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)

from langflow.custom import customs
from langflow.interface.base import LangChainTypeCreator
from langflow.interface.tools.constants import (
    CUSTOM_TOOLS,
    FILE_TOOLS,
)
from langflow.interface.tools.util import (
    get_tool_by_name,
    get_tool_params,
    get_tools_dict,
)
from langflow.settings import settings
from langflow.template.base import Template, TemplateField
from langflow.utils import util

TOOL_INPUTS = {
    "str": TemplateField(
        field_type="str",
        required=True,
        is_list=False,
        show=True,
        placeholder="",
        value="",
    ),
    "llm": TemplateField(field_type="BaseLLM", required=True, is_list=False, show=True),
    "func": TemplateField(
        field_type="function",
        required=True,
        is_list=False,
        show=True,
        multiline=True,
    ),
    "code": TemplateField(
        field_type="str",
        required=True,
        is_list=False,
        show=True,
        value="",
        multiline=True,
    ),
    "dict_": TemplateField(
        field_type="file",
        required=True,
        is_list=False,
        show=True,
        value="",
    ),
}


class ToolCreator(LangChainTypeCreator):
    type_name: str = "tools"
    tools_dict: Optional[Dict] = None

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.tools_dict is None:
            self.tools_dict = get_tools_dict()
        return self.tools_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of a tool."""

        base_classes = ["Tool"]
        all_tools = {}
        for tool in self.type_to_loader_dict.keys():
            if tool_params := get_tool_params(get_tool_by_name(tool)):
                tool_name = tool_params.get("name") or str(tool)
                all_tools[tool_name] = {"type": tool, "params": tool_params}

        # Raise error if name is not in tools
        if name not in all_tools.keys():
            raise ValueError("Tool not found")

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
        elif tool_type in FILE_TOOLS:
            params = all_tools[name]["params"]  # type: ignore
            base_classes += [name]

        else:
            params = []

        # Copy the field and add the name
        fields = []
        for param in params:
            field = TOOL_INPUTS.get(param, TOOL_INPUTS["str"]).copy()
            field.name = param
            if param == "aiosession":
                field.show = False
                field.required = False
            fields.append(field)

        template = Template(fields=fields, type_name=tool_type)

        tool_params = all_tools[name]["params"]
        return {
            "template": util.format_dict(template.to_dict()),
            **tool_params,
            "base_classes": base_classes,
        }

    def to_list(self) -> List[str]:
        """List all load tools"""

        tools = []

        for tool, fcn in get_tools_dict().items():
            tool_params = get_tool_params(fcn)

            if tool_params and not tool_params.get("name"):
                tool_params["name"] = tool

            if tool_params and (
                tool_params.get("name") in settings.tools
                or (tool_params.get("name") and settings.dev)
            ):
                tools.append(tool_params["name"])

        return tools


tool_creator = ToolCreator()
