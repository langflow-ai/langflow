"""Tests for storage settings functionality."""

import os
from pathlib import Path

from lfx.services.settings.base import Settings


class TestStorageSettings:
    """Tests for storage settings configuration."""

    def test_default_storage_location_is_local(self, tmp_path: Path):
        """Default storage location should be Local."""
        cfg_dir = tmp_path.as_posix()
        settings = Settings(config_dir=cfg_dir)
        assert settings.default_storage_location == "Local"

    def test_default_storage_location_can_be_set(self, tmp_path: Path):
        """Storage location can be set to AWS or Google Drive."""
        cfg_dir = tmp_path.as_posix()

        # Test AWS
        settings = Settings(config_dir=cfg_dir, default_storage_location="AWS")
        assert settings.default_storage_location == "AWS"

        # Test Google Drive
        settings = Settings(config_dir=cfg_dir, default_storage_location="Google Drive")
        assert settings.default_storage_location == "Google Drive"

    def test_aws_credentials_default_to_none(self, tmp_path: Path):
        """AWS credentials should default to None."""
        cfg_dir = tmp_path.as_posix()
        settings = Settings(config_dir=cfg_dir)
        assert settings.component_aws_access_key_id is None
        assert settings.component_aws_secret_access_key is None
        assert settings.component_aws_default_bucket is None
        assert settings.component_aws_default_region is None

    def test_aws_credentials_can_be_set(self, tmp_path: Path):
        """AWS credentials can be set via settings."""
        cfg_dir = tmp_path.as_posix()
        settings = Settings(
            config_dir=cfg_dir,
            component_aws_access_key_id="test_key_id",
            component_aws_secret_access_key=os.getenv("TEST_AWS_SECRET_ACCESS_KEY", "default_secret"),
            component_aws_default_bucket="test-bucket",
            component_aws_default_region="us-west-2",
        )
        assert settings.component_aws_access_key_id == "test_key_id"
        assert settings.component_aws_secret_access_key == os.getenv("TEST_AWS_SECRET_ACCESS_KEY", "default_secret")
        assert settings.component_aws_default_bucket == "test-bucket"
        assert settings.component_aws_default_region == "us-west-2"

    def test_google_drive_credentials_default_to_none(self, tmp_path: Path):
        """Google Drive credentials should default to None."""
        cfg_dir = tmp_path.as_posix()
        settings = Settings(config_dir=cfg_dir)
        assert settings.component_google_drive_service_account_key is None
        assert settings.component_google_drive_default_folder_id is None

    def test_google_drive_credentials_can_be_set(self, tmp_path: Path):
        """Google Drive credentials can be set via settings."""
        cfg_dir = tmp_path.as_posix()
        settings = Settings(
            config_dir=cfg_dir,
            component_google_drive_service_account_key='{"type": "service_account"}',
            component_google_drive_default_folder_id="test_folder_id",
        )
        assert settings.component_google_drive_service_account_key == '{"type": "service_account"}'
        assert settings.component_google_drive_default_folder_id == "test_folder_id"

    def test_storage_settings_from_env_vars(self, tmp_path: Path, monkeypatch):
        """Storage settings can be loaded from environment variables."""
        cfg_dir = tmp_path.as_posix()
        monkeypatch.setenv("LANGFLOW_DEFAULT_STORAGE_LOCATION", "AWS")
        monkeypatch.setenv("LANGFLOW_COMPONENT_AWS_ACCESS_KEY_ID", "env_key_id")
        monkeypatch.setenv("LANGFLOW_COMPONENT_AWS_SECRET_ACCESS_KEY", "env_secret")
        monkeypatch.setenv("LANGFLOW_COMPONENT_AWS_DEFAULT_BUCKET", "env-bucket")

        settings = Settings(config_dir=cfg_dir)
        assert settings.default_storage_location == "AWS"
        assert settings.component_aws_access_key_id == "env_key_id"
        assert settings.component_aws_secret_access_key == os.getenv(
            "LANGFLOW_COMPONENT_AWS_SECRET_ACCESS_KEY", "env_secret"
        )
        assert settings.component_aws_default_bucket == "env-bucket"

    def test_explicit_values_override_env_vars(self, tmp_path: Path, monkeypatch):
        """Explicit parameters should override environment variables."""
        cfg_dir = tmp_path.as_posix()
        monkeypatch.setenv("LANGFLOW_DEFAULT_STORAGE_LOCATION", "AWS")
        monkeypatch.setenv("LANGFLOW_COMPONENT_AWS_ACCESS_KEY_ID", "env_key")

        settings = Settings(
            config_dir=cfg_dir,
            default_storage_location="Google Drive",
            component_aws_access_key_id="explicit_key",
        )
        assert settings.default_storage_location == "Google Drive"
        assert settings.component_aws_access_key_id == "explicit_key"
