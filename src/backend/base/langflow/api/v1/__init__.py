from fastapi import APIRouter

from langflow.api.v1.api_key import router as api_key_router
from langflow.api.v1.chat import router as chat_router
from langflow.api.v1.endpoints import router as endpoints_router
from langflow.api.v1.files import router as files_router
from langflow.api.v1.flows import router as flows_router
from langflow.api.v1.folders import router as folders_router
from langflow.api.v1.login import router as login_router
from langflow.api.v1.mcp import router as mcp_router
from langflow.api.v1.mcp_projects import router as mcp_projects_router
from langflow.api.v1.monitor import router as monitor_router
from langflow.api.v1.projects import router as projects_router
from langflow.api.v1.starter_projects import router as starter_projects_router
from langflow.api.v1.store import router as store_router
from langflow.api.v1.users import router as users_router
from langflow.api.v1.validate import router as validate_router
from langflow.api.v1.variable import router as variables_router
from langflow.api.v1.voice_mode import router as voice_mode_router

router = APIRouter(prefix="/v1")
router.include_router(api_key_router)
router.include_router(chat_router)
router.include_router(endpoints_router)
router.include_router(files_router)
router.include_router(flows_router)
router.include_router(folders_router)
router.include_router(login_router)
router.include_router(mcp_projects_router)
router.include_router(mcp_router)
router.include_router(monitor_router)
router.include_router(projects_router)
router.include_router(starter_projects_router)
router.include_router(store_router)
router.include_router(users_router)
router.include_router(validate_router)
router.include_router(variables_router)
router.include_router(voice_mode_router)


__all__ = ["router"]
