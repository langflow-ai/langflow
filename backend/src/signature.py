from fastapi import APIRouter, HTTPException
from langchain import agents, chains, llms, prompts
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
    get_all_tool_names,
)
from langchain.chains.conversation import memory as memories

import util

# build router
router = APIRouter(
    prefix="/signatures",
    tags=["signatures"],
)


def build_template_from_function(name: str, type_to_loader_dict: dict):
    classes = [
        item.__annotations__["return"].__name__ for item in type_to_loader_dict.values()
    ]

    # Raise error if name is not in chains
    if name not in classes:
        raise ValueError(f"{name} not found")

    for _type, v in type_to_loader_dict.items():
        if v.__annotations__["return"].__name__ == name:
            _class = v.__annotations__["return"]

            docs = util.get_class_doc(_class)

            variables = {"_type": _type}
            for name, value in _class.__fields__.items():
                if name in ["callback_manager", "requests_wrapper"]:
                    continue
                variables[name] = {}
                for name_, value_ in value.__repr_args__():
                    if name_ == "default_factory":
                        try:
                            variables[name]["default"] = util.get_default_factory(
                                module=_class.__base__.__module__, function=value_
                            )
                        except Exception:
                            variables[name]["default"] = None
                    elif name_ not in ["name"]:
                        variables[name][name_] = value_

                variables[name]["placeholder"] = (
                    docs["Attributes"][name] if name in docs["Attributes"] else ""
                )

            return {
                "template": util.format_dict(variables),
                "description": docs["Description"],
                "base_classes": util.get_base_classes(_class),
            }


def build_template_from_class(name: str, type_to_cls_dict: dict):
    classes = [item.__name__ for item in type_to_cls_dict.values()]

    # Raise error if name is not in chains
    if name not in classes:
        raise ValueError(f"{name} not found.")

    for _type, v in type_to_cls_dict.items():
        if v.__name__ == name:
            _class = v

            docs = util.get_class_doc(_class)

            variables = {"_type": _type}
            for name, value in _class.__fields__.items():
                if name in ["callback_manager"]:
                    continue
                variables[name] = {}
                for name_, value_ in value.__repr_args__():
                    if name_ == "default_factory":
                        try:
                            variables[name]["default"] = util.get_default_factory(
                                module=_class.__base__.__module__, function=value_
                            )
                        except Exception:
                            variables[name]["default"] = None
                    elif name_ not in ["name"]:
                        variables[name][name_] = value_

                variables[name]["placeholder"] = (
                    docs["Attributes"][name] if name in docs["Attributes"] else ""
                )

            return {
                "template": util.format_dict(variables),
                "description": docs["Description"],
                "base_classes": util.get_base_classes(_class),
            }


@router.get("/chain")
def get_chain(name: str):
    """Get the signature of a chain."""
    try:
        return build_template_from_function(name, chains.loading.type_to_loader_dict)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Chain not found") from exc


@router.get("/agent")
def get_agent(name: str):
    """Get the signature of an agent."""
    try:
        return build_template_from_class(name, agents.loading.AGENT_TO_CLASS)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc


@router.get("/prompt")
def get_prompt(name: str):
    """Get the signature of a prompt."""
    try:
        return build_template_from_function(name, prompts.loading.type_to_loader_dict)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Prompt not found") from exc


@router.get("/llm")
def get_llm(name: str):
    """Get the signature of an llm."""
    try:
        return build_template_from_class(name, llms.type_to_cls_dict)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="LLM not found") from exc


# @router.get("/utility")
# def utility(name: str):
#     # Raise error if name is not in utilities
#     if name not in utilities.__all__:
#         raise Exception(f"Prompt {name} not found.")
#     _class = getattr(utilities, name)
#     return {
#         name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
#         for name, value in _class.__fields__.items()
#     }


@router.get("/memory")
def get_memory(name: str):
    """Get the signature of a memory."""
    try:
        return build_template_from_class(name, memories.type_to_cls_dict)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


# @router.get("/document_loader")
# def document_loader(name: str):
#     # Raise error if name is not in document_loader
#     if name not in document_loaders.__all__:
#         raise Exception(f"Prompt {name} not found.")
#     _class = getattr(document_loaders, name)
#     return {
#         name: {name: value for (name, value) in value.__repr_args__() if name != "name"}
#         for name, value in _class.__fields__.items()
#     }


@router.get("/tool")
def get_tool(name: str):
    """Get the signature of a tool."""

    all_tools = {
        util.get_tool_params(util.get_tools_dict(tool))["name"]: tool
        for tool in get_all_tool_names()
    }

    # Raise error if name is not in tools
    if name not in all_tools.keys():
        raise HTTPException(status_code=404, detail=f"Tool {name} not found.")

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

    template = {
        param: (type_dict[param] if param == "llm" else type_dict["str"])
        for param in params
    }
    template["_type"] = tool_type

    return {
        "template": template,
        **util.get_tool_params(util.get_tools_dict(tool_type)),
        "base_classes": ["Tool"],
    }


#     {"template": signature.tool(tool), **values}
#             for tool, values in tools.items()
#         }
# return {k: util.get_tool_params(v) for k, v in merged_dict.items()}
