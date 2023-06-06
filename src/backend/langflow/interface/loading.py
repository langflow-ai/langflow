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
from langchain.base_language import BaseLanguageModel
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains.loading import load_chain_from_config
from langchain.llms.loading import load_llm_from_config
from pydantic import ValidationError

from langflow.interface.agents.custom import CUSTOM_AGENTS
from langflow.interface.importing.utils import get_function, import_by_type
from langflow.interface.toolkits.base import toolkits_creator
from langflow.interface.types import get_type_list
from langflow.interface.utils import load_file_into_dict
from langflow.utils import util


def instantiate_class(node_type: str, base_type: str, params: Dict) -> Any:
    """Instantiate class from module type and key, and params"""
    params = convert_params_to_sets(params)
    params = convert_kwargs(params)
    if node_type in CUSTOM_AGENTS:
        custom_agent = CUSTOM_AGENTS.get(node_type)
        if custom_agent:
            return custom_agent.initialize(**params)

    class_object = import_by_type(_type=base_type, name=node_type)
    return instantiate_based_on_type(class_object, base_type, node_type, params)


def convert_params_to_sets(params):
    """Convert certain params to sets"""
    if "allowed_special" in params:
        params["allowed_special"] = set(params["allowed_special"])
    if "disallowed_special" in params:
        params["disallowed_special"] = set(params["disallowed_special"])
    return params


def convert_kwargs(params):
    # if *kwargs are passed as a string, convert to dict
    # first find any key that has kwargs in it
    kwargs_keys = [key for key in params.keys() if "kwargs" in key]
    for key in kwargs_keys:
        if isinstance(params[key], str):
            params[key] = json.loads(params[key])
    return params


def instantiate_based_on_type(class_object, base_type, node_type, params):
    if base_type == "agents":
        return instantiate_agent(class_object, params)
    elif base_type == "prompts":
        return instantiate_prompt(node_type, class_object, params)
    elif base_type == "tools":
        return instantiate_tool(node_type, class_object, params)
    elif base_type == "toolkits":
        return instantiate_toolkit(node_type, class_object, params)
    elif base_type == "embeddings":
        return instantiate_embedding(class_object, params)
    elif base_type == "vectorstores":
        return instantiate_vectorstore(class_object, params)
    elif base_type == "documentloaders":
        return instantiate_documentloader(class_object, params)
    elif base_type == "textsplitters":
        return instantiate_textsplitter(class_object, params)
    elif base_type == "utilities":
        return instantiate_utility(node_type, class_object, params)
    else:
        return class_object(**params)


def instantiate_agent(class_object, params):
    return load_agent_executor(class_object, params)


def instantiate_prompt(node_type, class_object, params):
    if node_type == "ZeroShotPrompt":
        if "tools" not in params:
            params["tools"] = []
        return ZeroShotAgent.create_prompt(**params)
    return class_object(**params)


def instantiate_tool(node_type, class_object, params):
    if node_type == "JsonSpec":
        params["dict_"] = load_file_into_dict(params.pop("path"))
        return class_object(**params)
    elif node_type == "PythonFunctionTool":
        params["func"] = get_function(params.get("code"))
        return class_object(**params)
    elif node_type.lower() == "tool":
        return class_object(**params)
    return class_object(**params)


def instantiate_toolkit(node_type, class_object, params):
    loaded_toolkit = class_object(**params)
    # Commenting this out for now to use toolkits as normal tools
    # if toolkits_creator.has_create_function(node_type):
    #     return load_toolkits_executor(node_type, loaded_toolkit, params)
    if isinstance(loaded_toolkit, BaseToolkit):
        return loaded_toolkit.get_tools()
    return loaded_toolkit


def instantiate_embedding(class_object, params):
    params.pop("model", None)
    params.pop("headers", None)
    try:
        return class_object(**params)
    except ValidationError:
        params = {
            key: value
            for key, value in params.items()
            if key in class_object.__fields__
        }
        return class_object(**params)


def instantiate_vectorstore(class_object, params):
    if len(params.get("documents", [])) == 0:
        raise ValueError(
            "The source you provided did not load correctly or was empty."
            "This may cause an error in the vectorstore."
        )
    return class_object.from_documents(**params)


def instantiate_documentloader(class_object, params):
    return class_object(**params).load()


def instantiate_textsplitter(class_object, params):
    try:
        documents = params.pop("documents")
    except KeyError as e:
        raise ValueError(
            "The source you provided did not load correctly or was empty."
            "Try changing the chunk_size of the Text Splitter."
        ) from e
    text_splitter = class_object(**params)
    return text_splitter.split_documents(documents)


def instantiate_utility(node_type, class_object, params):
    if node_type == "SQLDatabase":
        return class_object.from_uri(params.pop("uri"))
    return class_object(**params)


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
    llm: Optional[BaseLanguageModel] = None,
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
    allowed_tools = params.get("allowed_tools", [])
    llm_chain = params["llm_chain"]
    # if allowed_tools is not a list or set, make it a list
    if not isinstance(allowed_tools, (list, set)):
        allowed_tools = [allowed_tools]
    tool_names = [tool.name for tool in allowed_tools]
    # Agent class requires an output_parser but Agent classes
    # have a default output_parser.
    agent = agent_class(allowed_tools=tool_names, llm_chain=llm_chain)  # type: ignore
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
