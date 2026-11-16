"""Only active superusers may preview or apply selected repairs."""

from typing import Annotated

from fastapi import APIRouter, Depends

from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.user.model import User
from langflow.services.flow_repair.models import RepairApplyRequest, RepairBatchResult, RepairPreviewRequest
from langflow.services.flow_repair.service import apply_repairs, preview_repairs

router = APIRouter(prefix="/upgrade-repairs", tags=["Upgrade repairs"])
Superuser = Annotated[User, Depends(get_current_active_superuser)]


@router.post("/preview")
async def preview_selected(payload: RepairPreviewRequest, admin: Superuser) -> RepairBatchResult:
    return await preview_repairs(payload, admin.id)


@router.post("/apply")
async def apply_selected(payload: RepairApplyRequest, admin: Superuser) -> RepairBatchResult:
    return await apply_repairs(payload, admin.id)
