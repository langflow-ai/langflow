from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.settings.service import SettingsService
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(tags=["Storage Settings"], prefix="/storage-settings")

# Storage settings are persisted as internal variables with this prefix
STORAGE_SETTINGS_PREFIX = "__storage_"


class StorageSettingsResponse(BaseModel):
    """Storage settings response model."""

    default_storage_location: str
    component_aws_access_key_id: str | None
    component_aws_secret_access_key: str | None
    component_aws_default_bucket: str | None
    component_aws_default_region: str | None
    component_google_drive_service_account_key: str | None
    component_google_drive_default_folder_id: str | None


class StorageSettingsUpdate(BaseModel):
    """Storage settings update model."""

    default_storage_location: str | None = None
    component_aws_access_key_id: str | None = None
    component_aws_secret_access_key: str | None = None
    component_aws_default_bucket: str | None = None
    component_aws_default_region: str | None = None
    component_google_drive_service_account_key: str | None = None
    component_google_drive_default_folder_id: str | None = None


@router.get("", response_model=StorageSettingsResponse)
async def get_storage_settings(
    current_user: CurrentActiveUser,
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    """Get global storage settings for file components.

    Settings are loaded from database variables (persisted) with fallback to
    in-memory settings and environment variables.
    """
    async with session_scope() as session:
        variable_service = DatabaseVariableService(settings_service)

        # Helper to get variable value with fallback to settings
        async def get_setting(var_name: str, setting_attr: str) -> str | None:
            try:
                var = await variable_service.get_variable_object(
                    user_id=current_user.id, name=f"{STORAGE_SETTINGS_PREFIX}{var_name}", session=session
                )
                # Decrypt the value
                from langflow.services.auth import utils as auth_utils

                return auth_utils.decrypt_api_key(var.value, settings_service=settings_service)
            except ValueError:
                # Variable not found in DB, use in-memory setting
                return getattr(settings_service.settings, setting_attr)

        # Load settings from database or fallback to in-memory
        default_storage_location = await get_setting("default_storage_location", "default_storage_location") or "Local"
        aws_access_key_id = await get_setting("component_aws_access_key_id", "component_aws_access_key_id")
        aws_secret_access_key = await get_setting("component_aws_secret_access_key", "component_aws_secret_access_key")
        aws_default_bucket = await get_setting("component_aws_default_bucket", "component_aws_default_bucket")
        aws_default_region = await get_setting("component_aws_default_region", "component_aws_default_region")
        gdrive_service_account_key = await get_setting(
            "component_google_drive_service_account_key", "component_google_drive_service_account_key"
        )
        gdrive_default_folder_id = await get_setting(
            "component_google_drive_default_folder_id", "component_google_drive_default_folder_id"
        )

        # Mask sensitive values for security
        masked_aws_secret = "*" * 8 if aws_secret_access_key else None
        masked_gdrive_key = "*" * 8 if gdrive_service_account_key else None

        return StorageSettingsResponse(
            default_storage_location=default_storage_location,
            component_aws_access_key_id=aws_access_key_id,
            component_aws_secret_access_key=masked_aws_secret,
            component_aws_default_bucket=aws_default_bucket,
            component_aws_default_region=aws_default_region,
            component_google_drive_service_account_key=masked_gdrive_key,
            component_google_drive_default_folder_id=gdrive_default_folder_id,
        )


@router.patch("", response_model=StorageSettingsResponse)
async def update_storage_settings(
    settings_update: StorageSettingsUpdate,
    current_user: CurrentActiveUser,
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    """Update global storage settings for file components.

    Settings are persisted to the database and will survive restarts.
    """
    from langflow.services.auth import utils as auth_utils

    async with session_scope() as session:
        variable_service = DatabaseVariableService(settings_service)

        # Helper to get current value from DB or fallback to in-memory
        async def get_current_value(var_name: str, setting_attr: str) -> str | None:
            try:
                var = await variable_service.get_variable_object(
                    user_id=current_user.id, name=f"{STORAGE_SETTINGS_PREFIX}{var_name}", session=session
                )
                return auth_utils.decrypt_api_key(var.value, settings_service=settings_service)
            except ValueError:
                return getattr(settings_service.settings, setting_attr)

        # Determine the final storage location after update
        final_storage_location = (
            settings_update.default_storage_location
            if settings_update.default_storage_location is not None
            else await get_current_value("default_storage_location", "default_storage_location") or "Local"
        )

        # Validate AWS credentials if AWS is selected
        if final_storage_location == "AWS":
            # Check if we're updating credentials or if they already exist
            final_aws_key_id = (
                settings_update.component_aws_access_key_id
                if settings_update.component_aws_access_key_id is not None
                else await get_current_value("component_aws_access_key_id", "component_aws_access_key_id")
            )
            final_aws_secret = await get_current_value(
                "component_aws_secret_access_key", "component_aws_secret_access_key"
            )
            if settings_update.component_aws_secret_access_key is not None and not all(
                c == "*" for c in settings_update.component_aws_secret_access_key
            ):
                final_aws_secret = settings_update.component_aws_secret_access_key

            final_aws_bucket = (
                settings_update.component_aws_default_bucket
                if settings_update.component_aws_default_bucket is not None
                else await get_current_value("component_aws_default_bucket", "component_aws_default_bucket")
            )

            # Validate required AWS fields
            if not final_aws_key_id:
                raise HTTPException(
                    status_code=400,
                    detail="AWS Access Key ID is required when AWS storage is selected",
                )
            if not final_aws_secret:
                raise HTTPException(
                    status_code=400,
                    detail="AWS Secret Access Key is required when AWS storage is selected",
                )
            if not final_aws_bucket:
                raise HTTPException(
                    status_code=400,
                    detail="AWS Default Bucket is required when AWS storage is selected",
                )

        # Validate Google Drive credentials if Google Drive is selected
        if final_storage_location == "Google Drive":
            # Check if we're updating credentials or if they already exist
            final_gdrive_key = await get_current_value(
                "component_google_drive_service_account_key", "component_google_drive_service_account_key"
            )
            if settings_update.component_google_drive_service_account_key is not None and not all(
                c == "*" for c in settings_update.component_google_drive_service_account_key
            ):
                final_gdrive_key = settings_update.component_google_drive_service_account_key

            # Validate required Google Drive fields
            if not final_gdrive_key:
                raise HTTPException(
                    status_code=400,
                    detail="Google Drive Service Account Key is required when Google Drive storage is selected",
                )

        # Helper to create or update a variable in database
        async def save_setting(var_name: str, value: str) -> None:
            full_var_name = f"{STORAGE_SETTINGS_PREFIX}{var_name}"
            try:
                # Try to update existing
                await variable_service.update_variable(
                    user_id=current_user.id, name=full_var_name, value=value, session=session
                )
            except ValueError:
                # Variable doesn't exist, create it
                await variable_service.create_variable(
                    user_id=current_user.id,
                    name=full_var_name,
                    value=value,
                    type_=CREDENTIAL_TYPE,
                    session=session,
                )

        # Persist updates to database
        if settings_update.default_storage_location is not None:
            await save_setting("default_storage_location", settings_update.default_storage_location)

        if settings_update.component_aws_access_key_id is not None:
            await save_setting("component_aws_access_key_id", settings_update.component_aws_access_key_id)

        # Only update secret if not masked (not just asterisks)
        if settings_update.component_aws_secret_access_key is not None and not all(
            c == "*" for c in settings_update.component_aws_secret_access_key
        ):
            await save_setting("component_aws_secret_access_key", settings_update.component_aws_secret_access_key)

        if settings_update.component_aws_default_bucket is not None:
            await save_setting("component_aws_default_bucket", settings_update.component_aws_default_bucket)

        if settings_update.component_aws_default_region is not None:
            await save_setting("component_aws_default_region", settings_update.component_aws_default_region)

        # Only update service account key if not masked
        if settings_update.component_google_drive_service_account_key is not None and not all(
            c == "*" for c in settings_update.component_google_drive_service_account_key
        ):
            await save_setting(
                "component_google_drive_service_account_key", settings_update.component_google_drive_service_account_key
            )

        if settings_update.component_google_drive_default_folder_id is not None:
            await save_setting(
                "component_google_drive_default_folder_id",
                settings_update.component_google_drive_default_folder_id,
            )

        # Commit the transaction
        await session.commit()

        # Get final values for response
        final_aws_access_key_id = await get_current_value("component_aws_access_key_id", "component_aws_access_key_id")
        final_aws_secret_access_key = await get_current_value(
            "component_aws_secret_access_key", "component_aws_secret_access_key"
        )
        final_aws_default_bucket = await get_current_value(
            "component_aws_default_bucket", "component_aws_default_bucket"
        )
        final_aws_default_region = await get_current_value(
            "component_aws_default_region", "component_aws_default_region"
        )
        final_gdrive_service_account_key = await get_current_value(
            "component_google_drive_service_account_key", "component_google_drive_service_account_key"
        )
        final_gdrive_default_folder_id = await get_current_value(
            "component_google_drive_default_folder_id", "component_google_drive_default_folder_id"
        )

        # Return masked values for security
        masked_aws_secret = "*" * 8 if final_aws_secret_access_key else None
        masked_gdrive_key = "*" * 8 if final_gdrive_service_account_key else None

        return StorageSettingsResponse(
            default_storage_location=final_storage_location,
            component_aws_access_key_id=final_aws_access_key_id,
            component_aws_secret_access_key=masked_aws_secret,
            component_aws_default_bucket=final_aws_default_bucket,
            component_aws_default_region=final_aws_default_region,
            component_google_drive_service_account_key=masked_gdrive_key,
            component_google_drive_default_folder_id=final_gdrive_default_folder_id,
        )
