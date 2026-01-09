"""Mixin class for components that use global storage settings."""

from typing import Any

from lfx.inputs import SortableListInput
from lfx.io import BoolInput
from lfx.services.deps import get_settings_service
from lfx.utils.validate_cloud import is_astra_cloud_environment


def _get_storage_location_options():
    """Get storage location options, filtering out Local if in Astra cloud environment."""
    all_options = [{"name": "AWS", "icon": "Amazon"}, {"name": "Google Drive", "icon": "google"}]
    if is_astra_cloud_environment():
        return all_options
    return [{"name": "Local", "icon": "hard-drive"}, *all_options]


class StorageSettingsMixin:
    """Mixin class providing global storage settings support for file components.

    This mixin adds:
    - A toggle to override global storage settings
    - Storage location selector (hidden by default)
    - Methods to retrieve storage location and credentials from global or local settings

    Components using this mixin should call get_storage_settings_inputs() to get
    the input fields and implement their storage-specific logic using the provided methods.
    """

    @staticmethod
    def get_storage_settings_inputs():
        """Get common storage settings input fields.

        Returns:
            list: Input fields for storage settings (use_custom_storage and storage_location)
        """
        return [
            BoolInput(
                name="use_custom_storage",
                display_name="Override Global Storage",
                value=False,
                advanced=True,
                real_time_refresh=True,
                info="Enable to override global storage settings for this component.",
            ),
            SortableListInput(
                name="storage_location",
                display_name="Storage Location",
                placeholder="Select Location",
                info="Choose where to read/write the file.",
                options=_get_storage_location_options(),
                real_time_refresh=True,
                limit=1,
                show=False,
            ),
        ]

    def _get_selected_storage_location(self) -> str:
        """Get the selected storage location.

        Uses component-level settings if use_custom_storage is True,
        otherwise uses global settings.

        Returns:
            str: Storage location ("Local", "AWS", or "Google Drive")
        """
        use_custom = getattr(self, "use_custom_storage", False)

        if use_custom:
            # Use component-level storage location
            if hasattr(self, "storage_location") and self.storage_location:
                if isinstance(self.storage_location, list) and len(self.storage_location) > 0:
                    return self.storage_location[0].get("name", "")
                if isinstance(self.storage_location, dict):
                    return self.storage_location.get("name", "")
            return ""  # Return empty for Write File, "Local" for Read File

        # Use global settings
        settings = get_settings_service().settings
        return settings.default_storage_location

    def _get_aws_credentials(self) -> dict[str, str | None]:
        """Get AWS credentials from component or global settings.

        Returns:
            dict: AWS credentials with keys:
                - access_key_id
                - secret_access_key
                - bucket_name
                - region
        """
        use_custom = getattr(self, "use_custom_storage", False)
        settings = get_settings_service().settings

        if use_custom:
            # Get from component attributes (may be None)
            access_key = getattr(self, "aws_access_key_id", None)
            secret_key = getattr(self, "aws_secret_access_key", None)
            bucket = getattr(self, "bucket_name", None)
            region = getattr(self, "aws_region", None)

            # Handle SecretStr objects
            if access_key and hasattr(access_key, "get_secret_value"):
                access_key = access_key.get_secret_value()
            if secret_key and hasattr(secret_key, "get_secret_value"):
                secret_key = secret_key.get_secret_value()
        else:
            # Use global settings
            access_key = settings.component_aws_access_key_id
            secret_key = settings.component_aws_secret_access_key
            bucket = settings.component_aws_default_bucket
            region = settings.component_aws_default_region

        return {
            "access_key_id": access_key,
            "secret_access_key": secret_key,
            "bucket_name": bucket,
            "region": region,
        }

    def _get_google_drive_credentials(self) -> dict[str, str | None]:
        """Get Google Drive credentials from component or global settings.

        Returns:
            dict: Google Drive credentials with keys:
                - service_account_key
                - folder_id (may be None if not set)
        """
        use_custom = getattr(self, "use_custom_storage", False)
        settings = get_settings_service().settings

        if use_custom:
            # Get from component attributes
            service_key = getattr(self, "service_account_key", None)
            folder_id = getattr(self, "folder_id", None)
        else:
            # Use global settings
            service_key = settings.component_google_drive_service_account_key
            folder_id = settings.component_google_drive_default_folder_id

        return {
            "service_account_key": service_key,
            "folder_id": folder_id,
        }

    def _update_build_config_for_storage_toggle(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        storage_specific_fields: list[str],
    ) -> dict[str, Any]:
        """Update build config when use_custom_storage toggle changes.

        Args:
            build_config: The build configuration to update
            field_value: The value of the use_custom_storage field
            storage_specific_fields: List of storage-specific field names to hide/show

        Returns:
            dict: Updated build configuration
        """
        # Show/hide storage location fields based on toggle
        if "storage_location" in build_config:
            build_config["storage_location"]["show"] = bool(field_value)

        # If disabling custom storage, hide all storage-specific fields
        if not field_value:
            for f_name in storage_specific_fields:
                if f_name in build_config:
                    build_config[f_name]["show"] = False

        return build_config

    def _set_aws_credentials_on_self(self, credentials: dict[str, str | None]) -> None:
        """Set AWS credentials on self for use with existing utility functions.

        Args:
            credentials: Dictionary with AWS credentials
        """
        self.aws_access_key_id = credentials["access_key_id"]
        self.aws_secret_access_key = credentials["secret_access_key"]
        self.bucket_name = credentials["bucket_name"]
        self.aws_region = credentials["region"]

    def _validate_aws_credentials(self, credentials: dict[str, str | None]) -> None:
        """Validate that required AWS credentials are present.

        Args:
            credentials: Dictionary with AWS credentials

        Raises:
            ValueError: If required credentials are missing
        """
        use_custom = getattr(self, "use_custom_storage", False)

        if not credentials["access_key_id"]:
            if use_custom:
                msg = "AWS Access Key ID is required for S3 storage"
            else:
                msg = "AWS Access Key ID not configured in global storage settings"
            raise ValueError(msg)

        if not credentials["secret_access_key"]:
            if use_custom:
                msg = "AWS Secret Access Key is required for S3 storage"
            else:
                msg = "AWS Secret Access Key not configured in global storage settings"
            raise ValueError(msg)

        if not credentials["bucket_name"]:
            if use_custom:
                msg = "S3 Bucket Name is required for S3 storage"
            else:
                msg = "AWS Default Bucket not configured in global storage settings"
            raise ValueError(msg)

    def _validate_google_drive_credentials(self, credentials: dict[str, str | None]) -> None:
        """Validate that required Google Drive credentials are present.

        Args:
            credentials: Dictionary with Google Drive credentials

        Raises:
            ValueError: If required credentials are missing
        """
        use_custom = getattr(self, "use_custom_storage", False)

        if not credentials["service_account_key"]:
            if use_custom:
                msg = "GCP Credentials Secret Key is required for Google Drive storage"
            else:
                msg = "Google Drive service account key not configured in global storage settings"
            raise ValueError(msg)

        # folder_id validation is optional - depends on the operation
        # For read operations, file_id is required instead
        # For write operations, folder_id is required
