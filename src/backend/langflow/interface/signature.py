from typing import Any, Dict  # noqa: F401

from langchain import agents, chains, prompts
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
    get_all_tool_names,
)

from langflow.custom import customs
from langflow.interface.custom_lists import (
    llm_type_to_cls_dict,
    memory_type_to_cls_dict,
)
from langflow.utils import util


def get_signature(name: str, object_type: str):
    """Get the signature of an object."""
    return {
        "chains": get_chain_signature,
        "agents": get_agent_signature,
        "prompts": get_prompt_signature,
        "llms": get_llm_signature,
        "memories": get_memory_signature,
        "tools": get_tool_signature,
    }.get(object_type, lambda name: f"Invalid type: {name}")(name)


def get_chain_signature(name: str):
    """Get the chain type by signature."""
    try:
        return util.build_template_from_function(
            name, chains.loading.type_to_loader_dict
        )
    except ValueError as exc:
        raise ValueError("Chain not found") from exc


def get_agent_signature(name: str):
    """Get the signature of an agent."""
    try:
        return util.build_template_from_class(name, agents.loading.AGENT_TO_CLASS)
    except ValueError as exc:
        raise ValueError("Agent not found") from exc


def get_prompt_signature(name: str):
    """Get the signature of a prompt."""
    try:
        if name in customs.get_custom_prompts().keys():
            return customs.get_custom_prompts()[name]
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

    all_tools = {}
    for tool in get_all_tool_names():
        if tool_params := util.get_tool_params(util.get_tools_dict(tool)):
            all_tools[tool_params["name"]] = tool

    # Raise error if name is not in tools
    if name not in all_tools.keys():
        raise ValueError("Tool not found")

    type_dict = {
        "str": {
            "type": "str",
            "required": True,
            "list": False,
            "show": True,
            "placeholder": "",
            "value": "",
        },
        "llm": {"type": "BaseLLM", "required": True, "list": False, "show": True},
    }

    tool_type = all_tools[name]

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
    else:
        params = []

    template = {
        param: (type_dict[param].copy() if param == "llm" else type_dict["str"].copy())
        for param in params
    }

    # Remove required from aiosession
    if "aiosession" in template.keys():
        template["aiosession"]["required"] = False
        template["aiosession"]["show"] = False

    template["_type"] = tool_type  # type: ignore

    return {
        "template": template,
        **util.get_tool_params(util.get_tools_dict(tool_type)),
        "base_classes": ["Tool"],
    }
