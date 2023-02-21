from fastapi import APIRouter
import signature
import list_endpoints

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
            chain: signature.chain(chain) for chain in list_endpoints.list_chains()
        },
        "agents": {
            agent: signature.agent(agent) for agent in list_endpoints.list_agents()
        },
        "prompts": {
            prompt: signature.prompt(prompt) for prompt in list_endpoints.list_prompts()
        },
        "llms": {llm: signature.llm(llm) for llm in list_endpoints.list_llms()},
        # "utilities": {
        #     "template": {
        #         # utility: templates.utility(utility) for utility in list.list_utilities()
        #     }
        # },
        "memories": {
            memory: signature.memory(memory)
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
        "tools": {tool: signature.tool(tool) for tool in list_endpoints.list_tools()},
    }


@router.post("/predict")
def get_load(data: dict[str, str]):
    a = get_type_list()

    # Build json

    # if type in a["prompts"]:

    return a
