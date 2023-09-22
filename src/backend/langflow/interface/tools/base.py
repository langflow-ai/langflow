from typing import Dict, List, Optional

from langchain.agents.load_tools import (
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)

from langflow.custom import customs
from langflow.interface.base import LangChainTypeCreator
from langflow.interface.tools.constants import (
    ALL_TOOLS_NAMES,
    CUSTOM_TOOLS,
    FILE_TOOLS,
    OTHER_TOOLS,
)
from langflow.interface.tools.util import get_tool_params
from langflow.services.getters import get_settings_service

from langflow.template.field.base import TemplateField
from langflow.template.template.base import Template
from langflow.utils import util
from langflow.utils.util import build_template_from_class

TOOL_INPUTS = {
    "str": TemplateField(
        field_type="str",
        required=True,
        is_list=False,
        show=True,
        placeholder="",
        value="",
    ),
    "llm": TemplateField(
        field_type="BaseLanguageModel", required=True, is_list=False, show=True
    ),
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
    "path": TemplateField(
        field_type="file",
        required=True,
        is_list=False,
        show=True,
        value="",
        suffixes=[".json", ".yaml", ".yml"],
        file_types=["json", "yaml", "yml"],
    ),
}


class ToolCreator(LangChainTypeCreator):
    type_name: str = "tools"
    tools_dict: Optional[Dict] = None

    @property
    def type_to_loader_dict(self) -> Dict:
        settings_service = get_settings_service()
        if self.tools_dict is None:
            all_tools = {}

            for tool, tool_fcn in ALL_TOOLS_NAMES.items():
                tool_params = get_tool_params(tool_fcn)

                tool_name = tool_params.get("name") or tool

                if (
                    tool_name in settings_service.settings.TOOLS
                    or settings_service.settings.DEV
                ):
                    if tool_name == "JsonSpec":
                        tool_params["path"] = tool_params.pop("dict_")  # type: ignore
                    all_tools[tool_name] = {
                        "type": tool,
                        "params": tool_params,
                        "fcn": tool_fcn,
                    }

            self.tools_dict = all_tools

        return self.tools_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of a tool."""

        base_classes = ["Tool", "BaseTool"]
        fields = []
        params = []
        tool_params = {}

        # Raise error if name is not in tools
        if name not in self.type_to_loader_dict.keys():
            raise ValueError("Tool not found")

        tool_type: str = self.type_to_loader_dict[name]["type"]  # type: ignore

        # if tool_type in _BASE_TOOLS.keys():
        #     params = []
        if tool_type in _LLM_TOOLS.keys():
            params = ["llm"]
        elif tool_type in _EXTRA_LLM_TOOLS.keys():
            extra_keys = _EXTRA_LLM_TOOLS[tool_type][1]
            params = ["llm"] + extra_keys
        elif tool_type in _EXTRA_OPTIONAL_TOOLS.keys():
            extra_keys = _EXTRA_OPTIONAL_TOOLS[tool_type][1]
            params = extra_keys
        # elif tool_type == "Tool":
        #     params = ["name", "description", "func"]
        elif tool_type in CUSTOM_TOOLS:
            # Get custom tool params
            params = self.type_to_loader_dict[name]["params"]  # type: ignore
            base_classes = ["function"]
            if node := customs.get_custom_nodes("tools").get(tool_type):
                return node
        elif tool_type in FILE_TOOLS:
            params = self.type_to_loader_dict[name]["params"]  # type: ignore
            base_classes += [name]
        elif tool_type in OTHER_TOOLS:
            tool_dict = build_template_from_class(tool_type, OTHER_TOOLS)
            fields = tool_dict["template"]

            # Pop unnecessary fields and add name
            fields.pop("_type")  # type: ignore
            fields.pop("return_direct")  # type: ignore
            fields.pop("verbose")  # type: ignore

            tool_params = {
                "name": fields.pop("name")["value"],  # type: ignore
                "description": fields.pop("description")["value"],  # type: ignore
            }

            fields = [
                TemplateField(name=name, field_type=field["type"], **field)
                for name, field in fields.items()  # type: ignore
            ]
            base_classes += tool_dict["base_classes"]

        # Copy the field and add the name
        for param in params:
            field = TOOL_INPUTS.get(param, TOOL_INPUTS["str"]).copy()
            field.name = param
            field.advanced = False
            if param == "aiosession":
                field.show = False
                field.required = False

            fields.append(field)

        template = Template(fields=fields, type_name=tool_type)

        tool_params = {**tool_params, **self.type_to_loader_dict[name]["params"]}
        return {
            "template": util.format_dict(template.to_dict()),
            **tool_params,
            "base_classes": base_classes,
        }

    def to_list(self) -> List[str]:
        """List all load tools"""

        return list(self.type_to_loader_dict.keys())


tool_creator = ToolCreator()
