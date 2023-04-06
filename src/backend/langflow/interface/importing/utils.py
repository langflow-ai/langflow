# This module is used to import any langchain class by name.

import importlib
from typing import Any, Type

from langchain import PromptTemplate
from langchain.agents import Agent
from langchain.chains.base import Chain
from langchain.chat_models.base import BaseChatModel
from langchain.llms.base import BaseLLM
from langchain.tools import BaseTool

from langflow.interface.tools.util import get_tool_by_name


def import_module(module_path: str) -> Any:
    """Import module from module path"""
    if "from" not in module_path:
        # Import the module using the module path
        return importlib.import_module(module_path)
    # Split the module path into its components
    _, module_path, _, object_name = module_path.split()

    # Import the module using the module path
    module = importlib.import_module(module_path)

    return getattr(module, object_name)


def import_by_type(_type: str, name: str) -> Any:
    """Import class by type and name"""
    if _type is None:
        raise ValueError(f"Type cannot be None. Check if {name} is in the config file.")
    func_dict = {
        "agents": import_agent,
        "prompts": import_prompt,
        "llms": {"llm": import_llm, "chat": import_chat_llm},
        "tools": import_tool,
        "chains": import_chain,
        "toolkits": import_toolkit,
        "wrappers": import_wrapper,
        "memory": import_memory,
    }
    if _type == "llms":
        key = "chat" if "chat" in name.lower() else "llm"
        loaded_func = func_dict[_type][key]  # type: ignore
    else:
        loaded_func = func_dict[_type]

    return loaded_func(name)


def import_chat_llm(llm: str) -> BaseChatModel:
    """Import chat llm from llm name"""
    return import_class(f"langchain.chat_models.{llm}")


def import_memory(memory: str) -> Any:
    """Import memory from memory name"""
    return import_module(f"from langchain.memory import {memory}")


def import_class(class_path: str) -> Any:
    """Import class from class path"""
    module_path, class_name = class_path.rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, class_name)


def import_prompt(prompt: str) -> Type[PromptTemplate]:
    from langflow.interface.prompts.custom import CUSTOM_PROMPTS

    """Import prompt from prompt name"""
    if prompt == "ZeroShotPrompt":
        return import_class("langchain.prompts.PromptTemplate")
    elif prompt in CUSTOM_PROMPTS:
        return CUSTOM_PROMPTS[prompt]
    return import_class(f"langchain.prompts.{prompt}")


def import_wrapper(wrapper: str) -> Any:
    """Import wrapper from wrapper name"""
    return import_module(f"from langchain.requests import {wrapper}")


def import_toolkit(toolkit: str) -> Any:
    """Import toolkit from toolkit name"""
    return import_module(f"from langchain.agents.agent_toolkits import {toolkit}")


def import_agent(agent: str) -> Agent:
    """Import agent from agent name"""
    # check for custom agent

    return import_class(f"langchain.agents.{agent}")


def import_llm(llm: str) -> BaseLLM:
    """Import llm from llm name"""
    return import_class(f"langchain.llms.{llm}")


def import_tool(tool: str) -> BaseTool:
    """Import tool from tool name"""

    return get_tool_by_name(tool)


def import_chain(chain: str) -> Type[Chain]:
    """Import chain from chain name"""
    from langflow.interface.chains.custom import CUSTOM_CHAINS

    if chain in CUSTOM_CHAINS:
        return CUSTOM_CHAINS[chain]
    return import_class(f"langchain.chains.{chain}")
