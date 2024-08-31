# Router for base api
from fastapi import APIRouter

from langflow.api.v1 import (
    api_key_router,
    chat_router,
    endpoints_router,
    files_router,
    flows_router,
    folders_router,
    login_router,
    mcp_router,
    monitor_router,
    starter_projects_router,
    store_router,
    tasks_router,
    users_router,
    validate_router,
    variables_router,
)
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/api/v1")

routers = [
    chat_router,
    endpoints_router,
    validate_router,
    store_router,
    flows_router,
    users_router,
    api_key_router,
    login_router,
    variables_router,
    files_router,
    monitor_router,
    folders_router,
    starter_projects_router,
    tasks_router,
]


if get_settings_service().settings.mcp_server_enabled:
    routers.append(mcp_router)

for sub_router in routers:
    router.include_router(sub_router)
