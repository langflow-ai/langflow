# Router for base api
from fastapi import APIRouter
from langflow.api.v1 import chat_router, endpoints_router, validate_router

router = APIRouter(prefix="/api/v1", tags=["api"])
router.include_router(chat_router)
router.include_router(endpoints_router)
router.include_router(validate_router)
