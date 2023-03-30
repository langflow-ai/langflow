# This module is used to import any langchain class by name.

import importlib
from typing import Any

from langchain import PromptTemplate
from langchain.agents import Agent
from langchain.chains.base import Chain
from langchain.llms.base import BaseLLM
from langchain.tools import BaseTool
from langflow.interface.tools.util import get_tool_by_name


def import_module(module_path: str) -> Any:
    """Import module from module path"""
    return importlib.import_module(module_path)


def import_by_type(_type: str, name: str) -> Any:
    """Import class by type and name"""
    func_dict = {
        "agents": import_agent,
        "prompts": import_prompt,
        "llms": import_llm,
        "tools": import_tool,
        "chains": import_chain,
    }
    return func_dict[_type](name)


def import_class(class_path: str) -> Any:
    """Import class from class path"""
    module_path, class_name = class_path.rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, class_name)


def import_prompt(prompt: str) -> PromptTemplate:
    """Import prompt from prompt name"""
    if prompt == "ZeroShotPrompt":
        return import_class("langchain.prompts.PromptTemplate")
    return import_class(f"langchain.prompts.{prompt}")


def import_agent(agent: str) -> Agent:
    """Import agent from agent name"""
    return import_class(f"langchain.agents.{agent}")


def import_llm(llm: str) -> BaseLLM:
    """Import llm from llm name"""
    return import_class(f"langchain.llms.{llm}")


def import_tool(tool: str) -> BaseTool:
    """Import tool from tool name"""

    return get_tool_by_name(tool)


def import_chain(chain: str) -> Chain:
    """Import chain from chain name"""
    return import_class(f"langchain.chains.{chain}")
