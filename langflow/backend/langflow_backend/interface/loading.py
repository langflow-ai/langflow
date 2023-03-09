import json
from typing import Any, Dict
from langflow_backend.interface.types import get_type_list
from langchain.agents.loading import load_agent_executor_from_config
from langchain.chains.loading import load_chain_from_config
from langchain.llms.loading import load_llm_from_config
from langflow_backend.utils import payload


def load_flow_from_json(path: str):
    """Load flow from json file"""
    with open(path, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    extracted_json = extract_json(data_graph)
    return load_langchain_type_from_config(config=extracted_json)


def extract_json(data_graph):
    nodes = data_graph["nodes"]
    # Substitute ZeroShotPrompt with PromptTemplate
    nodes = replace_zero_shot_prompt_with_prompt_template(nodes)
    # Add input variables
    nodes = payload.extract_input_variables(nodes)
    # Nodes, edges and root node
    edges = data_graph["edges"]
    root = payload.get_root_node(nodes, edges)
    return payload.build_json(root, nodes, edges)


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
        return load_agent_executor_from_config(config)
    elif config["_type"] in type_list["chains"]:
        return load_chain_from_config(config)
    elif config["_type"] in type_list["llms"]:
        return load_llm_from_config(config)
    else:
        raise ValueError("Type should be either agent, chain or llm")


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
