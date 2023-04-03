import json
from typing import Any, Callable, Dict, Optional

from langchain.agents import ZeroShotAgent
from langchain.agents import agent as agent_module
from langchain.agents.agent import AgentExecutor
from langchain.agents.agent_toolkits.base import BaseToolkit
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)
from langchain.agents.loading import load_agent_from_config
from langchain.agents.tools import Tool
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains.loading import load_chain_from_config
from langchain.llms.base import BaseLLM
from langchain.llms.loading import load_llm_from_config

from langflow.interface.agents.custom import CUSTOM_AGENTS
from langflow.interface.importing.utils import import_by_type
from langflow.interface.toolkits.base import toolkits_creator
from langflow.interface.types import get_type_list
from langflow.utils import util, validate


def instantiate_class(node_type: str, base_type: str, params: Dict) -> Any:
    """Instantiate class from module type and key, and params"""
    if node_type in CUSTOM_AGENTS:
        if custom_agent := CUSTOM_AGENTS.get(node_type):
            return custom_agent.initialize(**params)  # type: ignore

    class_object = import_by_type(_type=base_type, name=node_type)

    if base_type == "agents":
        # We need to initialize it differently
        return load_agent_executor(class_object, params)
    elif node_type == "ZeroShotPrompt":
        if "tools" not in params:
            params["tools"] = []
        return ZeroShotAgent.create_prompt(**params)

    elif node_type == "PythonFunction":
        # If the node_type is "PythonFunction"
        # we need to get the function from the params
        # which will be a str containing a python function
        # and then we need to compile it and return the function
        # as the instance
        function_string = params["code"]
        if isinstance(function_string, str):
            return validate.eval_function(function_string)
        raise ValueError("Function should be a string")
    elif base_type == "toolkits":
        loaded_toolkit = class_object(**params)
        # Check if node_type has a loader
        if toolkits_creator.has_create_function(node_type):
            return load_toolkits_executor(node_type, loaded_toolkit, params)
        return loaded_toolkit
    else:
        return class_object(**params)


def load_flow_from_json(path: str):
    # This is done to avoid circular imports
    from langflow.graph import Graph

    """Load flow from json file"""
    with open(path, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    # Substitute ZeroShotPrompt with PromptTemplate
    # nodes = replace_zero_shot_prompt_with_prompt_template(nodes)
    # Add input variables
    # nodes = payload.extract_input_variables(nodes)

    # Nodes, edges and root node
    edges = data_graph["edges"]
    graph = Graph(nodes, edges)
    return graph.build()


def replace_zero_shot_prompt_with_prompt_template(nodes):
    """Replace ZeroShotPrompt with PromptTemplate"""
    for node in nodes:
        if node["data"]["type"] == "ZeroShotPrompt":
            # Build Prompt Template
            tools = [
                tool
                for tool in nodes
                if tool["type"] != "chatOutputNode"
                and "Tool" in tool["data"]["node"]["base_classes"]
            ]
            node["data"] = build_prompt_template(prompt=node["data"], tools=tools)
            break
    return nodes


def load_langchain_type_from_config(config: Dict[str, Any]):
    """Load langchain type from config"""
    # Get type list
    type_list = get_type_list()
    if config["_type"] in type_list["agents"]:
        config = util.update_verbose(config, new_value=False)
        return load_agent_executor_from_config(config, verbose=True)
    elif config["_type"] in type_list["chains"]:
        config = util.update_verbose(config, new_value=False)
        return load_chain_from_config(config, verbose=True)
    elif config["_type"] in type_list["llms"]:
        config = util.update_verbose(config, new_value=True)
        return load_llm_from_config(config)
    else:
        raise ValueError("Type should be either agent, chain or llm")


def load_agent_executor_from_config(
    config: dict,
    llm: Optional[BaseLLM] = None,
    tools: Optional[list[Tool]] = None,
    callback_manager: Optional[BaseCallbackManager] = None,
    **kwargs: Any,
):
    tools = load_tools_from_config(config["allowed_tools"])
    config["allowed_tools"] = [tool.name for tool in tools] if tools else []
    agent_obj = load_agent_from_config(config, llm, tools, **kwargs)

    return AgentExecutor.from_agent_and_tools(
        agent=agent_obj,
        tools=tools,
        callback_manager=callback_manager,
        **kwargs,
    )


def load_agent_executor(agent_class: type[agent_module.Agent], params, **kwargs):
    """Load agent executor from agent class, tools and chain"""
    allowed_tools = params["allowed_tools"]
    llm_chain = params["llm_chain"]
    tool_names = [tool.name for tool in allowed_tools]
    agent = agent_class(allowed_tools=tool_names, llm_chain=llm_chain)
    return AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=allowed_tools,
        **kwargs,
    )


def load_toolkits_executor(node_type: str, toolkit: BaseToolkit, params: dict):
    create_function: Callable = toolkits_creator.get_create_function(node_type)
    if llm := params.get("llm"):
        return create_function(llm=llm, toolkit=toolkit)


def load_tools_from_config(tool_list: list[dict]) -> list:
    """Load tools based on a config list.

    Args:
        config: config list.

    Returns:
        List of tools.
    """
    tools = []
    for tool in tool_list:
        tool_type = tool.pop("_type")
        llm_config = tool.pop("llm", None)
        llm = load_llm_from_config(llm_config) if llm_config else None
        kwargs = tool
        if tool_type in _BASE_TOOLS:
            tools.append(_BASE_TOOLS[tool_type]())
        elif tool_type in _LLM_TOOLS:
            if llm is None:
                raise ValueError(f"Tool {tool_type} requires an LLM to be provided")
            tools.append(_LLM_TOOLS[tool_type](llm))
        elif tool_type in _EXTRA_LLM_TOOLS:
            if llm is None:
                raise ValueError(f"Tool {tool_type} requires an LLM to be provided")
            _get_llm_tool_func, extra_keys = _EXTRA_LLM_TOOLS[tool_type]
            if missing_keys := set(extra_keys).difference(kwargs):
                raise ValueError(
                    f"Tool {tool_type} requires some parameters that were not "
                    f"provided: {missing_keys}"
                )
            tools.append(_get_llm_tool_func(llm=llm, **kwargs))
        elif tool_type in _EXTRA_OPTIONAL_TOOLS:
            _get_tool_func, extra_keys = _EXTRA_OPTIONAL_TOOLS[tool_type]
            kwargs = {k: value for k, value in kwargs.items() if value}
            tools.append(_get_tool_func(**kwargs))
        else:
            raise ValueError(f"Got unknown tool {tool_type}")
    return tools


def build_prompt_template(prompt, tools):
    """Build PromptTemplate from ZeroShotPrompt"""
    prefix = prompt["node"]["template"]["prefix"]["value"]
    suffix = prompt["node"]["template"]["suffix"]["value"]
    format_instructions = prompt["node"]["template"]["format_instructions"]["value"]

    tool_strings = "\n".join(
        [
            f"{tool['data']['node']['name']}: {tool['data']['node']['description']}"
            for tool in tools
        ]
    )
    tool_names = ", ".join([tool["data"]["node"]["name"] for tool in tools])
    format_instructions = format_instructions.format(tool_names=tool_names)
    value = "\n\n".join([prefix, tool_strings, format_instructions, suffix])

    prompt["type"] = "PromptTemplate"

    prompt["node"] = {
        "template": {
            "_type": "prompt",
            "input_variables": {
                "type": "str",
                "required": True,
                "placeholder": "",
                "list": True,
                "show": False,
                "multiline": False,
            },
            "output_parser": {
                "type": "BaseOutputParser",
                "required": False,
                "placeholder": "",
                "list": False,
                "show": False,
                "multline": False,
                "value": None,
            },
            "template": {
                "type": "str",
                "required": True,
                "placeholder": "",
                "list": False,
                "show": True,
                "multiline": True,
                "value": value,
            },
            "template_format": {
                "type": "str",
                "required": False,
                "placeholder": "",
                "list": False,
                "show": False,
                "multline": False,
                "value": "f-string",
            },
            "validate_template": {
                "type": "bool",
                "required": False,
                "placeholder": "",
                "list": False,
                "show": False,
                "multline": False,
                "value": True,
            },
        },
        "description": "Schema to represent a prompt for an LLM.",
        "base_classes": ["BasePromptTemplate"],
    }

    return prompt
