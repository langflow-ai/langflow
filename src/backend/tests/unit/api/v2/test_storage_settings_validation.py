"""Tests for storage settings validation."""

import pytest
from fastapi import HTTPException

from langflow.api.v2.storage_settings import StorageSettingsUpdate, update_storage_settings
from langflow.services.settings.service import SettingsService
from lfx.services.settings.auth import AuthSettings
from lfx.services.settings.base import Settings


@pytest.fixture
def settings_service(tmp_path):
    """Create a settings service with temporary config."""
    cfg_dir = tmp_path.as_posix()
    settings = Settings(config_dir=cfg_dir)
    auth_settings = AuthSettings(CONFIG_DIR=cfg_dir)
    service = SettingsService(settings, auth_settings)
    return service


@pytest.fixture
def mock_user():
    """Create a mock user."""
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = "test-user-id"
    return user


@pytest.mark.asyncio
async def test_validation_fails_when_switching_to_aws_without_credentials(settings_service, mock_user):
    """Test that validation fails when switching to AWS without providing credentials."""
    settings_update = StorageSettingsUpdate(default_storage_location="AWS")

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "AWS Access Key ID is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validation_fails_when_switching_to_aws_with_only_key_id(settings_service, mock_user):
    """Test that validation fails when switching to AWS with only access key ID."""
    settings_update = StorageSettingsUpdate(
        default_storage_location="AWS", component_aws_access_key_id="test-key-id"
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "AWS Secret Access Key is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validation_fails_when_switching_to_aws_without_bucket(settings_service, mock_user):
    """Test that validation fails when switching to AWS without bucket."""
    settings_update = StorageSettingsUpdate(
        default_storage_location="AWS",
        component_aws_access_key_id="test-key-id",
        component_aws_secret_access_key="test-secret",
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "AWS Default Bucket is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validation_passes_when_switching_to_aws_with_all_credentials(settings_service, mock_user):
    """Test that validation passes when switching to AWS with all credentials."""
    settings_update = StorageSettingsUpdate(
        default_storage_location="AWS",
        component_aws_access_key_id="test-key-id",
        component_aws_secret_access_key="test-secret",
        component_aws_default_bucket="test-bucket",
    )

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.default_storage_location == "AWS"
    assert response.component_aws_access_key_id == "test-key-id"
    assert response.component_aws_secret_access_key == "********"  # Masked
    assert response.component_aws_default_bucket == "test-bucket"


@pytest.mark.asyncio
async def test_validation_fails_when_switching_to_google_drive_without_credentials(settings_service, mock_user):
    """Test that validation fails when switching to Google Drive without credentials."""
    settings_update = StorageSettingsUpdate(default_storage_location="Google Drive")

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "Google Drive Service Account Key is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validation_passes_when_switching_to_google_drive_with_credentials(settings_service, mock_user):
    """Test that validation passes when switching to Google Drive with credentials."""
    settings_update = StorageSettingsUpdate(
        default_storage_location="Google Drive",
        component_google_drive_service_account_key='{"type": "service_account"}',
    )

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.default_storage_location == "Google Drive"
    assert response.component_google_drive_service_account_key == "********"  # Masked


@pytest.mark.asyncio
async def test_validation_passes_when_staying_on_local(settings_service, mock_user):
    """Test that validation passes when staying on Local (no credentials needed)."""
    settings_update = StorageSettingsUpdate(default_storage_location="Local")

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.default_storage_location == "Local"


@pytest.mark.asyncio
async def test_validation_passes_when_aws_already_configured(settings_service, mock_user):
    """Test that validation passes when AWS is already configured and not changing storage."""
    # Pre-configure AWS settings
    settings_service.settings.default_storage_location = "AWS"
    settings_service.settings.component_aws_access_key_id = "existing-key-id"
    settings_service.settings.component_aws_secret_access_key = "existing-secret"
    settings_service.settings.component_aws_default_bucket = "existing-bucket"

    # Update region only, keeping AWS as storage location
    settings_update = StorageSettingsUpdate(component_aws_default_region="us-west-2")

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.default_storage_location == "AWS"
    assert response.component_aws_default_region == "us-west-2"


@pytest.mark.asyncio
async def test_validation_passes_when_updating_credentials_without_changing_storage(settings_service, mock_user):
    """Test that validation passes when updating credentials without changing storage location."""
    # Pre-configure AWS settings
    settings_service.settings.default_storage_location = "AWS"
    settings_service.settings.component_aws_access_key_id = "old-key-id"
    settings_service.settings.component_aws_secret_access_key = "old-secret"
    settings_service.settings.component_aws_default_bucket = "old-bucket"

    # Update bucket only
    settings_update = StorageSettingsUpdate(component_aws_default_bucket="new-bucket")

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.component_aws_default_bucket == "new-bucket"


@pytest.mark.asyncio
async def test_validation_fails_when_clearing_required_aws_credential(settings_service, mock_user):
    """Test that validation fails when clearing a required AWS credential."""
    # Pre-configure AWS settings
    settings_service.settings.default_storage_location = "AWS"
    settings_service.settings.component_aws_access_key_id = "existing-key-id"
    settings_service.settings.component_aws_secret_access_key = "existing-secret"
    settings_service.settings.component_aws_default_bucket = "existing-bucket"

    # Try to clear the bucket
    settings_update = StorageSettingsUpdate(component_aws_default_bucket="")

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "AWS Default Bucket is required" in exc_info.value.detail
