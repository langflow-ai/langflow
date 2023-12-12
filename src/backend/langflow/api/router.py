# Router for base api
from fastapi import APIRouter

from langflow.api.v1 import (
    api_key_router,
    chat_router,
    credentials_router,
    endpoints_router,
    flows_router,
    login_router,
    store_router,
    users_router,
    validate_router,
)

router = APIRouter(
    prefix="/api/v1",
)
router.include_router(chat_router)
router.include_router(endpoints_router)
router.include_router(validate_router)
router.include_router(store_router)
router.include_router(flows_router)
router.include_router(users_router)
router.include_router(api_key_router)
router.include_router(login_router)
router.include_router(credentials_router)
