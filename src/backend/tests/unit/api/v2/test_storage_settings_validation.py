"""Tests for storage settings validation."""

import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

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
    return SettingsService(settings, auth_settings)


@pytest.fixture
def mock_user():
    """Create a mock user."""
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = uuid4()
    return user


@pytest.fixture
def mock_session_scope():
    """Mock the session_scope context manager and variable service methods."""
    with patch("langflow.api.v2.storage_settings.session_scope") as mock_scope, \
         patch("langflow.api.v2.storage_settings.DatabaseVariableService") as mock_var_service_class, \
         patch("langflow.services.auth.utils.encrypt_api_key") as mock_encrypt, \
         patch("langflow.services.auth.utils.decrypt_api_key") as mock_decrypt:

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_scope.return_value.__aenter__.return_value = mock_session

        # Store saved values
        saved_variables = {}

        # Mock encryption/decryption to just return the value
        mock_encrypt.side_effect = lambda value, **kwargs: value  # noqa: ARG005
        mock_decrypt.side_effect = lambda value, **kwargs: value  # noqa: ARG005

        # Mock get_variable_object to return saved values or raise ValueError
        async def mock_get_variable(user_id, name, session):  # noqa: ARG001
            if name in saved_variables:
                var = AsyncMock()
                var.value = saved_variables[name]
                return var
            msg = f"{name} variable not found"
            raise ValueError(msg)

        # Mock update_variable to save values
        async def mock_update_variable(user_id, name, value, session):  # noqa: ARG001
            if name not in saved_variables:
                msg = f"{name} variable not found"
                raise ValueError(msg)
            saved_variables[name] = value

        # Mock create_variable to save values
        async def mock_create_variable(user_id, name, value, type_, session):  # noqa: ARG001
            saved_variables[name] = value

        # Mock the variable service instance
        mock_var_service = AsyncMock()
        mock_var_service.get_variable_object = mock_get_variable
        mock_var_service.update_variable = mock_update_variable
        mock_var_service.create_variable = mock_create_variable
        mock_var_service_class.return_value = mock_var_service

        yield mock_scope


@pytest.mark.asyncio
async def test_validation_fails_when_switching_to_aws_without_credentials(
    mock_session_scope, settings_service, mock_user  # noqa: ARG001
):
    """Test that validation fails when switching to AWS without providing credentials."""
    settings_update = StorageSettingsUpdate(default_storage_location="AWS")

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "AWS Access Key ID is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validation_fails_when_switching_to_aws_with_only_key_id(mock_session_scope, settings_service, mock_user):  # noqa: ARG001
    """Test that validation fails when switching to AWS with only access key ID."""
    settings_update = StorageSettingsUpdate(default_storage_location="AWS", component_aws_access_key_id="test-key-id")

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "AWS Secret Access Key is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validation_fails_when_switching_to_aws_without_bucket(mock_session_scope, settings_service, mock_user):  # noqa: ARG001
    """Test that validation fails when switching to AWS without bucket."""
    settings_update = StorageSettingsUpdate(
        default_storage_location="AWS",
        component_aws_access_key_id="test-key-id",
        component_aws_secret_access_key=os.getenv("TEST_AWS_SECRET_ACCESS_KEY", "default-secret"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "AWS Default Bucket is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validation_passes_when_switching_to_aws_with_all_credentials(
    mock_session_scope, settings_service, mock_user  # noqa: ARG001
):
    """Test that validation passes when switching to AWS with all credentials."""
    settings_update = StorageSettingsUpdate(
        default_storage_location="AWS",
        component_aws_access_key_id="test-key-id",
        component_aws_secret_access_key=os.getenv("TEST_AWS_SECRET_ACCESS_KEY", "default-secret"),
        component_aws_default_bucket="test-bucket",
    )

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.default_storage_location == "AWS"
    assert response.component_aws_access_key_id == "test-key-id"
    # Assert that the AWS secret access key is masked for security purposes
    # The value "********" is a placeholder for a masked AWS secret access key, not a hardcoded password.
    assert response.component_aws_secret_access_key == "********"  # Masked  # noqa: S105
    assert response.component_aws_default_bucket == "test-bucket"


@pytest.mark.asyncio
async def test_validation_fails_when_switching_to_google_drive_without_credentials(
    mock_session_scope, settings_service, mock_user  # noqa: ARG001
):
    """Test that validation fails when switching to Google Drive without credentials."""
    settings_update = StorageSettingsUpdate(default_storage_location="Google Drive")

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "Google Drive Service Account Key is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validation_passes_when_switching_to_google_drive_with_credentials(
    mock_session_scope, settings_service, mock_user  # noqa: ARG001
):
    """Test that validation passes when switching to Google Drive with credentials."""
    settings_update = StorageSettingsUpdate(
        default_storage_location="Google Drive",
        component_google_drive_service_account_key='{"type": "service_account"}',
    )

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.default_storage_location == "Google Drive"
    assert response.component_google_drive_service_account_key == "********"  # Masked


@pytest.mark.asyncio
async def test_validation_passes_when_staying_on_local(mock_session_scope, settings_service, mock_user):  # noqa: ARG001
    """Test that validation passes when staying on Local (no credentials needed)."""
    settings_update = StorageSettingsUpdate(default_storage_location="Local")

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.default_storage_location == "Local"


@pytest.mark.asyncio
async def test_validation_passes_when_aws_already_configured(mock_session_scope, settings_service, mock_user):  # noqa: ARG001
    """Test that validation passes when AWS is already configured and not changing storage."""
    # Pre-configure AWS settings
    settings_service.settings.default_storage_location = "AWS"
    settings_service.settings.component_aws_access_key_id = "existing-key-id"
    settings_service.settings.component_aws_secret_access_key = os.getenv(
        "TEST_AWS_SECRET_ACCESS_KEY", "default-secret"
    )
    settings_service.settings.component_aws_default_bucket = "existing-bucket"

    # Update region only, keeping AWS as storage location
    settings_update = StorageSettingsUpdate(component_aws_default_region="us-west-2")

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.default_storage_location == "AWS"
    assert response.component_aws_default_region == "us-west-2"


@pytest.mark.asyncio
async def test_validation_passes_when_updating_credentials_without_changing_storage(
    mock_session_scope, settings_service, mock_user  # noqa: ARG001
):
    """Test that validation passes when updating credentials without changing storage location."""
    # Pre-configure AWS settings
    settings_service.settings.default_storage_location = "AWS"
    settings_service.settings.component_aws_access_key_id = "old-key-id"
    settings_service.settings.component_aws_secret_access_key = os.getenv(
        "TEST_OLD_AWS_SECRET_ACCESS_KEY", "default-old-secret"
    )
    settings_service.settings.component_aws_default_bucket = "old-bucket"

    # Update bucket only
    settings_update = StorageSettingsUpdate(component_aws_default_bucket="new-bucket")

    response = await update_storage_settings(settings_update, mock_user, settings_service)

    assert response.component_aws_default_bucket == "new-bucket"


@pytest.mark.asyncio
async def test_validation_fails_when_clearing_required_aws_credential(mock_session_scope, settings_service, mock_user):  # noqa: ARG001
    """Test that validation fails when clearing a required AWS credential."""
    # Pre-configure AWS settings
    settings_service.settings.default_storage_location = "AWS"
    settings_service.settings.component_aws_access_key_id = "existing-key-id"
    settings_service.settings.component_aws_secret_access_key = os.getenv(
        "EXISTING_AWS_SECRET_ACCESS_KEY", "default-secret"
    )
    settings_service.settings.component_aws_default_bucket = "existing-bucket"

    # Try to clear the bucket
    settings_update = StorageSettingsUpdate(component_aws_default_bucket="")

    with pytest.raises(HTTPException) as exc_info:
        await update_storage_settings(settings_update, mock_user, settings_service)

    assert exc_info.value.status_code == 400
    assert "AWS Default Bucket is required" in exc_info.value.detail
