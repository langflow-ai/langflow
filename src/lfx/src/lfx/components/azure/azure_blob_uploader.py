from pathlib import Path
from typing import Any

from langflow.schema import Data

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
            refresh_button=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="blob_prefix",
            display_name="Blob Prefix (Optional)",
            info="Optional prefix to add to uploaded blobs (e.g., 'uploads/2024/'). Leave empty for no prefix.",
            value="",
        ),
        DropdownInput(
            name="file_format",
            display_name="File Format",
            options=[".txt", ".csv", ".pdf", "Keep Original"],
            value="Keep Original",
            info=(
                "Choose the file format for uploaded content. "
                "Only applies to 'Store Data' strategy. "
                "PDF format will convert text content into a proper PDF document."
            ),
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
            value=False,
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
        # Validate inputs
        if not hasattr(self, "data_inputs") or not self.data_inputs:
            self.log("⚠️ No data inputs provided")
            return

        if not hasattr(self, "connection_string") or not self.connection_string:
            self.log("⚠️ Connection string is required")
            return

        if not hasattr(self, "container_name") or not self.container_name:
            self.log("⚠️ Container name is required")
            return

        self.log(f"Processing {len(self.data_inputs)} file(s) with strategy: {self.strategy}")

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
        uploaded_count = 0
        self.log(f"🔍 Processing {len(self.data_inputs)} items with 'Store Data' strategy")

        for idx, data_item in enumerate(self.data_inputs, 1):
            data_keys = list(data_item.data.keys()) if hasattr(data_item, "data") else "No data attr"
            self.log(f"📋 Item {idx}: {type(data_item)}, data keys: {data_keys}")

            file_path = data_item.data.get("file_path")
            text_content = data_item.data.get("text")

            if not text_content:
                self.log(f"⚠️ Item {idx}: Skipping - no text content found")
                continue

            # If no file_path, generate one based on index (without extension - will be added by _apply_file_format)
            if not file_path:
                file_path = f"data_item_{idx}"
                self.log(f"📝 Item {idx}: No file_path provided, using generated name: {file_path}")

            try:
                blob_name = self._normalize_path(file_path)
                self.log(f"📝 Item {idx}: Original path: {file_path}")
                self.log(f"📝 Item {idx}: Normalized path: {blob_name}")

                # Apply file format if specified
                blob_name = self._apply_file_format(blob_name)
                self.log(f"� Item {idx}: Final blob name: {blob_name}")

                # Prepare content based on file format
                content_to_upload = self._prepare_content(text_content, blob_name)
                self.log(f"📝 Item {idx}: Content size: {len(content_to_upload)} bytes")

                # Upload content as blob
                self.log(f"📤 Item {idx}: Connecting to container '{self.container_name}'...")
                container_client = self._blob_container_client()
                blob_client = container_client.get_blob_client(blob_name)

                # Determine content type based on extension
                content_type = "application/octet-stream"  # Default
                if extension := Path(blob_name).suffix.lower():
                    content_type_map = {
                        ".pdf": "application/pdf",
                        ".txt": "text/plain",
                        ".csv": "text/csv",
                    }
                    content_type = content_type_map.get(extension, "application/octet-stream")

                self.log(f"📤 Item {idx}: Uploading to blob: {blob_name} (content_type: {content_type})")

                # Create ContentSettings object for proper content type
                from azure.storage.blob import ContentSettings

                content_settings = ContentSettings(content_type=content_type)

                blob_client.upload_blob(content_to_upload, overwrite=True, content_settings=content_settings)

                self.log(f"✅ Item {idx}: Successfully uploaded to: {blob_name}")
                uploaded_count += 1
            except (OSError, ValueError, RuntimeError) as e:
                self.log(f"❌ Item {idx}: Error uploading {file_path}: {type(e).__name__}: {e!s}")
                import traceback

                self.log(f"Traceback: {traceback.format_exc()}")

        self.log(f"✅ Upload complete: {uploaded_count} of {len(self.data_inputs)} file(s) uploaded successfully")

    def process_files_by_name(self) -> None:
        """Upload files to Azure Blob Storage based on their file paths.

        Iterates through the list of data inputs, retrieves the file path from each data item,
        and uploads the original file to the specified Azure Blob Storage container if the file
        path is available.

        Returns:
            None
        """
        uploaded_count = 0
        self.log(f"🔍 Processing {len(self.data_inputs)} items with 'Store Original File' strategy")

        for idx, data_item in enumerate(self.data_inputs, 1):
            data_keys = list(data_item.data.keys()) if hasattr(data_item, "data") else "No data attr"
            self.log(f"📋 Item {idx}: {type(data_item)}, data keys: {data_keys}")

            file_path = data_item.data.get("file_path")

            if not file_path:
                self.log(f"⚠️ Item {idx}: no file_path found in data")
                continue

            try:
                # Check if file exists
                if not Path(file_path).exists():
                    self.log(f"❌ Item {idx}: File not found: {file_path}")
                    continue

                file_size = Path(file_path).stat().st_size
                blob_name = self._normalize_path(file_path)

                self.log(f"� Item {idx}: Original path: {file_path}")
                self.log(f"📝 Item {idx}: File size: {file_size} bytes")
                self.log(f"📝 Item {idx}: Blob name: {blob_name}")

                # Upload original file as blob
                self.log(f"📤 Item {idx}: Connecting to container '{self.container_name}'...")
                container_client = self._blob_container_client()
                blob_client = container_client.get_blob_client(blob_name)

                self.log(f"📤 Item {idx}: Uploading file to blob: {blob_name}")
                with Path(file_path).open("rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

                self.log(f"✅ Item {idx}: Successfully uploaded to: {blob_name}")
                uploaded_count += 1
            except (OSError, ValueError, RuntimeError) as e:
                self.log(f"❌ Item {idx}: Error uploading {file_path}: {type(e).__name__}: {e!s}")
                import traceback

                self.log(f"Traceback: {traceback.format_exc()}")

        self.log(f"✅ Upload complete: {uploaded_count} of {len(self.data_inputs)} file(s) uploaded successfully")

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
        prefix = getattr(self, "blob_prefix", "") or ""
        strip_path = getattr(self, "strip_path", False)
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
        file_format = getattr(self, "file_format", "Keep Original")

        if not file_format or file_format == "Keep Original":
            return blob_name

        # Remove existing extension and add new one
        blob_path = Path(blob_name)
        name_without_ext = blob_path.stem
        parent = blob_path.parent

        new_name = f"{name_without_ext}{file_format}"

        if parent and str(parent) != ".":
            return str(parent / new_name)
        return new_name

    def process_store_data(self) -> list[Data]:
        """Process files with 'Store Data' strategy - uploads parsed content."""
        self.log(f"🔍 Processing {len(self.data_inputs)} items with 'Store Data' strategy")

        uploaded_count = 0
        results = []

        for idx, data_item in enumerate(self.data_inputs, 1):
            try:
                # Log data structure for debugging
                data_keys = list(data_item.data.keys()) if hasattr(data_item, "data") else "No data attr"
                self.log(f"📋 Item {idx}: {type(data_item)}, data keys: {data_keys}")

                # Get text content (required for Store Data strategy)
                text_content = data_item.data.get("text", "")
                if not text_content:
                    self.log(f"⚠️ Item {idx}: No text content found, skipping")
                    continue

                # Get or generate file path
                file_path = data_item.data.get("file_path")
                if not file_path:
                    # Generate a filename if none provided
                    file_path = f"data_item_{idx}"
                    self.log(f"📝 Item {idx}: No file_path provided, using generated name: {file_path}")

                self.log(f"📝 Item {idx}: Original path: {file_path}")

                # Normalize the path (apply prefix, strip path if needed)
                normalized_path = self._normalize_path(file_path)
                self.log(f"📝 Item {idx}: Normalized path: {normalized_path}")

                # Apply file format
                blob_name = self._apply_file_format(normalized_path)
                self.log(f"📝 Item {idx}: Final blob name: {blob_name}")

                # Prepare content based on file format
                content = self._prepare_content(text_content, blob_name)
                self.log(f"📝 Item {idx}: Content size: {len(content)} bytes")

                # Upload to Azure
                self.log(f"📤 Item {idx}: Connecting to container '{self.container_name}'...")
                container_client = self._blob_container_client()

                self.log(f"📤 Item {idx}: Uploading to blob: {blob_name}")
                blob_client = container_client.get_blob_client(blob_name)

                # Set content type based on file extension
                from azure.storage.blob import ContentSettings

                extension = Path(blob_name).suffix.lower()
                content_type = "text/plain"
                if extension == ".pdf":
                    content_type = "application/pdf"
                elif extension == ".csv":
                    content_type = "text/csv"

                blob_client.upload_blob(
                    content,
                    overwrite=True,
                    content_settings=ContentSettings(content_type=content_type),
                )

                self.log(f"✅ Item {idx}: Successfully uploaded to: {blob_name}")
                uploaded_count += 1

                results.append(Data(data={"blob_name": blob_name, "container": self.container_name}))

            except (OSError, ValueError, RuntimeError) as e:
                self.log(f"❌ Item {idx}: Error uploading {file_path}: {type(e).__name__}: {e!s}")
                import traceback

                self.log(f"Traceback: {traceback.format_exc()}")
                continue

        self.log(f"✅ Upload complete: {uploaded_count} of {len(self.data_inputs)} file(s) uploaded successfully")
        return results

    def process_store_original_file(self) -> list[Data]:
        """Process files with 'Store Original File' strategy - uploads original files."""
        self.log(f"🔍 Processing {len(self.data_inputs)} items with 'Store Original File' strategy")

        uploaded_count = 0
        results = []

        for idx, data_item in enumerate(self.data_inputs, 1):
            try:
                # Log data structure for debugging
                data_keys = list(data_item.data.keys()) if hasattr(data_item, "data") else "No data attr"
                self.log(f"📋 Item {idx}: {type(data_item)}, data keys: {data_keys}")

                # Get file path (required for Store Original File strategy)
                file_path = data_item.data.get("file_path")
                if not file_path:
                    self.log(f"⚠️ Item {idx}: No file_path found, skipping")
                    continue

                self.log(f"📝 Item {idx}: Original path: {file_path}")

                # Check if file exists
                if not Path(file_path).exists():
                    self.log(f"⚠️ Item {idx}: File does not exist: {file_path}")
                    continue

                file_size = Path(file_path).stat().st_size
                self.log(f"📝 Item {idx}: File size: {file_size} bytes")

                # Normalize the path (apply prefix, strip path if needed)
                normalized_path = self._normalize_path(file_path)
                self.log(f"📝 Item {idx}: Normalized path: {normalized_path}")

                # For 'Store Original File', we keep the original extension
                blob_name = normalized_path

                self.log(f"📝 Item {idx}: Blob name: {blob_name}")

                # Upload to Azure
                self.log(f"📤 Item {idx}: Connecting to container '{self.container_name}'...")
                container_client = self._blob_container_client()

                self.log(f"📤 Item {idx}: Uploading file to blob: {blob_name}")
                blob_client = container_client.get_blob_client(blob_name)

                with Path(file_path).open("rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

                self.log(f"✅ Item {idx}: Successfully uploaded to: {blob_name}")
                uploaded_count += 1

                results.append(Data(data={"blob_name": blob_name, "container": self.container_name}))

            except (OSError, ValueError, RuntimeError) as e:
                self.log(f"❌ Item {idx}: Error uploading {file_path}: {type(e).__name__}: {e!s}")
                import traceback

                self.log(f"Traceback: {traceback.format_exc()}")
                continue

        self.log(f"✅ Upload complete: {uploaded_count} of {len(self.data_inputs)} file(s) uploaded successfully")
        return results

    def _prepare_content(self, text_content: str, blob_name: str) -> bytes:
        """Prepare content for upload based on file format.

        Args:
            text_content: The text content to upload.
            blob_name: The blob name (used to determine format).

        Returns:
            bytes: The content encoded appropriately for the file format.
        """
        # Get file extension
        extension = Path(blob_name).suffix.lower()
        self.log(f"🔍 _prepare_content: blob_name='{blob_name}', extension='{extension}'")

        # For CSV format, ensure proper line endings
        if extension == ".csv":
            self.log("📊 Preparing CSV content")
            # Normalize line endings for CSV
            normalized_content = text_content.replace("\r\n", "\n").replace("\r", "\n")
            return normalized_content.encode("utf-8")

        # For PDF format, create a proper PDF document
        if extension == ".pdf":
            self.log("📄 Creating PDF document from text")
            return self._create_pdf_from_text(text_content)

        # For all other formats, encode as UTF-8
        self.log(f"📝 Encoding as UTF-8 (extension: {extension})")
        return text_content.encode("utf-8")

    def _create_pdf_from_text(self, text_content: str) -> bytes:
        """Create a valid PDF document from text content using reportlab.

        Args:
            text_content: The text content to convert to PDF.

        Returns:
            bytes: A valid PDF file as bytes.
        """
        self.log(f"📄 _create_pdf_from_text called with {len(text_content)} characters")

        # Minimum PDF header length for validation
        min_pdf_header_length = 8

        try:
            from io import BytesIO

            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

            self.log("✅ reportlab imported successfully")

            # Create a PDF in memory
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18,
            )

            # Container for the 'Flowable' objects
            elements = []

            # Define styles
            styles = getSampleStyleSheet()
            style_normal = styles["Normal"]

            # Split text into paragraphs and add to PDF
            paragraphs = text_content.split("\n")
            self.log(f"📝 Processing {len(paragraphs)} paragraphs")

            for para_text in paragraphs:
                if para_text.strip():  # Skip empty lines
                    # Escape special characters for reportlab
                    escaped_text = para_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    para = Paragraph(escaped_text, style_normal)
                    elements.append(para)
                    elements.append(Spacer(1, 12))  # Add space between paragraphs

            self.log(f"📄 Building PDF with {len(elements)} elements")

            # Build the PDF
            doc.build(elements)

            # Get the PDF bytes
            buffer.seek(0)  # Reset buffer position to start
            pdf_bytes = buffer.read()

            self.log(f"✅ Created valid PDF document with reportlab ({len(pdf_bytes)} bytes)")
            header_check = pdf_bytes[:min_pdf_header_length] if len(pdf_bytes) >= min_pdf_header_length else "Too short"
            self.log(f"🔍 PDF header check: {header_check}")

        except ImportError as import_error:
            self.log(f"⚠️ reportlab not installed: {import_error}")
            self.log("⚠️ Falling back to plain text encoding")
            self.log("💡 Install reportlab with: uv pip install reportlab")
            return text_content.encode("utf-8")

        except (OSError, ValueError, RuntimeError) as e:
            self.log(f"❌ Error creating PDF: {type(e).__name__}: {e!s}")
            import traceback

            self.log(f"Traceback: {traceback.format_exc()}")
            self.log("⚠️ Falling back to plain text encoding")
            return text_content.encode("utf-8")

        return pdf_bytes
