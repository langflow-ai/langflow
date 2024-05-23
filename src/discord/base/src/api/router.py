# Router for base api
from fastapi import APIRouter

from .v1 import router as discord_router

router = APIRouter(
    prefix="/api/v1",
)

router.include_router(discord_router)
