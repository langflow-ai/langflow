# Router for base api
from fastapi import APIRouter
from langflow.api.v1 import (
    chat_router,
    endpoints_router,
    validate_router,
    flows_router,
    component_router,
    users_router,
    api_key_router,
    login_router,
)

router = APIRouter(
    prefix="/api/v1",
)
router.include_router(chat_router)
router.include_router(endpoints_router)
router.include_router(validate_router)
router.include_router(component_router)
router.include_router(flows_router)
router.include_router(users_router)
router.include_router(api_key_router)
router.include_router(login_router)
