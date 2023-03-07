from fastapi import APIRouter
from langflow.backend import signature
from langflow.backend import list_endpoints
from langflow.backend import payload
from langchain.agents.loading import load_agent_executor_from_config
from langchain.chains.loading import load_chain_from_config
from langchain.llms.loading import load_llm_from_config

from langchain.prompts.loading import load_prompt_from_config
from typing import Any
import io
import contextlib
import re


# build router
router = APIRouter()


def get_type_list():
    all_types = get_all()

    all_types.pop("tools")

    for key, value in all_types.items():
        all_types[key] = [item["template"]["_type"] for item in value.values()]

    return all_types


@router.get("/all")
def get_all():
    return {
        "chains": {
            chain: signature.get_chain(chain) for chain in list_endpoints.list_chains()
        },
        "agents": {
            agent: signature.get_agent(agent) for agent in list_endpoints.list_agents()
        },
        "prompts": {
            prompt: signature.get_prompt(prompt)
            for prompt in list_endpoints.list_prompts()
        },
        "llms": {llm: signature.get_llm(llm) for llm in list_endpoints.list_llms()},
        # "utilities": {
        #     "template": {
        #         # utility: templates.utility(utility) for utility in list.list_utilities()
        #     }
        # },
        "memories": {
            memory: signature.get_memory(memory)
            for memory in list_endpoints.list_memories()
        },
        # "document_loaders": {
        #     "template": {
        #         # memory: templates.document_loader(memory)
        #         # for memory in list.list_document_loaders()
        #     }
        # },
        # "vectorstores": {"template": {}},
        # "docstores": {"template": {}},
        # "tools": {
        #     tool: {"template": signature.tool(tool), **values}
        #     for tool, values in tools.items()
        # },
        "tools": {
            tool: signature.get_tool(tool) for tool in list_endpoints.list_tools()
        },
    }


@router.post("/predict")
def get_load(data: dict[str, Any]):
    # Get type list
    type_list = get_type_list()

    # Substitute ZeroShotPromt with PromptTemplate
    for node in data["nodes"]:
        if node["data"]["type"] == "ZeroShotPrompt":
            # Build Prompt Template
            tools = [
                tool
                for tool in data["nodes"]
                if tool["type"] != "chatOutputNode"
                and "Tool" in tool["data"]["node"]["base_classes"]
            ]
            node["data"] = build_prompt_template(prompt=node["data"], tools=tools)
            break

    # Add input variables
    data = payload.extract_input_variables(data)

    # Nodes, edges and root node
    message = data["message"]
    nodes = data["nodes"]
    edges = data["edges"]
    root = payload.get_root_node(data)

    extracted_json = payload.build_json(root, nodes, edges)

    # Build json
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

    return {
        "result": result,
        "thought": re.sub(
            r"\x1b\[([0-9,A-Z]{1,2}(;[0-9,A-Z]{1,2})?)?[m|K]", "", thought
        ).strip(),
    }


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
