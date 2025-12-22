"""Load File component - loads files without parsing.

This component loads files and returns raw file paths/bytes without any parsing.
This allows users to pass files directly to downstream components (e.g., LLM components
for image processing).

"""

from __future__ import annotations

import contextlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from lfx.base.data.base_file import BaseFileComponent
from lfx.inputs import SortableListInput
from lfx.inputs.inputs import StrInput
from lfx.io import BoolInput, FileInput, Output, SecretStrInput
from lfx.schema.message import Message
from lfx.services.deps import get_settings_service
from lfx.utils.constants import MESSAGE_SENDER_NAME_USER, MESSAGE_SENDER_USER
from lfx.utils.validate_cloud import is_astra_cloud_environment


def _get_storage_location_options():
    """Get storage location options, filtering out Local if in Astra cloud environment."""
    all_options = [{"name": "AWS", "icon": "Amazon"}, {"name": "Google Drive", "icon": "google"}]
    if is_astra_cloud_environment():
        return all_options
    return [{"name": "Local", "icon": "hard-drive"}, *all_options]


class LoadFileComponent(BaseFileComponent):
    """Load File component - loads files without parsing.

    This component loads files and returns raw file paths without any parsing operations.
    Files are returned in the Message.files field, ready to be passed to downstream
    components (e.g., LLM components for image processing)

    """

    display_name = "Load File"
    description = (
        "Loads files and returns raw file paths without parsing. "
        "Image files in the files field will be automatically converted to image content "
        "when passed to LLM components. Non-image files are passed as-is."
    )
    documentation: str = "https://docs.langflow.org/load-file"
    icon = "file"
    name = "LoadFile"

    # Accept all common file types since we're not parsing - use a comprehensive list
    # This includes text, images, documents, and other common formats
    VALID_EXTENSIONS = [
        # Text files
        "txt",
        "md",
        "mdx",
        "csv",
        "json",
        "yaml",
        "yml",
        "xml",
        "html",
        "htm",
        "xhtml",
        # Documents
        "pdf",
        "docx",
        "doc",
        "docm",
        "dotx",
        "dotm",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "pptm",
        "potx",
        "ppsx",
        "potm",
        "ppsm",
        # Images
        "jpg",
        "jpeg",
        "png",
        "gif",
        "bmp",
        "tiff",
        "webp",
        "svg",
        # Code
        "py",
        "js",
        "ts",
        "tsx",
        "sh",
        "sql",
        "java",
        "cpp",
        "c",
        "h",
        # Other
        "zip",
        "tar",
        "tgz",
        "bz2",
        "gz",
        "adoc",
        "asciidoc",
        "asc",
    ]

    _base_inputs = deepcopy(BaseFileComponent.get_base_inputs())

    for input_item in _base_inputs:
        if isinstance(input_item, FileInput) and input_item.name == "path":
            input_item.real_time_refresh = True
            input_item.tool_mode = False
            input_item.required = False
            break

    inputs = [
        SortableListInput(
            name="storage_location",
            display_name="Storage Location",
            placeholder="Select Location",
            info="Choose where to read the file from.",
            options=_get_storage_location_options(),
            real_time_refresh=True,
            limit=1,
        ),
        *_base_inputs,
        StrInput(
            name="file_path_str",
            display_name="File Path",
            info=(
                "Path to the file to read. Used when component is called as a tool. "
                "If not provided, will use the uploaded file from 'path' input."
            ),
            show=False,
            advanced=True,
            tool_mode=True,
            required=False,
        ),
        # AWS S3 specific inputs
        SecretStrInput(
            name="aws_access_key_id",
            display_name="AWS Access Key ID",
            info="AWS Access key ID.",
            show=False,
            advanced=False,
            required=True,
        ),
        SecretStrInput(
            name="aws_secret_access_key",
            display_name="AWS Secret Key",
            info="AWS Secret Key.",
            show=False,
            advanced=False,
            required=True,
        ),
        StrInput(
            name="bucket_name",
            display_name="S3 Bucket Name",
            info="Enter the name of the S3 bucket.",
            show=False,
            advanced=False,
            required=True,
        ),
        StrInput(
            name="aws_region",
            display_name="AWS Region",
            info="AWS region (e.g., us-east-1, eu-west-1).",
            show=False,
            advanced=False,
        ),
        StrInput(
            name="s3_file_key",
            display_name="S3 File Key",
            info="The key (path) of the file in S3 bucket.",
            show=False,
            advanced=False,
            required=True,
        ),
        # Google Drive specific inputs
        SecretStrInput(
            name="service_account_key",
            display_name="GCP Credentials Secret Key",
            info="Your Google Cloud Platform service account JSON key as a secret string (complete JSON content).",
            show=False,
            advanced=False,
            required=True,
        ),
        StrInput(
            name="file_id",
            display_name="Google Drive File ID",
            info=("The Google Drive file ID to read. The file must be shared with the service account email."),
            show=False,
            advanced=False,
            required=True,
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            advanced=True,
            info="If true, errors will not raise an exception.",
        ),
    ]

    outputs = [
        Output(display_name="File Paths", name="message", method="load_files_raw"),
        Output(display_name="File Path", name="loaded_file_path", method="load_files_path"),
    ]

    def _get_selected_storage_location(self) -> str:
        """Get the selected storage location from the SortableListInput."""
        if hasattr(self, "storage_location") and self.storage_location:
            if isinstance(self.storage_location, list) and len(self.storage_location) > 0:
                return self.storage_location[0].get("name", "")
            if isinstance(self.storage_location, dict):
                return self.storage_location.get("name", "")
        return "Local"  # Default to Local if not specified

    def _validate_and_resolve_paths(self) -> list[BaseFileComponent.BaseFile]:
        """Override to handle file_path_str input from tool mode and cloud storage.

        Priority:
        1. Cloud storage (AWS/Google Drive) if selected
        2. file_path_str (if provided by the tool call)
        3. path (uploaded file from UI)
        """
        storage_location = self._get_selected_storage_location()

        # Handle AWS S3
        if storage_location == "AWS":
            return self._read_from_aws_s3()

        # Handle Google Drive
        if storage_location == "Google Drive":
            return self._read_from_google_drive()

        # Handle Local storage
        # Check if file_path_str is provided (from tool mode)
        file_path_str = getattr(self, "file_path_str", None)
        if file_path_str:
            from lfx.schema.data import Data

            resolved_path = Path(self.resolve_path(file_path_str))
            if not resolved_path.exists():
                msg = f"File or directory not found: {file_path_str}"
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)
                return []

            data_obj = Data(data={self.SERVER_FILE_PATH_FIELDNAME: str(resolved_path)})
            return [BaseFileComponent.BaseFile(data_obj, resolved_path, delete_after_processing=False)]

        # Otherwise use the default implementation (uses path FileInput)
        return super()._validate_and_resolve_paths()

    def _read_from_aws_s3(self) -> list[BaseFileComponent.BaseFile]:
        """Read file from AWS S3."""
        from lfx.base.data.cloud_storage_utils import create_s3_client, validate_aws_credentials

        # Validate AWS credentials
        validate_aws_credentials(self)
        if not getattr(self, "s3_file_key", None):
            msg = "S3 File Key is required"
            raise ValueError(msg)

        # Create S3 client
        s3_client = create_s3_client(self)

        # Download file to temp location
        import tempfile

        # Get file extension from S3 key
        file_extension = Path(self.s3_file_key).suffix or ""

        with tempfile.NamedTemporaryFile(mode="wb", suffix=file_extension, delete=False) as temp_file:
            temp_file_path = temp_file.name
            try:
                s3_client.download_fileobj(self.bucket_name, self.s3_file_key, temp_file)
            except Exception as e:
                # Clean up temp file on failure
                with contextlib.suppress(OSError):
                    Path(temp_file_path).unlink()
                msg = f"Failed to download file from S3: {e}"
                raise RuntimeError(msg) from e

        # Create BaseFile object
        from lfx.schema.data import Data

        temp_path = Path(temp_file_path)
        data_obj = Data(data={self.SERVER_FILE_PATH_FIELDNAME: str(temp_path)})
        return [BaseFileComponent.BaseFile(data_obj, temp_path, delete_after_processing=True)]

    def _read_from_google_drive(self) -> list[BaseFileComponent.BaseFile]:
        """Read file from Google Drive."""
        import tempfile

        from googleapiclient.http import MediaIoBaseDownload

        from lfx.base.data.cloud_storage_utils import create_google_drive_service

        # Validate Google Drive credentials
        if not getattr(self, "service_account_key", None):
            msg = "GCP Credentials Secret Key is required for Google Drive storage"
            raise ValueError(msg)
        if not getattr(self, "file_id", None):
            msg = "Google Drive File ID is required"
            raise ValueError(msg)

        # Create Google Drive service with read-only scope
        drive_service = create_google_drive_service(
            self.service_account_key, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )

        # Get file metadata to determine file name and extension
        try:
            file_metadata = drive_service.files().get(fileId=self.file_id, fields="name,mimeType").execute()
            file_name = file_metadata.get("name", "download")
        except Exception as e:
            msg = (
                f"Unable to access file with ID '{self.file_id}'. "
                f"Error: {e!s}. "
                "Please ensure: 1) The file ID is correct, 2) The file exists, "
                "3) The service account has been granted access to this file."
            )
            raise ValueError(msg) from e

        # Download file to temp location
        file_extension = Path(file_name).suffix or ""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=file_extension, delete=False) as temp_file:
            temp_file_path = temp_file.name
            try:
                request = drive_service.files().get_media(fileId=self.file_id)
                downloader = MediaIoBaseDownload(temp_file, request)
                done = False
                while not done:
                    _status, done = downloader.next_chunk()
            except Exception as e:
                # Clean up temp file on failure
                with contextlib.suppress(OSError):
                    Path(temp_file_path).unlink()
                msg = f"Failed to download file from Google Drive: {e}"
                raise RuntimeError(msg) from e

        # Create BaseFile object
        from lfx.schema.data import Data

        temp_path = Path(temp_file_path)
        data_obj = Data(data={self.SERVER_FILE_PATH_FIELDNAME: str(temp_path)})
        return [BaseFileComponent.BaseFile(data_obj, temp_path, delete_after_processing=True)]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        """Process input files - no-op since we're not parsing, just returning file paths.

        We ensure each file has a Data object with the file_path, but we don't parse the content.
        """
        from lfx.schema.data import Data

        # Ensure each file has proper data structure with file_path
        for file in file_list:
            if not file.data or len(file.data) == 0:
                # Create a minimal Data object with just the file path
                data_obj = Data(data={self.SERVER_FILE_PATH_FIELDNAME: str(file.path)})
                file.data = [data_obj]
            else:
                # Ensure file_path is set in existing data
                for data_item in file.data:
                    if self.SERVER_FILE_PATH_FIELDNAME not in data_item.data:
                        data_item.data[self.SERVER_FILE_PATH_FIELDNAME] = str(file.path)

        return file_list

    def load_files_raw(self) -> Message:
        """Load files and return as Message with file paths in the files field (no parsing).

        This method returns raw file paths without parsing. When the Message is passed to
        LLM components:
        - Image files (detected by file extension/content) are automatically converted to
          image content format for multimodal LLM processing
        - Non-image files are passed as-is (their handling depends on the LLM component)

        Returns:
            Message: Message with file paths in the files field
        """
        files = self._validate_and_resolve_paths()
        if not files:
            return Message(
                text="",
                files=[],
                sender=MESSAGE_SENDER_USER,
                sender_name=MESSAGE_SENDER_NAME_USER,
            )

        settings = get_settings_service().settings

        # Collect file paths - for S3 storage, use virtual storage keys
        # For local storage, use actual file paths
        if settings.storage_type == "s3":
            file_paths = [file.path.as_posix() for file in files]
        else:
            file_paths = [file.path.as_posix() for file in files if file.path.exists()]

        # Return Message with files in the files field (not text field)
        # This allows LLM components to process images/files directly
        # Set sender to USER so LLM components can properly convert to HumanMessage
        return Message(
            text="",
            files=file_paths,
            sender=MESSAGE_SENDER_USER,
            sender_name=MESSAGE_SENDER_NAME_USER,
        )

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        """Show/hide storage-specific fields based on selection context."""
        # Update storage location options dynamically based on cloud environment
        if "storage_location" in build_config:
            updated_options = _get_storage_location_options()
            build_config["storage_location"]["options"] = updated_options

        # Handle storage location selection
        if field_name == "storage_location":
            # Extract selected storage location
            selected = [location["name"] for location in field_value] if isinstance(field_value, list) else []

            # Hide all storage-specific fields first
            storage_fields = [
                "aws_access_key_id",
                "aws_secret_access_key",
                "bucket_name",
                "aws_region",
                "s3_file_key",
                "service_account_key",
                "file_id",
            ]

            for f_name in storage_fields:
                if f_name in build_config:
                    build_config[f_name]["show"] = False

            # Show fields based on selected storage location
            if len(selected) == 1:
                location = selected[0]

                if location == "Local":
                    # Show file upload input for local storage
                    if "path" in build_config:
                        build_config["path"]["show"] = True

                elif location == "AWS":
                    # Hide file upload input, show AWS fields
                    if "path" in build_config:
                        build_config["path"]["show"] = False

                    aws_fields = [
                        "aws_access_key_id",
                        "aws_secret_access_key",
                        "bucket_name",
                        "aws_region",
                        "s3_file_key",
                    ]
                    for f_name in aws_fields:
                        if f_name in build_config:
                            build_config[f_name]["show"] = True
                            build_config[f_name]["advanced"] = False

                elif location == "Google Drive":
                    # Hide file upload input, show Google Drive fields
                    if "path" in build_config:
                        build_config["path"]["show"] = False

                    gdrive_fields = ["service_account_key", "file_id"]
                    for f_name in gdrive_fields:
                        if f_name in build_config:
                            build_config[f_name]["show"] = True
                            build_config[f_name]["advanced"] = False
            # No storage location selected - show file upload by default
            elif "path" in build_config:
                build_config["path"]["show"] = True

        return build_config
