# Router for base api
from fastapi import APIRouter

from langflow_api.api.v2 import (
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
router_v1.include_router(mcp_projects_router)

# router_v2.include_router(files_router_v2) # TODO: Add v2 files router? 

# TODO: just have single api router - consolidate files
router.include_router(router_v1)
router.include_router(router_v2)
