from fastapi import APIRouter
from typing import Dict, Any

from langflow.api.v1 import (
    ai_agent_router,
    api_key_router,
    chat_router,
    endpoints_router,
    files_router,
    flows_router,
    folders_router,
    login_router,
    mcp_projects_router,
    mcp_router,
    monitor_router,
    projects_router,
    starter_projects_router,
    store_router,
    users_router,
    validate_router,
    variables_router,
    voice_mode_router,
)
from langflow.api.v2 import files_router as files_router_v2
# Remove direct monkey_agent import to avoid circular imports

router = APIRouter(
    prefix="/api",
)

router_v1 = APIRouter(
    prefix="/v1",
)

router_v2 = APIRouter(
    prefix="/v2",
)

router_v1.include_router(chat_router)
router_v1.include_router(endpoints_router)
router_v1.include_router(validate_router)
router_v1.include_router(store_router)
router_v1.include_router(flows_router)
router_v1.include_router(users_router)
router_v1.include_router(api_key_router)
router_v1.include_router(login_router)
router_v1.include_router(variables_router)
router_v1.include_router(files_router)
router_v1.include_router(monitor_router)
router_v1.include_router(folders_router)
router_v1.include_router(projects_router)
router_v1.include_router(starter_projects_router)
router_v1.include_router(voice_mode_router)
router_v1.include_router(mcp_router)
router_v1.include_router(ai_agent_router)
router_v1.include_router(mcp_projects_router)

# Create a simple direct endpoint to test monkey-agent functionality
@router_v1.get("/monkey-agent/test", tags=["Monkey Agent"])
async def test_monkey_agent() -> Dict[str, Any]:
    """
    Simple test endpoint for the monkey agent
    """
    return {"status": "ok", "message": "Monkey agent test endpoint is working!"}

# Handle monkey_agent router directly to avoid circular imports
try:
    # Import at runtime to avoid circular imports
    import sys
    sys.path.append("/Users/happy/CascadeProjects/langflow-fork/src/backend")
    from langflow.monkey_agent.api import router as monkey_agent_router
    
    # The router already has the complete path prefix, so we include it at the root level
    # instead of with router_v1 to avoid double prefixing
    router.include_router(monkey_agent_router)
except ImportError as e:
    print(f"Warning: Could not import monkey_agent module: {e}")
    # Continue without the monkey_agent router

router_v2.include_router(files_router_v2)

router.include_router(router_v1)
router.include_router(router_v2)
