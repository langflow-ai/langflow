from fastapi import APIRouter
import signature
import list_endpoints
import payload
from langchain.agents.loading import load_agent_executor_from_config
from langchain.chains.loading import load_chain_from_config
from langchain.llms.loading import load_llm_from_config

from langchain.prompts.loading import load_prompt_from_config
from typing import Any

# build router
router = APIRouter()


def get_type_list():
    all_types = get_all()

    all_types.pop("tools")

    for key, value in all_types.items():
        all_types[key] = [item["template"]["_type"] for item in value.values()]

    return all_types


@router.get("/")
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
    type_list = get_type_list()

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

        return {"result": loaded.run(message)}
    elif extracted_json["_type"] in type_list["chains"]:
        loaded = load_chain_from_config(extracted_json)

        return {"result": loaded.run(message)}
    elif extracted_json["_type"] in type_list["llms"]:
        loaded = load_llm_from_config(extracted_json)

        return {"result": loaded(message)}
    else:
        return {"result": "Error: Type should be either agent, chain or llm"}

    # elif extracted_json["_type"] in type_list["prompts"]:
    #     loaded = load_prompt_from_config(extracted_json)
    #     print(loaded.format(product=''))

    #     return {'result': loaded.format(product=message)}

    # if type in a["prompts"]:

    # return a
