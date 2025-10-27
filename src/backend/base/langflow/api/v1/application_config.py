from fastapi import APIRouter, HTTPException

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.application_config import (
    ApplicationConfigRead,
    ApplicationConfigUpdate,
    get_config_by_key,
    upsert_config,
)

router = APIRouter(prefix="/application-config", tags=["Application Config"])


@router.get("/{key}", response_model=ApplicationConfigRead, status_code=200)
async def get_application_config(
    *,
    key: str,
    session: DbSession,
):
    """Get application configuration by key.

    Args:
        key: Configuration key (e.g., 'app-logo')
        session: Database session

    Returns:
        ApplicationConfigRead: Configuration object

    Raises:
        HTTPException: 404 if config not found
    """
    try:
        config = await get_config_by_key(session, key)
        if not config:
            raise HTTPException(status_code=404, detail=f"Configuration '{key}' not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{key}", response_model=ApplicationConfigRead, status_code=200)
async def update_application_config(
    *,
    key: str,
    update: ApplicationConfigUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
):
    """Update or create application configuration (upsert).

    Args:
        key: Configuration key (e.g., 'app-logo')
        update: Configuration update data
        current_user: Current authenticated user
        session: Database session

    Returns:
        ApplicationConfigRead: Updated/created configuration

    Raises:
        HTTPException: 400 if validation fails, 500 for server errors
    """
    try:
        if not update.value:
            raise HTTPException(status_code=400, detail="Configuration value cannot be empty")

        config = await upsert_config(
            session=session,
            key=key,
            value=update.value,
            updated_by=current_user.id,
            description=update.description,
        )
        return config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
