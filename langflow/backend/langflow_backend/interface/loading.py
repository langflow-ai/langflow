import contextlib
import re
import io
from typing import Any, Dict
from langflow_backend.interface.types import get_type_list
from langchain.agents.loading import load_agent_executor_from_config
from langchain.chains.loading import load_chain_from_config
from langchain.llms.loading import load_llm_from_config
from langflow_backend.utils import payload


def replace_zero_shot_prompt_with_prompt_template(nodes):
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


def process_data_graph(data_graph: Dict[str, Any]):
    nodes = data_graph["nodes"]
    # Substitute ZeroShotPrompt with PromptTemplate
    nodes = replace_zero_shot_prompt_with_prompt_template(nodes)
    # Add input variables
    data_graph = payload.extract_input_variables(data_graph)
    # Nodes, edges and root node
    message = data_graph["message"]
    edges = data_graph["edges"]
    root = payload.get_root_node(data_graph)
    extracted_json = payload.build_json(root, nodes, edges)

    # Process json
    result, thought = get_result_and_thought(extracted_json, message)

    # Remove unnecessary data from response
    begin = thought.rfind(message)
    thought = thought[(begin + len(message)) :]

    return {
        "result": result,
        "thought": re.sub(
            r"\x1b\[([0-9,A-Z]{1,2}(;[0-9,A-Z]{1,2})?)?[m|K]", "", thought
        ).strip(),
    }


def get_result_and_thought(extracted_json: Dict[str, Any], message: str):
    # Get type list
    type_list = get_type_list()
    if extracted_json["_type"] in type_list["agents"]:
        loaded = load_agent_executor_from_config(extracted_json)

        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            result = loaded.run(message)
            thought = output_buffer.getvalue()

    elif extracted_json["_type"] in type_list["chains"]:
        loaded = load_chain_from_config(extracted_json)

        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            result = loaded.run(message)
            thought = output_buffer.getvalue()

    elif extracted_json["_type"] in type_list["llms"]:
        loaded = load_llm_from_config(extracted_json)

        with io.StringIO() as output_buffer, contextlib.redirect_stdout(output_buffer):
            result = loaded(message)
            thought = output_buffer.getvalue()
    else:
        result = "Error: Type should be either agent, chain or llm"
        thought = ""
    return result, thought


def build_prompt_template(prompt, tools):
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
