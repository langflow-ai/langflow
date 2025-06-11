# Router for base api
from fastapi import APIRouter

from langflow.api.v1 import router as router_v1
from langflow.api.v2 import router as router_v2

router = APIRouter(
    prefix="/api",
)

router.include_router(router_v1)
router.include_router(router_v2)
