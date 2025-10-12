from pathlib import Path
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DropdownInput,
    HandleInput,
    Output,
    SecretStrInput,
    StrInput,
)


class AzureBlobUploaderComponent(Component):
    """Azure Blob Storage Uploader Component.

    Uploads files to Azure Blob Storage container with two strategies:
    - Store Data: Uploads parsed content (text) from Data objects
    - Store Original File: Uploads original files from file paths

    Requires azure-storage-blob package.
    Works with File and Directory components as inputs.
    """

    display_name = "Azure Blob Upload"
    description = "Upload files to Azure Blob Storage."
    icon = "Azure"
    name = "AzureBlobUpload"

    inputs = [
        SecretStrInput(
            name="connection_string",
            display_name="Connection String",
            required=True,
            password=True,
            info="Azure Storage connection string from your Azure Portal.",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="container_name",
            display_name="Container Name",
            info="Select a container from your Azure Storage account.",
            options=[],
            value="",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="blob_prefix",
            display_name="Blob Prefix (Optional)",
            info="Optional prefix to add to uploaded blobs (e.g., 'uploads/2024/'). Leave empty for no prefix.",
            required=False,
            advanced=True,
        ),
        DropdownInput(
            name="file_format",
            display_name="File Format",
            options=[".txt", ".json", ".csv", ".md", ".html", ".xml", ".log", "Keep Original"],
            value=".txt",
            info=(
                "Choose the file format for uploaded content. Select 'Keep Original' to preserve "
                "the original file extension. Only applies to 'Store Data' strategy."
            ),
            advanced=True,
        ),
        DropdownInput(
            name="strategy",
            display_name="Strategy for file upload",
            options=["Store Data", "Store Original File"],
            value="Store Data",
            info=(
                "Choose the strategy to upload the file. Store Data means that the source file "
                "is parsed and stored as text content. Store Original File means that the source "
                "file is uploaded as is."
            ),
        ),
        HandleInput(
            name="data_inputs",
            display_name="Data Inputs",
            info="The data to upload to Azure Blob Storage.",
            input_types=["Data"],
            is_list=True,
            required=True,
        ),
        BoolInput(
            name="strip_path",
            display_name="Strip Path",
            info="Removes path from file path, keeping only the filename.",
            required=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Uploads to Azure Blob Storage", name="data", method="process_files"),
    ]

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        """Update container list when connection string changes."""
        # Ensure container_name value is always a string
        if "container_name" in build_config and "value" not in build_config["container_name"]:
            build_config["container_name"]["value"] = ""

        # Get current values - use field_value when that specific field is changing
        if field_name == "connection_string":
            connection_string = field_value or ""
        else:
            connection_string = build_config.get("connection_string", {}).get("value", "")

        # Populate container dropdown whenever we have a connection string
        if connection_string:
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError:
                build_config["container_name"]["options"] = []
                build_config["container_name"]["info"] = (
                    "⚠️ azure-storage-blob is not installed. Install with: uv pip install azure-storage-blob"
                )
                return build_config

            try:
                # List all containers
                blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                containers = list(blob_service_client.list_containers())
                container_names = [container.name for container in containers]

                build_config["container_name"]["options"] = container_names
                build_config["container_name"]["info"] = f"Found {len(container_names)} container(s)"

                # Reset container selection when connection string changes
                if field_name == "connection_string":
                    build_config["container_name"]["value"] = ""

            except Exception as e:  # noqa: BLE001
                build_config["container_name"]["options"] = []
                build_config["container_name"]["info"] = f"⚠️ Error: {str(e)[:100]}"
                return build_config
        else:
            # No connection string yet
            build_config["container_name"]["options"] = []
            build_config["container_name"]["info"] = "Enter connection string first"
            return build_config

        return build_config

    def process_files(self) -> None:
        """Process files based on the selected strategy.

        Uses a strategy pattern to process files. The strategy is determined
        by the `self.strategy` attribute, which can be either "Store Data" or "Store Original File".
        Calls the corresponding method based on the strategy.

        Returns:
            None
        """
        strategy_methods = {
            "Store Data": self.process_files_by_data,
            "Store Original File": self.process_files_by_name,
        }
        strategy_methods.get(self.strategy, lambda: self.log("Invalid strategy"))()

    def process_files_by_data(self) -> None:
        """Upload files to Azure Blob Storage based on the data inputs.

        Iterates over the data inputs, logs the file path and text content,
        and uploads each file to the specified Azure Blob Storage container if both
        file path and text content are available. Applies file format conversion if specified.

        Returns:
            None
        """
        for data_item in self.data_inputs:
            file_path = data_item.data.get("file_path")
            text_content = data_item.data.get("text")

            if file_path and text_content:
                blob_name = self._normalize_path(file_path)

                # Apply file format if specified
                blob_name = self._apply_file_format(blob_name)

                self.log(f"Uploading data from: {file_path} to blob: {blob_name}")

                # Prepare content based on file format
                content_to_upload = self._prepare_content(text_content, blob_name)

                # Upload content as blob
                container_client = self._blob_container_client()
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(content_to_upload, overwrite=True)

                self.log(f"✓ Uploaded text content to: {blob_name}")

    def process_files_by_name(self) -> None:
        """Upload files to Azure Blob Storage based on their file paths.

        Iterates through the list of data inputs, retrieves the file path from each data item,
        and uploads the original file to the specified Azure Blob Storage container if the file
        path is available.

        Returns:
            None
        """
        for data_item in self.data_inputs:
            file_path = data_item.data.get("file_path")

            if file_path:
                blob_name = self._normalize_path(file_path)
                self.log(f"Uploading file: {file_path} to blob: {blob_name}")

                # Upload original file as blob
                container_client = self._blob_container_client()
                blob_client = container_client.get_blob_client(blob_name)

                with Path(file_path).open("rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

                self.log(f"✓ Uploaded file to: {blob_name}")

    def _blob_container_client(self) -> Any:
        """Create and return an Azure Blob Storage container client.

        Returns:
            Any: An azure.storage.blob.ContainerClient instance.
        """
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as e:
            msg = "azure-storage-blob is not installed. Install with: uv pip install azure-storage-blob"
            raise ImportError(msg) from e

        if not self.connection_string:
            msg = "Connection string is required"
            raise ValueError(msg)

        if not self.container_name:
            msg = "Container name is required"
            raise ValueError(msg)

        blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        return blob_service_client.get_container_client(self.container_name)

    def _normalize_path(self, file_path: str) -> str:
        """Process the file path based on the blob_prefix and strip_path settings.

        Args:
            file_path: The original file path.

        Returns:
            str: The processed blob name/path.
        """
        prefix = self.blob_prefix
        strip_path = self.strip_path
        processed_path: str = file_path

        if strip_path:
            # Filename only
            processed_path = Path(file_path).name

        # Concatenate the blob_prefix if it exists
        if prefix:
            processed_path = str(Path(prefix) / processed_path)

        return processed_path

    def _apply_file_format(self, blob_name: str) -> str:
        """Apply the selected file format to the blob name.

        Args:
            blob_name: The original blob name.

        Returns:
            str: The blob name with the new file extension.
        """
        if not hasattr(self, "file_format") or self.file_format == "Keep Original":
            return blob_name

        # Remove existing extension and add new one
        blob_path = Path(blob_name)
        name_without_ext = blob_path.stem
        parent = blob_path.parent

        new_name = f"{name_without_ext}{self.file_format}"

        if parent and str(parent) != ".":
            return str(parent / new_name)
        return new_name

    def _prepare_content(self, text_content: str, blob_name: str) -> bytes:
        """Prepare content for upload based on file format.

        Args:
            text_content: The text content to upload.
            blob_name: The blob name (used to determine format).

        Returns:
            bytes: The content encoded appropriately for the file format.
        """
        import json

        # Get file extension
        extension = Path(blob_name).suffix.lower()

        # For JSON format, try to parse and pretty-print
        if extension == ".json":
            try:
                # Try to parse as JSON and format it
                json_data = json.loads(text_content)
                formatted_content = json.dumps(json_data, indent=2, ensure_ascii=False)
                return formatted_content.encode("utf-8")
            except (json.JSONDecodeError, ValueError):
                # If not valid JSON, just upload as-is
                self.log("Content is not valid JSON, uploading as plain text")
                return text_content.encode("utf-8")

        # For CSV format, ensure proper line endings
        elif extension == ".csv":
            # Normalize line endings for CSV
            normalized_content = text_content.replace("\r\n", "\n").replace("\r", "\n")
            return normalized_content.encode("utf-8")

        # For all other formats, just encode as UTF-8
        else:
            return text_content.encode("utf-8")
