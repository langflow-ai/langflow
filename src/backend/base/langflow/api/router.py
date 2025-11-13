# Router for base api
from fastapi import APIRouter

from langflow.api.v1 import (
    agent_builder_router,
    agent_marketplace_router,
    api_key_router,
    application_config_router,
    auth_proxy_router,
    chat_router,
    endpoints_router,
    files_router,
    flexstore_router,
    flows_router,
    folders_router,
    knowledge_bases_router,
    login_router,
    mcp_projects_router,
    mcp_router,
    models_router,
    monitor_router,
    openai_responses_router,
    projects_router,
    published_flows_router,
    spec_router,
    starter_projects_router,
    store_router,
    users_router,
    validate_router,
    variables_router,
    vector_db_router,
    spec_flow_builder_router,
)
from langflow.api.v1.voice_mode import router as voice_mode_router
from langflow.api.v2 import files_router as files_router_v2
from langflow.api.v2 import mcp_router as mcp_router_v2

router_v1 = APIRouter(
    prefix="/v1",
)

router_v2 = APIRouter(
    prefix="/v2",
)

router_v1.include_router(agent_builder_router)
router_v1.include_router(agent_marketplace_router)
router_v1.include_router(api_key_router)
router_v1.include_router(application_config_router)
router_v1.include_router(auth_proxy_router)
router_v1.include_router(chat_router)
router_v1.include_router(endpoints_router)
router_v1.include_router(files_router)
router_v1.include_router(spec_flow_builder_router)
router_v1.include_router(flexstore_router)
router_v1.include_router(flows_router)
router_v1.include_router(folders_router)
router_v1.include_router(knowledge_bases_router)
router_v1.include_router(login_router)
router_v1.include_router(mcp_projects_router)
router_v1.include_router(mcp_router)
router_v1.include_router(models_router)
router_v1.include_router(monitor_router)
router_v1.include_router(openai_responses_router)
router_v1.include_router(projects_router)
router_v1.include_router(published_flows_router)
router_v1.include_router(spec_router)
router_v1.include_router(starter_projects_router)
router_v1.include_router(store_router)
router_v1.include_router(users_router)
router_v1.include_router(validate_router)
router_v1.include_router(variables_router)
router_v1.include_router(vector_db_router)
router_v1.include_router(voice_mode_router)

router_v2.include_router(files_router_v2)
router_v2.include_router(mcp_router_v2)

router = APIRouter(
    prefix="/api",
)
router.include_router(router_v1)
router.include_router(router_v2)
