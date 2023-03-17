from fastapi import APIRouter

from langflow.interface.listing import list_type

# build router
router = APIRouter(
    prefix="/list",
    tags=["list"],
)


@router.get("/")
def read_items():
    """List all components"""
    return [
        "chains",
        "agents",
        "prompts",
        "llms",
        "tools",
    ]


@router.get("/chains")
def list_chains():
    """List all chain types"""
    return list_type("chains")


@router.get("/agents")
def list_agents():
    """List all agent types"""
    # return list(agents.loading.AGENT_TO_CLASS.keys())
    return list_type("agents")


@router.get("/prompts")
def list_prompts():
    """List all prompt types"""
    return list_type("prompts")


@router.get("/llms")
def list_llms():
    """List all llm types"""
    return list_type("llms")


@router.get("/memories")
def list_memories():
    """List all memory types"""
    return list_type("memories")


@router.get("/tools")
def list_tools():
    """List all load tools"""
    return list_type("tools")
