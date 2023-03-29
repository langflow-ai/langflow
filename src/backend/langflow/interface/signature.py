from typing import Any, Dict  # noqa: F401

from langchain import agents, chains, prompts
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)

from langflow.custom import customs
from langflow.interface.custom_lists import (
    llm_type_to_cls_dict,
    memory_type_to_cls_dict,
    toolkit_type_to_cls_dict,
    toolkit_type_to_loader_dict,
    wrapper_type_to_cls_dict,
)

from langflow.interface.listing import CUSTOM_TOOLS, ALL_TOOLS_NAMES
from langflow.template.template import Field, Template
from langflow.utils import util


def get_signature(name: str, object_type: str):
    """Get the signature of an object."""
    return {
        "toolkits": get_toolkit_signature,
        "chains": get_chain_signature,
        "agents": get_agent_signature,
        "prompts": get_prompt_signature,
        "llms": get_llm_signature,
        # "memories": get_memory_signature,
        "tools": get_tool_signature,
        "wrappers": get_wrapper_signature,
    }.get(object_type, lambda name: f"Invalid type: {name}")(name)


def get_toolkit_signature(name: str):
    """Get the signature of a toolkit."""
    try:
        if name.islower():
            pass
            # return util.build_template_from_function(
            #     name, toolkit_type_to_loader_dict, add_function=True
            # )
        else:
            return util.build_template_from_class(
                name, toolkit_type_to_cls_dict, add_function=True
            )
    except ValueError as exc:
        raise ValueError("Toolkit not found") from exc


def get_wrapper_signature(name: str):
    """Get the signature of a wrapper."""
    try:
        return util.build_template_from_class(
            name,
            wrapper_type_to_cls_dict,
        )
    except ValueError as exc:
        raise ValueError("Wrapper not found") from exc


def get_chain_signature(name: str):
    """Get the chain type by signature."""
    try:
        return util.build_template_from_function(
            name, chains.loading.type_to_loader_dict, add_function=True
        )

    except ValueError as exc:
        raise ValueError("Chain not found") from exc


def get_agent_signature(name: str):
    """Get the signature of an agent."""
    try:
        return util.build_template_from_class(
            name, agents.loading.AGENT_TO_CLASS, add_function=True
        )
    except ValueError as exc:
        raise ValueError("Agent not found") from exc


def get_prompt_signature(name: str):
    """Get the signature of a prompt."""
    try:
        if name in customs.get_custom_nodes("prompts").keys():
            return customs.get_custom_nodes("prompts")[name]
        return util.build_template_from_function(
            name, prompts.loading.type_to_loader_dict
        )
    except ValueError as exc:
        raise ValueError("Prompt not found") from exc


def get_llm_signature(name: str):
    """Get the signature of an llm."""
    try:
        return util.build_template_from_class(name, llm_type_to_cls_dict)
    except ValueError as exc:
        raise ValueError("LLM not found") from exc


def get_memory_signature(name: str):
    """Get the signature of a memory."""
    try:
        return util.build_template_from_class(name, memory_type_to_cls_dict)
    except ValueError as exc:
        raise ValueError("Memory not found") from exc


def get_tool_signature(name: str):
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
