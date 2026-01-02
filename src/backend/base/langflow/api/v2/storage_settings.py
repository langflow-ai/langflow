from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
from langflow.services.deps import get_settings_service
from langflow.services.settings.service import SettingsService

router = APIRouter(tags=["Storage Settings"], prefix="/storage-settings")


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
    current_user: CurrentActiveUser,  # noqa: ARG001
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    """Get global storage settings for file components."""
    settings = settings_service.settings

    # Mask sensitive values for security
    masked_aws_secret = None
    if settings.component_aws_secret_access_key:
        masked_aws_secret = "*" * 8

    masked_gdrive_key = None
    if settings.component_google_drive_service_account_key:
        masked_gdrive_key = "*" * 8

    return StorageSettingsResponse(
        default_storage_location=settings.default_storage_location,
        component_aws_access_key_id=settings.component_aws_access_key_id,
        component_aws_secret_access_key=masked_aws_secret,
        component_aws_default_bucket=settings.component_aws_default_bucket,
        component_aws_default_region=settings.component_aws_default_region,
        component_google_drive_service_account_key=masked_gdrive_key,
        component_google_drive_default_folder_id=settings.component_google_drive_default_folder_id,
    )


@router.patch("", response_model=StorageSettingsResponse)
async def update_storage_settings(
    settings_update: StorageSettingsUpdate,
    current_user: CurrentActiveUser,  # noqa: ARG001
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    """Update global storage settings for file components."""
    settings = settings_service.settings

    # Determine the final storage location after update
    final_storage_location = (
        settings_update.default_storage_location
        if settings_update.default_storage_location is not None
        else settings.default_storage_location
    )

    # Validate AWS credentials if AWS is selected
    if final_storage_location == "AWS":
        # Check if we're updating credentials or if they already exist
        final_aws_key_id = (
            settings_update.component_aws_access_key_id
            if settings_update.component_aws_access_key_id is not None
            else settings.component_aws_access_key_id
        )
        final_aws_secret = settings.component_aws_secret_access_key
        if settings_update.component_aws_secret_access_key is not None and not all(
            c == "*" for c in settings_update.component_aws_secret_access_key
        ):
            final_aws_secret = settings_update.component_aws_secret_access_key

        final_aws_bucket = (
            settings_update.component_aws_default_bucket
            if settings_update.component_aws_default_bucket is not None
            else settings.component_aws_default_bucket
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
        final_gdrive_key = settings.component_google_drive_service_account_key
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

    # Update only provided fields
    if settings_update.default_storage_location is not None:
        settings.default_storage_location = settings_update.default_storage_location

    if settings_update.component_aws_access_key_id is not None:
        settings.component_aws_access_key_id = settings_update.component_aws_access_key_id

    # Only update secret if not masked (not just asterisks)
    if settings_update.component_aws_secret_access_key is not None and not all(
        c == "*" for c in settings_update.component_aws_secret_access_key
    ):
        settings.component_aws_secret_access_key = settings_update.component_aws_secret_access_key

    if settings_update.component_aws_default_bucket is not None:
        settings.component_aws_default_bucket = settings_update.component_aws_default_bucket

    if settings_update.component_aws_default_region is not None:
        settings.component_aws_default_region = settings_update.component_aws_default_region

    # Only update service account key if not masked
    if settings_update.component_google_drive_service_account_key is not None and not all(
        c == "*" for c in settings_update.component_google_drive_service_account_key
    ):
        settings.component_google_drive_service_account_key = settings_update.component_google_drive_service_account_key

    if settings_update.component_google_drive_default_folder_id is not None:
        settings.component_google_drive_default_folder_id = settings_update.component_google_drive_default_folder_id

    # Return masked values for security
    masked_aws_secret = None
    if settings.component_aws_secret_access_key:
        masked_aws_secret = "*" * 8

    masked_gdrive_key = None
    if settings.component_google_drive_service_account_key:
        masked_gdrive_key = "*" * 8

    return StorageSettingsResponse(
        default_storage_location=settings.default_storage_location,
        component_aws_access_key_id=settings.component_aws_access_key_id,
        component_aws_secret_access_key=masked_aws_secret,
        component_aws_default_bucket=settings.component_aws_default_bucket,
        component_aws_default_region=settings.component_aws_default_region,
        component_google_drive_service_account_key=masked_gdrive_key,
        component_google_drive_default_folder_id=settings.component_google_drive_default_folder_id,
    )
