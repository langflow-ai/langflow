import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import orjson
import pandas as pd
from fastapi import UploadFile
from fastapi.encoders import jsonable_encoder

from lfx.custom import Component
from lfx.inputs import SortableListInput
from lfx.io import BoolInput, DropdownInput, HandleInput, SecretStrInput, StrInput
from lfx.schema import Data, DataFrame, Message
from lfx.services.deps import get_settings_service, get_storage_service, session_scope
from lfx.template.field.base import Output
from lfx.utils.validate_cloud import is_astra_cloud_environment


def _get_storage_location_options():
    """Get storage location options, filtering out Local if in Astra cloud environment."""
    all_options = [{"name": "AWS", "icon": "Amazon"}, {"name": "Google Drive", "icon": "google"}]
    if is_astra_cloud_environment():
        return all_options
    return [{"name": "Local", "icon": "hard-drive"}, *all_options]


class SaveToFileComponent(Component):
    display_name = "Write File"
    description = "Save data to local file, AWS S3, or Google Drive in the selected format."
    documentation: str = "https://docs.langflow.org/write-file"
    icon = "file-text"
    name = "SaveToFile"

    # File format options for different storage types
    LOCAL_DATA_FORMAT_CHOICES = ["csv", "excel", "json", "markdown"]
    LOCAL_MESSAGE_FORMAT_CHOICES = ["txt", "json", "markdown"]
    AWS_FORMAT_CHOICES = [
        "txt",
        "json",
        "csv",
        "xml",
        "html",
        "md",
        "yaml",
        "log",
        "tsv",
        "jsonl",
        "parquet",
        "xlsx",
        "zip",
    ]
    GDRIVE_FORMAT_CHOICES = ["txt", "json", "csv", "xlsx", "slides", "docs", "jpg", "mp3"]

    inputs = [
        # Storage location selection
        SortableListInput(
            name="storage_location",
            display_name="Storage Location",
            placeholder="Select Location",
            info="Choose where to save the file.",
            options=_get_storage_location_options(),
            real_time_refresh=True,
            limit=1,
        ),
        # Common inputs
        HandleInput(
            name="input",
            display_name="File Content",
            info="The input to save.",
            dynamic=True,
            input_types=["Data", "DataFrame", "Message"],
            required=True,
        ),
        StrInput(
            name="file_name",
            display_name="File Name",
            info="Name file will be saved as (without extension).",
            required=True,
            show=False,
            tool_mode=True,
        ),
        BoolInput(
            name="append_mode",
            display_name="Append",
            info=(
                "Append to file if it exists (only for Local storage with plain text formats). "
                "Not supported for cloud storage (AWS/Google Drive)."
            ),
            value=False,
            show=False,
        ),
        # Format inputs (dynamic based on storage location)
        DropdownInput(
            name="local_format",
            display_name="File Format",
            options=list(dict.fromkeys(LOCAL_DATA_FORMAT_CHOICES + LOCAL_MESSAGE_FORMAT_CHOICES)),
            info="Select the file format for local storage.",
            value="json",
            show=False,
        ),
        DropdownInput(
            name="aws_format",
            display_name="File Format",
            options=AWS_FORMAT_CHOICES,
            info="Select the file format for AWS S3 storage.",
            value="txt",
            show=False,
        ),
        DropdownInput(
            name="gdrive_format",
            display_name="File Format",
            options=GDRIVE_FORMAT_CHOICES,
            info="Select the file format for Google Drive storage.",
            value="txt",
            show=False,
        ),
        # AWS S3 specific inputs
        SecretStrInput(
            name="aws_access_key_id",
            display_name="AWS Access Key ID",
            info="AWS Access key ID.",
            show=False,
            advanced=True,
        ),
        SecretStrInput(
            name="aws_secret_access_key",
            display_name="AWS Secret Key",
            info="AWS Secret Key.",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="bucket_name",
            display_name="S3 Bucket Name",
            info="Enter the name of the S3 bucket.",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="aws_region",
            display_name="AWS Region",
            info="AWS region (e.g., us-east-1, eu-west-1).",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="s3_prefix",
            display_name="S3 Prefix",
            info="Prefix for all files in S3.",
            show=False,
            advanced=True,
        ),
        # Google Drive specific inputs
        SecretStrInput(
            name="service_account_key",
            display_name="GCP Credentials Secret Key",
            info="Your Google Cloud Platform service account JSON key as a secret string (complete JSON content).",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="folder_id",
            display_name="Google Drive Folder ID",
            info=(
                "The Google Drive folder ID where the file will be uploaded. "
                "The folder must be shared with the service account email."
            ),
            required=True,
            show=False,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="File Path", name="message", method="save_to_file")]

    def update_build_config(self, build_config, field_value, field_name=None):
        """Update build configuration to show/hide fields based on storage location selection."""
        # Update options dynamically based on cloud environment
        # This ensures options are refreshed when build_config is updated
        if "storage_location" in build_config:
            updated_options = _get_storage_location_options()
            build_config["storage_location"]["options"] = updated_options

        if field_name != "storage_location":
            return build_config

        # Extract selected storage location
        selected = [location["name"] for location in field_value] if isinstance(field_value, list) else []

        # Hide all dynamic fields first
        dynamic_fields = [
            "file_name",  # Common fields (input is always visible)
            "append_mode",
            "local_format",
            "aws_format",
            "gdrive_format",
            "aws_access_key_id",
            "aws_secret_access_key",
            "bucket_name",
            "aws_region",
            "s3_prefix",
            "service_account_key",
            "folder_id",
        ]

        for f_name in dynamic_fields:
            if f_name in build_config:
                build_config[f_name]["show"] = False

        # Show fields based on selected storage location
        if len(selected) == 1:
            location = selected[0]

            # Show file_name when any storage location is selected
            if "file_name" in build_config:
                build_config["file_name"]["show"] = True

            # Show append_mode only for Local storage (not supported for cloud storage)
            if "append_mode" in build_config:
                build_config["append_mode"]["show"] = location == "Local"

            if location == "Local":
                if "local_format" in build_config:
                    build_config["local_format"]["show"] = True

            elif location == "AWS":
                aws_fields = [
                    "aws_format",
                    "aws_access_key_id",
                    "aws_secret_access_key",
                    "bucket_name",
                    "aws_region",
                    "s3_prefix",
                ]
                for f_name in aws_fields:
                    if f_name in build_config:
                        build_config[f_name]["show"] = True

            elif location == "Google Drive":
                gdrive_fields = ["gdrive_format", "service_account_key", "folder_id"]
                for f_name in gdrive_fields:
                    if f_name in build_config:
                        build_config[f_name]["show"] = True

        return build_config

    async def save_to_file(self) -> Message:
        """Save the input to a file and upload it, returning a confirmation message."""
        # Validate inputs
        if not self.file_name:
            msg = "File name must be provided."
            raise ValueError(msg)
        if not self._get_input_type():
            msg = "Input type is not set."
            raise ValueError(msg)

        # Get selected storage location
        storage_location = self._get_selected_storage_location()
        if not storage_location:
            msg = "Storage location must be selected."
            raise ValueError(msg)

        # Check if Local storage is disabled in cloud environment
        if storage_location == "Local" and is_astra_cloud_environment():
            msg = "Local storage is not available in cloud environment. Please use AWS or Google Drive."
            raise ValueError(msg)

        # Route to appropriate save method based on storage location
        if storage_location == "Local":
            return await self._save_to_local()
        if storage_location == "AWS":
            return await self._save_to_aws()
        if storage_location == "Google Drive":
            return await self._save_to_google_drive()
        msg = f"Unsupported storage location: {storage_location}"
        raise ValueError(msg)

    def _get_input_type(self) -> str:
        """Determine the input type based on the provided input."""
        # Use exact type checking (type() is) instead of isinstance() to avoid inheritance issues.
        # Since Message inherits from Data, isinstance(message, Data) would return True for Message objects,
        # causing Message inputs to be incorrectly identified as Data type.
        if type(self.input) is DataFrame:
            return "DataFrame"
        if type(self.input) is Message:
            return "Message"
        if type(self.input) is Data:
            return "Data"
        msg = f"Unsupported input type: {type(self.input)}"
        raise ValueError(msg)

    def _get_default_format(self) -> str:
        """Return the default file format based on input type."""
        if self._get_input_type() == "DataFrame":
            return "csv"
        if self._get_input_type() == "Data":
            return "json"
        if self._get_input_type() == "Message":
            return "json"
        return "json"  # Fallback

    def _adjust_file_path_with_format(self, path: Path, fmt: str) -> Path:
        """Adjust the file path to include the correct extension."""
        file_extension = path.suffix.lower().lstrip(".")
        if fmt == "excel":
            return Path(f"{path}.xlsx").expanduser() if file_extension not in ["xlsx", "xls"] else path
        return Path(f"{path}.{fmt}").expanduser() if file_extension != fmt else path

    def _is_plain_text_format(self, fmt: str) -> bool:
        """Check if a file format is plain text (supports appending)."""
        plain_text_formats = ["txt", "json", "markdown", "md", "csv", "xml", "html", "yaml", "log", "tsv", "jsonl"]
        return fmt.lower() in plain_text_formats

    async def _upload_file(self, file_path: Path) -> None:
        """Upload the saved file using the upload_user_file service."""
        from langflow.api.v2.files import upload_user_file
        from langflow.services.database.models.user.crud import get_user_by_id

        # Ensure the file exists
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        # Upload the file - always use append=False because the local file already contains
        # the correct content (either new or appended locally)
        with file_path.open("rb") as f:
            async with session_scope() as db:
                if not self.user_id:
                    msg = "User ID is required for file saving."
                    raise ValueError(msg)
                current_user = await get_user_by_id(db, self.user_id)

                await upload_user_file(
                    file=UploadFile(filename=file_path.name, file=f, size=file_path.stat().st_size),
                    session=db,
                    current_user=current_user,
                    storage_service=get_storage_service(),
                    settings_service=get_settings_service(),
                    append=False,
                )

    def _save_dataframe(self, dataframe: DataFrame, path: Path, fmt: str) -> str:
        """Save a DataFrame to the specified file format."""
        append_mode = getattr(self, "append_mode", False)
        should_append = append_mode and path.exists() and self._is_plain_text_format(fmt)

        if fmt == "csv":
            dataframe.to_csv(path, index=False, mode="a" if should_append else "w", header=not should_append)
        elif fmt == "excel":
            dataframe.to_excel(path, index=False, engine="openpyxl")
        elif fmt == "json":
            if should_append:
                # Read and parse existing JSON
                existing_data = []
                try:
                    existing_content = path.read_text(encoding="utf-8").strip()
                    if existing_content:
                        parsed = json.loads(existing_content)
                        # Handle case where existing content is a single object
                        if isinstance(parsed, dict):
                            existing_data = [parsed]
                        elif isinstance(parsed, list):
                            existing_data = parsed
                except (json.JSONDecodeError, FileNotFoundError):
                    # Treat parse errors or missing file as empty array
                    existing_data = []

                # Append new data
                new_records = json.loads(dataframe.to_json(orient="records"))
                existing_data.extend(new_records)

                # Write back as a single JSON array
                path.write_text(json.dumps(existing_data, indent=2), encoding="utf-8")
            else:
                dataframe.to_json(path, orient="records", indent=2)
        elif fmt == "markdown":
            content = dataframe.to_markdown(index=False)
            if should_append:
                path.write_text(path.read_text(encoding="utf-8") + "\n\n" + content, encoding="utf-8")
            else:
                path.write_text(content, encoding="utf-8")
        else:
            msg = f"Unsupported DataFrame format: {fmt}"
            raise ValueError(msg)
        action = "appended to" if should_append else "saved successfully as"
        return f"DataFrame {action} '{path}'"

    def _save_data(self, data: Data, path: Path, fmt: str) -> str:
        """Save a Data object to the specified file format."""
        append_mode = getattr(self, "append_mode", False)
        should_append = append_mode and path.exists() and self._is_plain_text_format(fmt)

        if fmt == "csv":
            pd.DataFrame(data.data).to_csv(
                path,
                index=False,
                mode="a" if should_append else "w",
                header=not should_append,
            )
        elif fmt == "excel":
            pd.DataFrame(data.data).to_excel(path, index=False, engine="openpyxl")
        elif fmt == "json":
            new_data = jsonable_encoder(data.data)
            if should_append:
                # Read and parse existing JSON
                existing_data = []
                try:
                    existing_content = path.read_text(encoding="utf-8").strip()
                    if existing_content:
                        parsed = json.loads(existing_content)
                        # Handle case where existing content is a single object
                        if isinstance(parsed, dict):
                            existing_data = [parsed]
                        elif isinstance(parsed, list):
                            existing_data = parsed
                except (json.JSONDecodeError, FileNotFoundError):
                    # Treat parse errors or missing file as empty array
                    existing_data = []

                # Append new data
                if isinstance(new_data, list):
                    existing_data.extend(new_data)
                else:
                    existing_data.append(new_data)

                # Write back as a single JSON array
                path.write_text(json.dumps(existing_data, indent=2), encoding="utf-8")
            else:
                content = orjson.dumps(new_data, option=orjson.OPT_INDENT_2).decode("utf-8")
                path.write_text(content, encoding="utf-8")
        elif fmt == "markdown":
            content = pd.DataFrame(data.data).to_markdown(index=False)
            if should_append:
                path.write_text(path.read_text(encoding="utf-8") + "\n\n" + content, encoding="utf-8")
            else:
                path.write_text(content, encoding="utf-8")
        else:
            msg = f"Unsupported Data format: {fmt}"
            raise ValueError(msg)
        action = "appended to" if should_append else "saved successfully as"
        return f"Data {action} '{path}'"

    async def _save_message(self, message: Message, path: Path, fmt: str) -> str:
        """Save a Message to the specified file format, handling async iterators."""
        content = ""
        if message.text is None:
            content = ""
        elif isinstance(message.text, AsyncIterator):
            async for item in message.text:
                content += str(item) + " "
            content = content.strip()
        elif isinstance(message.text, Iterator):
            content = " ".join(str(item) for item in message.text)
        else:
            content = str(message.text)

        append_mode = getattr(self, "append_mode", False)
        should_append = append_mode and path.exists() and self._is_plain_text_format(fmt)

        if fmt == "txt":
            if should_append:
                path.write_text(path.read_text(encoding="utf-8") + "\n" + content, encoding="utf-8")
            else:
                path.write_text(content, encoding="utf-8")
        elif fmt == "json":
            new_message = {"message": content}
            if should_append:
                # Read and parse existing JSON
                existing_data = []
                try:
                    existing_content = path.read_text(encoding="utf-8").strip()
                    if existing_content:
                        parsed = json.loads(existing_content)
                        # Handle case where existing content is a single object
                        if isinstance(parsed, dict):
                            existing_data = [parsed]
                        elif isinstance(parsed, list):
                            existing_data = parsed
                except (json.JSONDecodeError, FileNotFoundError):
                    # Treat parse errors or missing file as empty array
                    existing_data = []

                # Append new message
                existing_data.append(new_message)

                # Write back as a single JSON array
                path.write_text(json.dumps(existing_data, indent=2), encoding="utf-8")
            else:
                path.write_text(json.dumps(new_message, indent=2), encoding="utf-8")
        elif fmt == "markdown":
            md_content = f"**Message:**\n\n{content}"
            if should_append:
                path.write_text(path.read_text(encoding="utf-8") + "\n\n" + md_content, encoding="utf-8")
            else:
                path.write_text(md_content, encoding="utf-8")
        else:
            msg = f"Unsupported Message format: {fmt}"
            raise ValueError(msg)
        action = "appended to" if should_append else "saved successfully as"
        return f"Message {action} '{path}'"

    def _get_selected_storage_location(self) -> str:
        """Get the selected storage location from the SortableListInput."""
        if hasattr(self, "storage_location") and self.storage_location:
            if isinstance(self.storage_location, list) and len(self.storage_location) > 0:
                return self.storage_location[0].get("name", "")
            if isinstance(self.storage_location, dict):
                return self.storage_location.get("name", "")
        return ""

    def _get_file_format_for_location(self, location: str) -> str:
        """Get the appropriate file format based on storage location."""
        if location == "Local":
            return getattr(self, "local_format", None) or self._get_default_format()
        if location == "AWS":
            return getattr(self, "aws_format", "txt")
        if location == "Google Drive":
            return getattr(self, "gdrive_format", "txt")
        return self._get_default_format()

    async def _save_to_local(self) -> Message:
        """Save file to local storage (original functionality)."""
        file_format = self._get_file_format_for_location("Local")

        # Validate file format based on input type
        allowed_formats = (
            self.LOCAL_MESSAGE_FORMAT_CHOICES if self._get_input_type() == "Message" else self.LOCAL_DATA_FORMAT_CHOICES
        )
        if file_format not in allowed_formats:
            msg = f"Invalid file format '{file_format}' for {self._get_input_type()}. Allowed: {allowed_formats}"
            raise ValueError(msg)

        # Prepare file path
        file_path = Path(self.file_name).expanduser()
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = self._adjust_file_path_with_format(file_path, file_format)

        # Save the input to file based on type
        if self._get_input_type() == "DataFrame":
            confirmation = self._save_dataframe(self.input, file_path, file_format)
        elif self._get_input_type() == "Data":
            confirmation = self._save_data(self.input, file_path, file_format)
        elif self._get_input_type() == "Message":
            confirmation = await self._save_message(self.input, file_path, file_format)
        else:
            msg = f"Unsupported input type: {self._get_input_type()}"
            raise ValueError(msg)

        # Upload the saved file
        await self._upload_file(file_path)

        # Return the final file path and confirmation message
        final_path = Path.cwd() / file_path if not file_path.is_absolute() else file_path
        return Message(text=f"{confirmation} at {final_path}")

    async def _save_to_aws(self) -> Message:
        """Save file to AWS S3 using S3 functionality."""
        # Validate AWS credentials
        if not getattr(self, "aws_access_key_id", None):
            msg = "AWS Access Key ID is required for S3 storage"
            raise ValueError(msg)
        if not getattr(self, "aws_secret_access_key", None):
            msg = "AWS Secret Key is required for S3 storage"
            raise ValueError(msg)
        if not getattr(self, "bucket_name", None):
            msg = "S3 Bucket Name is required for S3 storage"
            raise ValueError(msg)

        # Use S3 upload functionality
        try:
            import boto3
        except ImportError as e:
            msg = "boto3 is not installed. Please install it using `uv pip install boto3`."
            raise ImportError(msg) from e

        # Create S3 client
        client_config = {
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
        }

        if hasattr(self, "aws_region") and self.aws_region:
            client_config["region_name"] = self.aws_region

        s3_client = boto3.client("s3", **client_config)

        # Extract content
        content = self._extract_content_for_upload()
        file_format = self._get_file_format_for_location("AWS")

        # Generate file path
        file_path = f"{self.file_name}.{file_format}"
        if hasattr(self, "s3_prefix") and self.s3_prefix:
            file_path = f"{self.s3_prefix.rstrip('/')}/{file_path}"

        # Create temporary file
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=f".{file_format}", delete=False
        ) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Upload to S3
            s3_client.upload_file(temp_file_path, self.bucket_name, file_path)
            s3_url = f"s3://{self.bucket_name}/{file_path}"
            return Message(text=f"File successfully uploaded to {s3_url}")
        finally:
            # Clean up temp file
            if Path(temp_file_path).exists():
                Path(temp_file_path).unlink()

    async def _save_to_google_drive(self) -> Message:
        """Save file to Google Drive using Google Drive functionality."""
        # Validate Google Drive credentials
        if not getattr(self, "service_account_key", None):
            msg = "GCP Credentials Secret Key is required for Google Drive storage"
            raise ValueError(msg)
        if not getattr(self, "folder_id", None):
            msg = "Google Drive Folder ID is required for Google Drive storage"
            raise ValueError(msg)

        # Use Google Drive upload functionality
        try:
            import json
            import tempfile

            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as e:
            msg = "Google API client libraries are not installed. Please install them."
            raise ImportError(msg) from e

        # Parse credentials with multiple fallback strategies
        credentials_dict = None
        parse_errors = []

        # Strategy 1: Parse as-is with strict=False to allow control characters
        try:
            credentials_dict = json.loads(self.service_account_key, strict=False)
        except json.JSONDecodeError as e:
            parse_errors.append(f"Standard parse: {e!s}")

        # Strategy 2: Strip whitespace and try again
        if credentials_dict is None:
            try:
                cleaned_key = self.service_account_key.strip()
                credentials_dict = json.loads(cleaned_key, strict=False)
            except json.JSONDecodeError as e:
                parse_errors.append(f"Stripped parse: {e!s}")

        # Strategy 3: Check if it's double-encoded (JSON string of a JSON string)
        if credentials_dict is None:
            try:
                decoded_once = json.loads(self.service_account_key, strict=False)
                if isinstance(decoded_once, str):
                    credentials_dict = json.loads(decoded_once, strict=False)
                else:
                    credentials_dict = decoded_once
            except json.JSONDecodeError as e:
                parse_errors.append(f"Double-encoded parse: {e!s}")

        # Strategy 4: Try to fix common issues with newlines in the private_key field
        if credentials_dict is None:
            try:
                # Replace literal \n with actual newlines which is common in pasted JSON
                fixed_key = self.service_account_key.replace("\\n", "\n")
                credentials_dict = json.loads(fixed_key, strict=False)
            except json.JSONDecodeError as e:
                parse_errors.append(f"Newline-fixed parse: {e!s}")

        if credentials_dict is None:
            error_details = "; ".join(parse_errors)
            msg = (
                f"Unable to parse service account key JSON. Tried multiple strategies: {error_details}. "
                "Please ensure you've copied the entire JSON content from your service account key file. "
                "The JSON should start with '{' and contain fields like 'type', 'project_id', 'private_key', etc."
            )
            raise ValueError(msg)

        # Create Google Drive service with appropriate scopes
        # Use drive scope for folder access, file scope is too restrictive for folder verification
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict, scopes=["https://www.googleapis.com/auth/drive"]
        )
        drive_service = build("drive", "v3", credentials=credentials)

        # Extract content and format
        content = self._extract_content_for_upload()
        file_format = self._get_file_format_for_location("Google Drive")

        # Handle special Google Drive formats
        if file_format in ["slides", "docs"]:
            return await self._save_to_google_apps(drive_service, credentials, content, file_format)

        # Create temporary file
        file_path = f"{self.file_name}.{file_format}"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=f".{file_format}",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Upload to Google Drive
            # Note: We skip explicit folder verification since it requires broader permissions.
            # If the folder doesn't exist or isn't accessible, the create() call will fail with a clear error.
            file_metadata = {"name": file_path, "parents": [self.folder_id]}
            media = MediaFileUpload(temp_file_path, resumable=True)

            try:
                uploaded_file = (
                    drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                )
            except Exception as e:
                msg = (
                    f"Unable to upload file to Google Drive folder '{self.folder_id}'. "
                    f"Error: {e!s}. "
                    "Please ensure: 1) The folder ID is correct, 2) The folder exists, "
                    "3) The service account has been granted access to this folder."
                )
                raise ValueError(msg) from e

            file_id = uploaded_file.get("id")
            file_url = f"https://drive.google.com/file/d/{file_id}/view"
            return Message(text=f"File successfully uploaded to Google Drive: {file_url}")
        finally:
            # Clean up temp file
            if Path(temp_file_path).exists():
                Path(temp_file_path).unlink()

    async def _save_to_google_apps(self, drive_service, credentials, content: str, app_type: str) -> Message:
        """Save content to Google Apps (Slides or Docs)."""
        import time

        if app_type == "slides":
            from googleapiclient.discovery import build

            slides_service = build("slides", "v1", credentials=credentials)

            file_metadata = {
                "name": self.file_name,
                "mimeType": "application/vnd.google-apps.presentation",
                "parents": [self.folder_id],
            }

            created_file = drive_service.files().create(body=file_metadata, fields="id").execute()
            presentation_id = created_file["id"]

            time.sleep(2)  # Wait for file to be available  # noqa: ASYNC251

            presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
            slide_id = presentation["slides"][0]["objectId"]

            # Add content to slide
            requests = [
                {
                    "createShape": {
                        "objectId": "TextBox_01",
                        "shapeType": "TEXT_BOX",
                        "elementProperties": {
                            "pageObjectId": slide_id,
                            "size": {
                                "height": {"magnitude": 3000000, "unit": "EMU"},
                                "width": {"magnitude": 6000000, "unit": "EMU"},
                            },
                            "transform": {
                                "scaleX": 1,
                                "scaleY": 1,
                                "translateX": 1000000,
                                "translateY": 1000000,
                                "unit": "EMU",
                            },
                        },
                    }
                },
                {"insertText": {"objectId": "TextBox_01", "insertionIndex": 0, "text": content}},
            ]

            slides_service.presentations().batchUpdate(
                presentationId=presentation_id, body={"requests": requests}
            ).execute()
            file_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"

        elif app_type == "docs":
            from googleapiclient.discovery import build

            docs_service = build("docs", "v1", credentials=credentials)

            file_metadata = {
                "name": self.file_name,
                "mimeType": "application/vnd.google-apps.document",
                "parents": [self.folder_id],
            }

            created_file = drive_service.files().create(body=file_metadata, fields="id").execute()
            document_id = created_file["id"]

            time.sleep(2)  # Wait for file to be available  # noqa: ASYNC251

            # Add content to document
            requests = [{"insertText": {"location": {"index": 1}, "text": content}}]
            docs_service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
            file_url = f"https://docs.google.com/document/d/{document_id}/edit"

        return Message(text=f"File successfully created in Google {app_type.title()}: {file_url}")

    def _extract_content_for_upload(self) -> str:
        """Extract content from input for upload to cloud services."""
        if self._get_input_type() == "DataFrame":
            return self.input.to_csv(index=False)
        if self._get_input_type() == "Data":
            if hasattr(self.input, "data") and self.input.data:
                if isinstance(self.input.data, dict):
                    import json

                    return json.dumps(self.input.data, indent=2, ensure_ascii=False)
                return str(self.input.data)
            return str(self.input)
        if self._get_input_type() == "Message":
            return str(self.input.text) if self.input.text else str(self.input)
        return str(self.input)
