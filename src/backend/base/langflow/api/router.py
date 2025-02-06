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
    monitor_router,
    starter_projects_router,
    store_router,
    users_router,
    validate_router,
    variables_router,
)
from langflow.api.v2 import files_router as files_router_v2

router = APIRouter(
    prefix="/api/v1",
)

router_v2 = APIRouter(
    prefix="/api/v2",
)

router.include_router(chat_router)
router.include_router(endpoints_router)
router.include_router(validate_router)
router.include_router(store_router)
router.include_router(flows_router)
router.include_router(users_router)
router.include_router(api_key_router)
router.include_router(login_router)
router.include_router(variables_router)
router.include_router(files_router)
router.include_router(monitor_router)
router.include_router(folders_router)
router.include_router(starter_projects_router)

router_v2.include_router(files_router_v2)
