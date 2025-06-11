from fastapi import APIRouter

from langflow.api.v2.files import router as files_router

router = APIRouter(prefix="/v2")
router.include_router(files_router)

__all__ = ["router"]
