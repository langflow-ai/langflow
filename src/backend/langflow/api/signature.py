from fastapi import APIRouter, HTTPException

from langflow.interface.signature import get_signature

# build router
router = APIRouter(
    prefix="/signatures",
    tags=["signatures"],
)


@router.get("/chain")
def get_chain(name: str):
    """Get the signature of a chain."""
    try:
        return get_signature(name, "chains")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Chain not found") from exc


@router.get("/agent")
def get_agent(name: str):
    """Get the signature of an agent."""
    try:
        return get_signature(name, "agents")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc


@router.get("/prompt")
def get_prompt(name: str):
    """Get the signature of a prompt."""
    try:
        return get_signature(name, "prompts")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Prompt not found") from exc


@router.get("/llm")
def get_llm(name: str):
    """Get the signature of an llm."""
    try:
        return get_signature(name, "llms")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="LLM not found") from exc


@router.get("/memory")
def get_memory(name: str):
    """Get the signature of a memory."""
    try:
        return get_signature(name, "memories")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


@router.get("/tool")
def get_tool(name: str):
    """Get the signature of a tool."""
    try:
        return get_signature(name, "tools")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Tool not found") from exc
