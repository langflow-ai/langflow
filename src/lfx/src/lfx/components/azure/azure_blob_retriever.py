from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MultiselectInput, Output, SecretStrInput, StrInput
from lfx.schema import Message


class AzureBlobRetrieverComponent(Component):
    """Retrieve files from Azure Blob Storage.

    Lists and retrieves blobs from an Azure Blob Storage container.
    Requires azure-storage-blob package.
    """

    display_name = "Azure Blob Retrieve"
    description = "Retrieve files from Azure Blob Storage."
    icon = "Azure"
    name = "AzureBlobRetrieve"

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
            display_name="Blob Prefix Filter (Optional)",
            info="Optional prefix to filter blobs (e.g., 'uploads/2024/'). Leave empty to list all blobs.",
            required=False,
            real_time_refresh=True,
        ),
        MultiselectInput(
            name="blob_names",
            display_name="Select Files",
            info="Select one or more files to retrieve. Options load after entering connection details above.",
            options=[],
            value=[],
            required=False,
            refresh_button=True,
            real_time_refresh=True,
        ),
    ]

    outputs = [
        Output(display_name="Message", name="message", method="retrieve_blobs"),
    ]

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        """Update container list and blob list when connection info changes."""
        # Ensure container_name value is always a string
        if "container_name" in build_config and "value" not in build_config["container_name"]:
            build_config["container_name"]["value"] = ""

        # Ensure blob_names value is always a list (required by MultiselectInput)
        if "blob_names" in build_config and (
            "value" not in build_config["blob_names"] or not isinstance(build_config["blob_names"].get("value"), list)
        ):
            build_config["blob_names"]["value"] = []

        # Get current values - use field_value when that specific field is changing
        if field_name == "connection_string":
            connection_string = field_value or ""
        else:
            connection_string = build_config.get("connection_string", {}).get("value", "")

        if field_name == "container_name" and not isinstance(field_value, dict):
            container_name = field_value or ""
        else:
            container_name = build_config.get("container_name", {}).get("value", "")

        if field_name == "blob_prefix":
            blob_prefix = field_value or ""
        else:
            blob_prefix = build_config.get("blob_prefix", {}).get("value", "") or ""

        # Step 1: Populate container dropdown whenever we have a connection string
        if connection_string:
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError:
                build_config["container_name"]["options"] = []
                build_config["container_name"]["info"] = (
                    "⚠️ azure-storage-blob is not installed. Install with: uv pip install azure-storage-blob"
                )
                build_config["blob_names"]["options"] = []
                build_config["blob_names"]["value"] = []
                build_config["blob_names"]["info"] = "Install azure-storage-blob first"
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
                    build_config["blob_names"]["options"] = []
                    build_config["blob_names"]["value"] = []
                    build_config["blob_names"]["info"] = "Select a container first"

            except Exception as e:  # noqa: BLE001
                build_config["container_name"]["options"] = []
                build_config["container_name"]["info"] = f"⚠️ Error: {str(e)[:100]}"
                build_config["blob_names"]["options"] = []
                build_config["blob_names"]["value"] = []
                build_config["blob_names"]["info"] = "Fix connection error first"
                return build_config
        else:
            # No connection string yet
            build_config["container_name"]["options"] = []
            build_config["container_name"]["info"] = "Enter connection string first"
            build_config["blob_names"]["options"] = []
            build_config["blob_names"]["value"] = []
            build_config["blob_names"]["info"] = "Enter connection string and select container"
            return build_config

        # Step 2: Populate blob dropdown whenever we have both connection string and container
        if connection_string and container_name:
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError:
                build_config["blob_names"]["options"] = []
                build_config["blob_names"]["value"] = []
                build_config["blob_names"]["info"] = "⚠️ azure-storage-blob is not installed."
                return build_config

            try:
                # List blobs from Azure
                blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                container_client = blob_service_client.get_container_client(container_name)

                # List blobs with optional prefix
                blobs = list(container_client.list_blobs(name_starts_with=blob_prefix if blob_prefix else None))
                blob_options = [blob.name for blob in blobs]

                build_config["blob_names"]["options"] = blob_options
                # Only reset value when container changes, not when prefix changes
                if field_name == "container_name":
                    build_config["blob_names"]["value"] = []
                build_config["blob_names"]["info"] = f"Found {len(blob_options)} blob(s)"

            except Exception as e:  # noqa: BLE001
                # If connection fails, show error in info
                build_config["blob_names"]["options"] = []
                build_config["blob_names"]["value"] = []
                build_config["blob_names"]["info"] = f"⚠️ Error: {str(e)[:100]}"

        else:
            # Not enough connection info yet
            build_config["blob_names"]["options"] = []
            build_config["blob_names"]["value"] = []
            if not container_name:
                build_config["blob_names"]["info"] = "Select a container to load blobs"

        return build_config

    def retrieve_blobs(self) -> Message:
        """Retrieve blobs from Azure Blob Storage."""
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

        # Initialize blob service client
        blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        container_client = blob_service_client.get_container_client(self.container_name)

        all_content = []

        # Check if specific blob names were selected (from multiselect)
        selected_blobs = []

        if self.blob_names is not None and isinstance(self.blob_names, list):
            # MultiselectInput returns a list - filter out any empty strings
            selected_blobs = [name for name in self.blob_names if name]
            self.log(f"Selected {len(selected_blobs)} blob(s): {selected_blobs}")

        # Require blob selection
        if not selected_blobs:
            self.log("No blobs selected. Please select one or more blobs from the dropdown.")
            return Message(text="Please select one or more blobs to retrieve.")

        # Retrieve selected blobs
        self.log(f"Retrieving {len(selected_blobs)} blob(s) from {self.container_name}...")

        for blob_name in selected_blobs:
            try:
                self.log(f"Retrieving: {blob_name}")
                blob_client = container_client.get_blob_client(blob_name)
                blob_data = blob_client.download_blob()
                content = blob_data.readall()

                text_content = None

                # Check if it's a PDF file
                if blob_name.lower().endswith(".pdf"):
                    try:
                        import io

                        from pypdf import PdfReader

                        pdf_file = io.BytesIO(content)
                        reader = PdfReader(pdf_file)

                        # Extract text from all pages
                        pdf_text = []
                        for page_num, page in enumerate(reader.pages, 1):
                            page_text = page.extract_text()
                            if page_text.strip():
                                pdf_text.append(f"--- Page {page_num} ---\n{page_text}")

                        if pdf_text:
                            text_content = "\n\n".join(pdf_text)
                            self.log(f"Successfully extracted text from PDF {blob_name} ({len(reader.pages)} pages)")
                        else:
                            text_content = f"[PDF file with {len(reader.pages)} pages, but no text could be extracted]"
                            self.log(f"PDF {blob_name} has no extractable text")

                    except ImportError:
                        text_content = "[PDF file - pypdf not installed. Install with: uv pip install pypdf]"
                        self.log("pypdf library not available for PDF parsing")
                    except Exception as e:  # noqa: BLE001
                        text_content = f"[PDF file - error extracting text: {e!s}]"
                        self.log(f"Error parsing PDF {blob_name}: {e}")
                else:
                    # Try multiple encodings to decode as text for non-PDF files
                    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

                    for encoding in encodings:
                        try:
                            text_content = content.decode(encoding)
                            self.log(f"Successfully decoded {blob_name} using {encoding}")
                            break
                        except (UnicodeDecodeError, AttributeError):
                            continue

                    # If all encodings fail, try to detect if it's actually text
                    if text_content is None:
                        # Check if content is mostly printable ASCII/text
                        try:
                            # Try with error handling to replace bad bytes
                            text_content = content.decode("utf-8", errors="replace")
                            self.log(f"Decoded {blob_name} with error replacement")
                        except Exception:  # noqa: BLE001
                            text_content = f"[Binary content, {len(content)} bytes - unable to decode as text]"
                            self.log(f"Could not decode {blob_name} - treating as binary")

                all_content.append(text_content)
                self.log(f"✓ Retrieved: {blob_name} ({len(content)} bytes)")
            except Exception as e:  # noqa: BLE001
                error_msg = f"Error retrieving {blob_name}: {e}"
                self.log(error_msg)
                all_content.append(error_msg)

        if not all_content:
            return Message(text="No content retrieved from selected blobs.")

        # Use separator to join multiple file contents (default: double newline like Read File)
        separator = getattr(self, "separator", "\n\n") or "\n\n"
        combined_text = separator.join(all_content)

        self.log(f"✓ Successfully retrieved {len(all_content)} blob(s)")

        return Message(
            text=combined_text,
            sender="Azure Blob Storage",
            sender_name=f"Retrieved {len(all_content)} blob(s) from {self.container_name}",
        )
