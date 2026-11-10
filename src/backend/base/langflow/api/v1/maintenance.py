"""Maintenance controls remain available while ordinary writes are frozen."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.utils.migration_pause import is_paused
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.maintenance import REASON_MAX_LENGTH
from langflow.services.database.models.user.model import User
from langflow.services.maintenance.state import MaintenanceStatus, maintenance_status, set_maintenance

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])
Superuser = Annotated[User, Depends(get_current_active_superuser)]


class MaintenanceRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)


class MaintenanceRead(MaintenanceStatus):
    paused: bool
    migration: bool


<<<<<<< HEAD
async def _read(session: DbSessionReadOnly, *, include_details: bool = True) -> MaintenanceRead:
    state = await maintenance_status(session, include_details=include_details)
=======
async def _read(session: DbSessionReadOnly) -> MaintenanceRead:
    state = await maintenance_status(session)
>>>>>>> origin/release-1.14.0
    migration = is_paused()
    return MaintenanceRead(**state.model_dump(), paused=state.maintenance or migration, migration=migration)


@router.get("/status")
<<<<<<< HEAD
async def read_status(user: CurrentActiveUser, session: DbSessionReadOnly) -> MaintenanceRead:
    return await _read(session, include_details=user.is_superuser)
=======
async def read_status(_user: CurrentActiveUser, session: DbSessionReadOnly) -> MaintenanceRead:
    return await _read(session)
>>>>>>> origin/release-1.14.0


@router.post("/on")
async def enable_maintenance(payload: MaintenanceRequest, admin: Superuser, session: DbSession) -> MaintenanceRead:
    await set_maintenance(session, enabled=True, reason=payload.reason, actor_id=admin.id)
    return await _read(session)


@router.post("/off")
async def disable_maintenance(admin: Superuser, session: DbSession) -> MaintenanceRead:
    await set_maintenance(session, enabled=False, actor_id=admin.id)
    return await _read(session)
