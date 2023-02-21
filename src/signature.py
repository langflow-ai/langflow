from fastapi import APIRouter

from langchain import chains
from langchain import agents
from langchain import prompts
from langchain import llms
from langchain import utilities
from langchain.chains.conversation import memory as memories
from langchain import document_loaders
from langchain.agents.load_tools import (
    get_all_tool_names,
    _BASE_TOOLS,
    _LLM_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
)
import util
import list
import inspect

# build router
router = APIRouter(
    prefix="/signatures",
    tags=["signatures"],
)


def build_template_from_function(name: str, dict: dict):
    classes = [item.__annotations__["return"].__name__ for item in dict.values()]

    # Raise error if name is not in chains
    if name not in classes:
        raise Exception(f"{name} not found.")

    for _type, v in dict.items():
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
                        except:
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


def build_template_from_class(name: str, dict: dict):
    classes = [item.__name__ for item in dict.values()]

    # Raise error if name is not in chains
    if name not in classes:
        raise Exception(f"{name} not found.")

    for _type, v in dict.items():
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
                        except:
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
def chain(name: str):
    return build_template_from_function(name, chains.loading.type_to_loader_dict)


@router.get("/agent")
def agent(name: str):
    return build_template_from_class(name, agents.loading.AGENT_TO_CLASS)


@router.get("/prompt")
def prompt(name: str):
    return build_template_from_function(name, prompts.loading.type_to_loader_dict)


@router.get("/llm")
def llm(name: str):
    return build_template_from_class(name, llms.type_to_cls_dict)


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
def memory(name: str):
    return build_template_from_class(name, memories.type_to_cls_dict)


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
def tool(name: str):
    # Raise error if name is not in tools
    if name not in get_all_tool_names():
        raise Exception(f"Tool {name} not found.")

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

    if name in _BASE_TOOLS:
        params = []
    elif name in _LLM_TOOLS:
        params = ["llm"]
    elif name in _EXTRA_LLM_TOOLS:
        _, extra_keys = _EXTRA_LLM_TOOLS[name]
        params = ["llm"] + extra_keys
    elif name in _EXTRA_OPTIONAL_TOOLS:
        _, extra_keys = _EXTRA_OPTIONAL_TOOLS[name]
        params = extra_keys

    template = {
        param: (type_dict[param] if param == "llm" else type_dict["str"])
        for param in params
    }
    template["_type"] = name

    return {
        "template": template,
        **util.get_tool_params(util.get_tools_dict(name)),
        "base_classes": ["Tool"],
    }


#     {"template": signature.tool(tool), **values}
#             for tool, values in tools.items()
#         }
# return {k: util.get_tool_params(v) for k, v in merged_dict.items()}
