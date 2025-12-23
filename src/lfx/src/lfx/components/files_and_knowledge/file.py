"""Enhanced file component with Docling support and process isolation.

Notes:
-----
- ALL Docling parsing/export runs in a separate OS process to prevent memory
  growth and native library state from impacting the main Langflow process.
- Standard text/structured parsing continues to use existing BaseFileComponent
  utilities (and optional threading via `parallel_load_data`).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import textwrap
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from lfx.base.data.base_file import BaseFileComponent
from lfx.base.data.storage_utils import parse_storage_path, read_file_bytes, validate_image_content_type
from lfx.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data
from lfx.inputs import SortableListInput
from lfx.inputs.inputs import DropdownInput, MessageTextInput, StrInput
from lfx.io import BoolInput, FileInput, IntInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame  # noqa: TC001
from lfx.schema.message import Message
from lfx.services.deps import get_settings_service, get_storage_service
from lfx.utils.async_helpers import run_until_complete
from lfx.utils.validate_cloud import is_astra_cloud_environment


def _get_storage_location_options():
    """Get storage location options, filtering out Local if in Astra cloud environment."""
    all_options = [{"name": "AWS", "icon": "Amazon"}, {"name": "Google Drive", "icon": "google"}]
    if is_astra_cloud_environment():
        return all_options
    return [{"name": "Local", "icon": "hard-drive"}, *all_options]


class FileComponent(BaseFileComponent):
    """File component with optional Docling processing (isolated in a subprocess)."""

    display_name = "Read File"
    # description is now a dynamic property - see get_tool_description()
    _base_description = "Loads content from one or more files."
    documentation: str = "https://docs.langflow.org/read-file"
    icon = "file-text"
    name = "File"
    add_tool_output = True  # Enable tool mode toggle without requiring tool_mode inputs

    # Extensions that can be processed without Docling (using standard text parsing)
    TEXT_EXTENSIONS = TEXT_FILE_TYPES

    # Extensions that require Docling for processing (images, advanced office formats, etc.)
    DOCLING_ONLY_EXTENSIONS = [
        "adoc",
        "asciidoc",
        "asc",
        "bmp",
        "dotx",
        "dotm",
        "docm",
        "jpg",
        "jpeg",
        "png",
        "potx",
        "ppsx",
        "pptm",
        "potm",
        "ppsm",
        "pptx",
        "tiff",
        "xls",
        "xlsx",
        "xhtml",
        "webp",
    ]

    # Docling-supported/compatible extensions; TEXT_FILE_TYPES are supported by the base loader.
    VALID_EXTENSIONS = [
        *TEXT_EXTENSIONS,
        *DOCLING_ONLY_EXTENSIONS,
    ]

    # Fixed export settings used when markdown export is requested.
    EXPORT_FORMAT = "Markdown"
    IMAGE_MODE = "placeholder"

    _base_inputs = deepcopy(BaseFileComponent.get_base_inputs())

    for input_item in _base_inputs:
        if isinstance(input_item, FileInput) and input_item.name == "path":
            input_item.real_time_refresh = True
            input_item.tool_mode = False  # Disable tool mode for file upload input
            input_item.required = False  # Make it optional so it doesn't error in tool mode
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
            tool_mode=True,  # Required for Toolset toggle, but _get_tools() ignores this parameter
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
            name="advanced_mode",
            display_name="Advanced Parser",
            value=False,
            real_time_refresh=True,
            info=(
                "Enable advanced document processing and export with Docling for PDFs, images, and office documents. "
                "Note that advanced document processing can consume significant resources."
            ),
            # Disabled in cloud
            show=not is_astra_cloud_environment(),
        ),
        DropdownInput(
            name="pipeline",
            display_name="Pipeline",
            info="Docling pipeline to use",
            options=["standard", "vlm"],
            value="standard",
            advanced=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="ocr_engine",
            display_name="OCR Engine",
            info="OCR engine to use. Only available when pipeline is set to 'standard'.",
            options=["None", "easyocr"],
            value="easyocr",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="md_image_placeholder",
            display_name="Image placeholder",
            info="Specify the image placeholder for markdown exports.",
            value="<!-- image -->",
            advanced=True,
            show=False,
        ),
        StrInput(
            name="md_page_break_placeholder",
            display_name="Page break placeholder",
            info="Add this placeholder between pages in the markdown output.",
            value="",
            advanced=True,
            show=False,
        ),
        MessageTextInput(
            name="doc_key",
            display_name="Doc Key",
            info="The key to use for the DoclingDocument column.",
            value="doc",
            advanced=True,
            show=False,
        ),
        # Deprecated input retained for backward-compatibility.
        BoolInput(
            name="use_multithreading",
            display_name="[Deprecated] Use Multithreading",
            advanced=True,
            value=True,
            info="Set 'Processing Concurrency' greater than 1 to enable multithreading.",
        ),
        IntInput(
            name="concurrency_multithreading",
            display_name="Processing Concurrency",
            advanced=True,
            info="When multiple files are being processed, the number of files to process concurrently.",
            value=1,
        ),
        BoolInput(
            name="markdown",
            display_name="Markdown Export",
            info="Export processed documents to Markdown format. Only available when advanced mode is enabled.",
            value=False,
            show=False,
        ),
    ]

    outputs = [
        Output(display_name="Raw Content", name="message", method="load_files_message", tool_mode=True),
    ]

    # ------------------------------ Tool description with file names --------------

    def get_tool_description(self) -> str:
        """Return a dynamic description that includes the names of uploaded files.

        This helps the Agent understand which files are available to read.
        """
        base_description = "Loads and returns the content from uploaded files."

        # Get the list of uploaded file paths
        file_paths = getattr(self, "path", None)
        if not file_paths:
            return base_description

        # Ensure it's a list
        if not isinstance(file_paths, list):
            file_paths = [file_paths]

        # Extract just the file names from the paths
        file_names = []
        for fp in file_paths:
            if fp:
                name = Path(fp).name
                file_names.append(name)

        if file_names:
            files_str = ", ".join(file_names)
            return f"{base_description} Available files: {files_str}. Call this tool to read these files."

        return base_description

    @property
    def description(self) -> str:
        """Dynamic description property that includes uploaded file names."""
        return self.get_tool_description()

    async def _get_tools(self) -> list:
        """Override to create a tool without parameters.

        The Read File component should use the files already uploaded via UI,
        not accept file paths from the Agent (which wouldn't know the internal paths).
        """
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel

        # Empty schema - no parameters needed
        class EmptySchema(BaseModel):
            """No parameters required - uses pre-uploaded files."""

        async def read_files_tool() -> str:
            """Read the content of uploaded files."""
            try:
                result = self.load_files_message()
                if hasattr(result, "get_text"):
                    return result.get_text()
                if hasattr(result, "text"):
                    return result.text
                return str(result)
            except (FileNotFoundError, ValueError, OSError, RuntimeError) as e:
                return f"Error reading files: {e}"

        description = self.get_tool_description()

        tool = StructuredTool(
            name="load_files_message",
            description=description,
            coroutine=read_files_tool,
            args_schema=EmptySchema,
            handle_tool_error=True,
            tags=["load_files_message"],
            metadata={
                "display_name": "Read File",
                "display_description": description,
            },
        )

        return [tool]

    # ------------------------------ UI helpers --------------------------------------

    def _path_value(self, template: dict) -> list[str]:
        """Return the list of currently selected file paths from the template."""
        return template.get("path", {}).get("file_path", [])

    def _disable_docling_fields_in_cloud(self, build_config: dict[str, Any]) -> None:
        """Disable all Docling-related fields in cloud environments."""
        if "advanced_mode" in build_config:
            build_config["advanced_mode"]["show"] = False
            build_config["advanced_mode"]["value"] = False
        # Hide all Docling-related fields
        docling_fields = ("pipeline", "ocr_engine", "doc_key", "md_image_placeholder", "md_page_break_placeholder")
        for field in docling_fields:
            if field in build_config:
                build_config[field]["show"] = False
        # Also disable OCR engine specifically
        if "ocr_engine" in build_config:
            build_config["ocr_engine"]["value"] = "None"

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        """Show/hide Advanced Parser and related fields based on selection context."""
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

        if field_name == "path":
            paths = self._path_value(build_config)

            # Disable in cloud environments
            if is_astra_cloud_environment():
                self._disable_docling_fields_in_cloud(build_config)
            else:
                # If all files can be processed by docling, do so
                allow_advanced = all(not file_path.endswith((".csv", ".xlsx", ".parquet")) for file_path in paths)
                build_config["advanced_mode"]["show"] = allow_advanced
                if not allow_advanced:
                    build_config["advanced_mode"]["value"] = False
                    docling_fields = (
                        "pipeline",
                        "ocr_engine",
                        "doc_key",
                        "md_image_placeholder",
                        "md_page_break_placeholder",
                    )
                    for field in docling_fields:
                        if field in build_config:
                            build_config[field]["show"] = False

        # Docling Processing
        elif field_name == "advanced_mode":
            # Disable in cloud environments - don't show Docling fields even if advanced_mode is toggled
            if is_astra_cloud_environment():
                self._disable_docling_fields_in_cloud(build_config)
            else:
                docling_fields = (
                    "pipeline",
                    "ocr_engine",
                    "doc_key",
                    "md_image_placeholder",
                    "md_page_break_placeholder",
                )
                for field in docling_fields:
                    if field in build_config:
                        build_config[field]["show"] = bool(field_value)
                        if field == "pipeline":
                            build_config[field]["advanced"] = not bool(field_value)

        elif field_name == "pipeline":
            # Disable in cloud environments - don't show OCR engine even if pipeline is changed
            if is_astra_cloud_environment():
                self._disable_docling_fields_in_cloud(build_config)
            elif field_value == "standard":
                build_config["ocr_engine"]["show"] = True
                build_config["ocr_engine"]["value"] = "easyocr"
            else:
                build_config["ocr_engine"]["show"] = False
                build_config["ocr_engine"]["value"] = "None"

        return build_config

    def update_outputs(self, frontend_node: dict[str, Any], field_name: str, field_value: Any) -> dict[str, Any]:  # noqa: ARG002
        """Dynamically show outputs based on file count/type and advanced mode."""
        if field_name not in ["path", "advanced_mode", "pipeline"]:
            return frontend_node

        template = frontend_node.get("template", {})
        paths = self._path_value(template)
        if not paths:
            return frontend_node

        frontend_node["outputs"] = []
        if len(paths) == 1:
            file_path = paths[0] if field_name == "path" else frontend_node["template"]["path"]["file_path"][0]
            if file_path.endswith((".csv", ".xlsx", ".parquet")):
                frontend_node["outputs"].append(
                    Output(
                        display_name="Structured Content",
                        name="dataframe",
                        method="load_files_structured",
                        tool_mode=True,
                    ),
                )
            elif file_path.endswith(".json"):
                frontend_node["outputs"].append(
                    Output(display_name="Structured Content", name="json", method="load_files_json", tool_mode=True),
                )

            advanced_mode = frontend_node.get("template", {}).get("advanced_mode", {}).get("value", False)
            if advanced_mode:
                frontend_node["outputs"].append(
                    Output(
                        display_name="Structured Output",
                        name="advanced_dataframe",
                        method="load_files_dataframe",
                        tool_mode=True,
                    ),
                )
                frontend_node["outputs"].append(
                    Output(
                        display_name="Markdown", name="advanced_markdown", method="load_files_markdown", tool_mode=True
                    ),
                )
                frontend_node["outputs"].append(
                    Output(display_name="File Path", name="path", method="load_files_path", tool_mode=True),
                )
            else:
                frontend_node["outputs"].append(
                    Output(display_name="Raw Content", name="message", method="load_files_message", tool_mode=True),
                )
                frontend_node["outputs"].append(
                    Output(display_name="File Path", name="path", method="load_files_path", tool_mode=True),
                )
        else:
            # Multiple files => DataFrame output; advanced parser disabled
            frontend_node["outputs"].append(
                Output(display_name="Files", name="dataframe", method="load_files", tool_mode=True)
            )

        return frontend_node

    # ------------------------------ Core processing ----------------------------------

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
            # Use the string path from tool mode
            from pathlib import Path

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

    def _is_docling_compatible(self, file_path: str) -> bool:
        """Lightweight extension gate for Docling-compatible types."""
        docling_exts = (
            ".adoc",
            ".asciidoc",
            ".asc",
            ".bmp",
            ".csv",
            ".dotx",
            ".dotm",
            ".docm",
            ".docx",
            ".htm",
            ".html",
            ".jpg",
            ".jpeg",
            ".json",
            ".md",
            ".pdf",
            ".png",
            ".potx",
            ".ppsx",
            ".pptm",
            ".potm",
            ".ppsm",
            ".pptx",
            ".tiff",
            ".txt",
            ".xls",
            ".xlsx",
            ".xhtml",
            ".xml",
            ".webp",
        )
        return file_path.lower().endswith(docling_exts)

    async def _get_local_file_for_docling(self, file_path: str) -> tuple[str, bool]:
        """Get a local file path for Docling processing, downloading from S3 if needed.

        Args:
            file_path: Either a local path or S3 key (format "flow_id/filename")

        Returns:
            tuple[str, bool]: (local_path, should_delete) where should_delete indicates
                              if this is a temporary file that should be cleaned up
        """
        settings = get_settings_service().settings
        if settings.storage_type == "local":
            return file_path, False

        # S3 storage - download to temp file
        parsed = parse_storage_path(file_path)
        if not parsed:
            msg = f"Invalid S3 path format: {file_path}. Expected 'flow_id/filename'"
            raise ValueError(msg)

        storage_service = get_storage_service()
        flow_id, filename = parsed

        # Get file content from S3
        content = await storage_service.get_file(flow_id, filename)

        suffix = Path(filename).suffix
        with NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as tmp_file:
            tmp_file.write(content)
            temp_path = tmp_file.name

        return temp_path, True

    def _process_docling_in_subprocess(self, file_path: str) -> Data | None:
        """Run Docling in a separate OS process and map the result to a Data object.

        We avoid multiprocessing pickling by launching `python -c "<script>"` and
        passing JSON config via stdin. The child prints a JSON result to stdout.

        For S3 storage, the file is downloaded to a temp file first.
        """
        if not file_path:
            return None

        settings = get_settings_service().settings
        if settings.storage_type == "s3":
            local_path, should_delete = run_until_complete(self._get_local_file_for_docling(file_path))
        else:
            local_path = file_path
            should_delete = False

        try:
            return self._process_docling_subprocess_impl(local_path, file_path)
        finally:
            # Clean up temp file if we created one
            if should_delete:
                with contextlib.suppress(Exception):
                    Path(local_path).unlink()  # Ignore cleanup errors

    def _process_docling_subprocess_impl(self, local_file_path: str, original_file_path: str) -> Data | None:
        """Implementation of Docling subprocess processing.

        Args:
            local_file_path: Path to local file to process
            original_file_path: Original file path to include in metadata
        Returns:
            Data object with processed content
        """
        args: dict[str, Any] = {
            "file_path": local_file_path,
            "markdown": bool(self.markdown),
            "image_mode": str(self.IMAGE_MODE),
            "md_image_placeholder": str(self.md_image_placeholder),
            "md_page_break_placeholder": str(self.md_page_break_placeholder),
            "pipeline": str(self.pipeline),
            "ocr_engine": (
                self.ocr_engine if self.ocr_engine and self.ocr_engine != "None" and self.pipeline != "vlm" else None
            ),
        }

        # Child script for isolating the docling processing
        child_script = textwrap.dedent(
            r"""
            import json, sys

            def try_imports():
                try:
                    from docling.datamodel.base_models import ConversionStatus, InputFormat  # type: ignore
                    from docling.document_converter import DocumentConverter  # type: ignore
                    from docling_core.types.doc import ImageRefMode  # type: ignore
                    return ConversionStatus, InputFormat, DocumentConverter, ImageRefMode, "latest"
                except Exception as e:
                    raise e

            def create_converter(strategy, input_format, DocumentConverter, pipeline, ocr_engine):
                # --- Standard PDF/IMAGE pipeline (your existing behavior), with optional OCR ---
                if pipeline == "standard":
                    try:
                        from docling.datamodel.pipeline_options import PdfPipelineOptions  # type: ignore
                        from docling.document_converter import PdfFormatOption  # type: ignore

                        pipe = PdfPipelineOptions()
                        pipe.do_ocr = False

                        if ocr_engine:
                            try:
                                from docling.models.factories import get_ocr_factory  # type: ignore
                                pipe.do_ocr = True
                                fac = get_ocr_factory(allow_external_plugins=False)
                                pipe.ocr_options = fac.create_options(kind=ocr_engine)
                            except Exception:
                                # If OCR setup fails, disable it
                                pipe.do_ocr = False

                        fmt = {}
                        if hasattr(input_format, "PDF"):
                            fmt[getattr(input_format, "PDF")] = PdfFormatOption(pipeline_options=pipe)
                        if hasattr(input_format, "IMAGE"):
                            fmt[getattr(input_format, "IMAGE")] = PdfFormatOption(pipeline_options=pipe)

                        return DocumentConverter(format_options=fmt)
                    except Exception:
                        return DocumentConverter()

                # --- Vision-Language Model (VLM) pipeline ---
                if pipeline == "vlm":
                    try:
                        from docling.datamodel.pipeline_options import VlmPipelineOptions
                        from docling.datamodel.vlm_model_specs import GRANITEDOCLING_MLX, GRANITEDOCLING_TRANSFORMERS
                        from docling.document_converter import PdfFormatOption
                        from docling.pipeline.vlm_pipeline import VlmPipeline

                        vl_pipe = VlmPipelineOptions(
                            vlm_options=GRANITEDOCLING_TRANSFORMERS,
                        )

                        if sys.platform == "darwin":
                            try:
                                import mlx_vlm
                                vl_pipe.vlm_options = GRANITEDOCLING_MLX
                            except ImportError as e:
                                raise e

                        # VLM paths generally don't need OCR; keep OCR off by default here.
                        fmt = {}
                        if hasattr(input_format, "PDF"):
                            fmt[getattr(input_format, "PDF")] = PdfFormatOption(
                            pipeline_cls=VlmPipeline,
                            pipeline_options=vl_pipe
                        )
                        if hasattr(input_format, "IMAGE"):
                            fmt[getattr(input_format, "IMAGE")] = PdfFormatOption(
                            pipeline_cls=VlmPipeline,
                            pipeline_options=vl_pipe
                        )

                        return DocumentConverter(format_options=fmt)
                    except Exception as e:
                        raise e

                # --- Fallback: default converter with no special options ---
                return DocumentConverter()

            def export_markdown(document, ImageRefMode, image_mode, img_ph, pg_ph):
                try:
                    mode = getattr(ImageRefMode, image_mode.upper(), image_mode)
                    return document.export_to_markdown(
                        image_mode=mode,
                        image_placeholder=img_ph,
                        page_break_placeholder=pg_ph,
                    )
                except Exception:
                    try:
                        return document.export_to_text()
                    except Exception:
                        return str(document)

            def to_rows(doc_dict):
                rows = []
                for t in doc_dict.get("texts", []):
                    prov = t.get("prov") or []
                    page_no = None
                    if prov and isinstance(prov, list) and isinstance(prov[0], dict):
                        page_no = prov[0].get("page_no")
                    rows.append({
                        "page_no": page_no,
                        "label": t.get("label"),
                        "text": t.get("text"),
                        "level": t.get("level"),
                    })
                return rows

            def main():
                cfg = json.loads(sys.stdin.read())
                file_path = cfg["file_path"]
                markdown = cfg["markdown"]
                image_mode = cfg["image_mode"]
                img_ph = cfg["md_image_placeholder"]
                pg_ph = cfg["md_page_break_placeholder"]
                pipeline = cfg["pipeline"]
                ocr_engine = cfg.get("ocr_engine")
                meta = {"file_path": file_path}

                try:
                    ConversionStatus, InputFormat, DocumentConverter, ImageRefMode, strategy = try_imports()
                    converter = create_converter(strategy, InputFormat, DocumentConverter, pipeline, ocr_engine)
                    try:
                        res = converter.convert(file_path)
                    except Exception as e:
                        print(json.dumps({"ok": False, "error": f"Docling conversion error: {e}", "meta": meta}))
                        return

                    ok = False
                    if hasattr(res, "status"):
                        try:
                            ok = (res.status == ConversionStatus.SUCCESS) or (str(res.status).lower() == "success")
                        except Exception:
                            ok = (str(res.status).lower() == "success")
                    if not ok and hasattr(res, "document"):
                        ok = getattr(res, "document", None) is not None
                    if not ok:
                        print(json.dumps({"ok": False, "error": "Docling conversion failed", "meta": meta}))
                        return

                    doc = getattr(res, "document", None)
                    if doc is None:
                        print(json.dumps({"ok": False, "error": "Docling produced no document", "meta": meta}))
                        return

                    if markdown:
                        text = export_markdown(doc, ImageRefMode, image_mode, img_ph, pg_ph)
                        print(json.dumps({"ok": True, "mode": "markdown", "text": text, "meta": meta}))
                        return

                    # structured
                    try:
                        doc_dict = doc.export_to_dict()
                    except Exception as e:
                        print(json.dumps({"ok": False, "error": f"Docling export_to_dict failed: {e}", "meta": meta}))
                        return

                    rows = to_rows(doc_dict)
                    print(json.dumps({"ok": True, "mode": "structured", "doc": rows, "meta": meta}))
                except Exception as e:
                    print(
                        json.dumps({
                            "ok": False,
                            "error": f"Docling processing error: {e}",
                            "meta": {"file_path": file_path},
                        })
                    )

            if __name__ == "__main__":
                main()
            """
        )

        # Validate file_path to avoid command injection or unsafe input
        if not isinstance(args["file_path"], str) or any(c in args["file_path"] for c in [";", "|", "&", "$", "`"]):
            return Data(data={"error": "Unsafe file path detected.", "file_path": args["file_path"]})

        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-u", "-c", child_script],
            input=json.dumps(args).encode("utf-8"),
            capture_output=True,
            check=False,
        )

        if not proc.stdout:
            err_msg = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else "no output from child process"
            return Data(data={"error": f"Docling subprocess error: {err_msg}", "file_path": original_file_path})

        try:
            result = json.loads(proc.stdout.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            err_msg = proc.stderr.decode("utf-8", errors="replace")
            return Data(
                data={
                    "error": f"Invalid JSON from Docling subprocess: {e}. stderr={err_msg}",
                    "file_path": original_file_path,
                },
            )

        if not result.get("ok"):
            error_msg = result.get("error", "Unknown Docling error")
            # Override meta file_path with original_file_path to ensure correct path matching
            meta = result.get("meta", {})
            meta["file_path"] = original_file_path
            return Data(data={"error": error_msg, **meta})

        meta = result.get("meta", {})
        # Override meta file_path with original_file_path to ensure correct path matching
        # The subprocess returns the temp file path, but we need the original S3/local path for rollup_data
        meta["file_path"] = original_file_path
        if result.get("mode") == "markdown":
            exported_content = str(result.get("text", ""))
            return Data(
                text=exported_content,
                data={"exported_content": exported_content, "export_format": self.EXPORT_FORMAT, **meta},
            )

        rows = list(result.get("doc", []))
        return Data(data={"doc": rows, "export_format": self.EXPORT_FORMAT, **meta})

    def process_files(
        self,
        file_list: list[BaseFileComponent.BaseFile],
    ) -> list[BaseFileComponent.BaseFile]:
        """Process input files.

        - advanced_mode => Docling in a separate process.
        - Otherwise => standard parsing in current process (optionally threaded).
        """
        if not file_list:
            msg = "No files to process."
            raise ValueError(msg)

        # Validate image files to detect content/extension mismatches
        # This prevents API errors like "Image does not match the provided media type"
        image_extensions = {"jpeg", "jpg", "png", "gif", "webp", "bmp", "tiff"}
        settings = get_settings_service().settings
        for file in file_list:
            extension = file.path.suffix[1:].lower()
            if extension in image_extensions:
                # Read bytes based on storage type
                try:
                    if settings.storage_type == "s3":
                        # For S3 storage, use storage service to read file bytes
                        file_path_str = str(file.path)
                        content = run_until_complete(read_file_bytes(file_path_str))
                    else:
                        # For local storage, read bytes directly from filesystem
                        content = file.path.read_bytes()

                    is_valid, error_msg = validate_image_content_type(
                        str(file.path),
                        content=content,
                    )
                    if not is_valid:
                        self.log(error_msg)
                        if not self.silent_errors:
                            raise ValueError(error_msg)
                except (OSError, FileNotFoundError) as e:
                    self.log(f"Could not read file for validation: {e}")
                    # Continue - let it fail later with better error

        # Validate that files requiring Docling are only processed when advanced mode is enabled
        if not self.advanced_mode:
            for file in file_list:
                extension = file.path.suffix[1:].lower()
                if extension in self.DOCLING_ONLY_EXTENSIONS:
                    if is_astra_cloud_environment():
                        msg = (
                            f"File '{file.path.name}' has extension '.{extension}' which requires "
                            f"Advanced Parser mode. Advanced Parser is not available in cloud environments."
                        )
                    else:
                        msg = (
                            f"File '{file.path.name}' has extension '.{extension}' which requires "
                            f"Advanced Parser mode. Please enable 'Advanced Parser' to process this file."
                        )
                    self.log(msg)
                    raise ValueError(msg)

        def process_file_standard(file_path: str, *, silent_errors: bool = False) -> Data | None:
            try:
                return parse_text_file_to_data(file_path, silent_errors=silent_errors)
            except FileNotFoundError as e:
                self.log(f"File not found: {file_path}. Error: {e}")
                if not silent_errors:
                    raise
                return None
            except Exception as e:
                self.log(f"Unexpected error processing {file_path}: {e}")
                if not silent_errors:
                    raise
                return None

        docling_compatible = all(self._is_docling_compatible(str(f.path)) for f in file_list)

        # Advanced path: Check if ALL files are compatible with Docling
        if self.advanced_mode and docling_compatible:
            final_return: list[BaseFileComponent.BaseFile] = []
            for file in file_list:
                file_path = str(file.path)
                advanced_data: Data | None = self._process_docling_in_subprocess(file_path)

                # Handle None case - Docling processing failed or returned None
                if advanced_data is None:
                    error_data = Data(
                        data={
                            "file_path": file_path,
                            "error": "Docling processing returned no result. Check logs for details.",
                        },
                    )
                    final_return.extend(self.rollup_data([file], [error_data]))
                    continue

                # --- UNNEST: expand each element in `doc` to its own Data row
                payload = getattr(advanced_data, "data", {}) or {}

                # Check for errors first
                if "error" in payload:
                    error_msg = payload.get("error", "Unknown error")
                    error_data = Data(
                        data={
                            "file_path": file_path,
                            "error": error_msg,
                            **{k: v for k, v in payload.items() if k not in ("error", "file_path")},
                        },
                    )
                    final_return.extend(self.rollup_data([file], [error_data]))
                    continue

                doc_rows = payload.get("doc")
                if isinstance(doc_rows, list) and doc_rows:
                    # Non-empty list of structured rows
                    rows: list[Data | None] = [
                        Data(
                            data={
                                "file_path": file_path,
                                **(item if isinstance(item, dict) else {"value": item}),
                            },
                        )
                        for item in doc_rows
                    ]
                    final_return.extend(self.rollup_data([file], rows))
                elif isinstance(doc_rows, list) and not doc_rows:
                    # Empty list - file was processed but no text content found
                    # Create a Data object indicating no content was extracted
                    self.log(f"No text extracted from '{file_path}', creating placeholder data")
                    empty_data = Data(
                        data={
                            "file_path": file_path,
                            "text": "(No text content extracted from image)",
                            "info": "Image processed successfully but contained no extractable text",
                            **{k: v for k, v in payload.items() if k != "doc"},
                        },
                    )
                    final_return.extend(self.rollup_data([file], [empty_data]))
                else:
                    # If not structured, keep as-is (e.g., markdown export or error dict)
                    # Ensure file_path is set for proper rollup matching
                    if not payload.get("file_path"):
                        payload["file_path"] = file_path
                        # Create new Data with file_path
                        advanced_data = Data(
                            data=payload,
                            text=getattr(advanced_data, "text", None),
                        )
                    final_return.extend(self.rollup_data([file], [advanced_data]))
            return final_return

        # Standard multi-file (or single non-advanced) path
        concurrency = 1 if not self.use_multithreading else max(1, self.concurrency_multithreading)

        file_paths = [str(f.path) for f in file_list]
        self.log(f"Starting parallel processing of {len(file_paths)} files with concurrency: {concurrency}.")
        my_data = parallel_load_data(
            file_paths,
            silent_errors=self.silent_errors,
            load_function=process_file_standard,
            max_concurrency=concurrency,
        )
        return self.rollup_data(file_list, my_data)

    # ------------------------------ Output helpers -----------------------------------

    def load_files_helper(self) -> DataFrame:
        result = self.load_files()

        # Result is a DataFrame - check if it has any rows
        if result.empty:
            msg = "Could not extract content from the provided file(s)."
            raise ValueError(msg)

        # Check for error column with error messages
        if "error" in result.columns:
            errors = result["error"].dropna().tolist()
            if errors and not any(col in result.columns for col in ["text", "doc", "exported_content"]):
                raise ValueError(errors[0])

        return result

    def load_files_dataframe(self) -> DataFrame:
        """Load files using advanced Docling processing and export to DataFrame format."""
        self.markdown = False
        return self.load_files_helper()

    def load_files_markdown(self) -> Message:
        """Load files using advanced Docling processing and export to Markdown format."""
        self.markdown = True
        result = self.load_files_helper()

        # Result is a DataFrame - check for text or exported_content columns
        if "text" in result.columns and not result["text"].isna().all():
            text_values = result["text"].dropna().tolist()
            if text_values:
                return Message(text=str(text_values[0]))

        if "exported_content" in result.columns and not result["exported_content"].isna().all():
            content_values = result["exported_content"].dropna().tolist()
            if content_values:
                return Message(text=str(content_values[0]))

        # Return empty message with info that no text was found
        return Message(text="(No text content extracted from file)")
