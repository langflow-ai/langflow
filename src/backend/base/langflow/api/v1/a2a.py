from fastapi import APIRouter, HTTPException, Depends
from langflow.services.deps import get_a2a_service

router = APIRouter(prefix="/a2a", tags=["A2A"])

@router.get("/{flow_id}/{component_id}/.well-known/agent.json")
async def get_agent_card(flow_id: str, component_id: str, a2a_service = Depends(get_a2a_service)):
    card = a2a_service.get_agent_card(flow_id, component_id)
    if not card:
        raise HTTPException(status_code=404, detail="Agent card not found")
    return card

@router.post("/{flow_id}/{component_id}/rpc")
async def rpc_endpoint(flow_id: str, component_id: str, payload: dict, a2a_service = Depends(get_a2a_service)):
    # Mock JSON-RPC 2.0 execution
    method = payload.get("method")
    if method == "message/send":
        return {"jsonrpc": "2.0", "result": {"message": {"role": "assistant", "parts": [{"kind": "text", "text": "A2A Response"}]}}, "id": payload.get("id")}
    raise HTTPException(status_code=400, detail="Method not supported")
