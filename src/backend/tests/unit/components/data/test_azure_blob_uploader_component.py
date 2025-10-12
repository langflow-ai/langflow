import os
import tempfile
import uuid
from pathlib import Path

import pytest
from lfx.components.azure.azure_blob_uploader import AzureBlobUploaderComponent
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


@pytest.mark.skipif(
    not os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    and not (os.environ.get("AZURE_STORAGE_ACCOUNT_NAME") and os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")),
    reason="Azure Storage credentials not defined (need AZURE_STORAGE_CONNECTION_STRING or both "
    "AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY).",
)
class TestAzureBlobUploaderComponent(ComponentTestBaseWithoutClient):
    """Unit tests for the AzureBlobUploaderComponent.

    This test class inherits from ComponentTestBaseWithoutClient and includes several pytest fixtures and a test method
    to verify the functionality of the AzureBlobUploaderComponent.

    Fixtures:
        component_class: Returns the component class to be tested.
        file_names_mapping: Returns an empty list since this component doesn't have version-specific files.
        default_kwargs: Returns an empty dictionary since this component doesn't have any default arguments.
        temp_files: Creates three temporary files with predefined content and yields them as Data objects.
        Cleans up the files after the test.
        azure_container: Creates a unique container for testing, yields the container name, and deletes the container
        and its contents after the test.

    Test Methods:
        test_upload: Tests the upload functionality of the AzureBlobUploaderComponent by uploading temporary files
        to the container and verifying their content.
    """

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return AzureBlobUploaderComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""

    @pytest.fixture
    def default_kwargs(self):
        """Return an empty dictionary since this component doesn't have any default arguments."""
        return {}

    @pytest.fixture
    def temp_files(self):
        """Setup: Create three temporary files."""
        temp_files = []
        contents = [
            b"Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            b"Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            b"Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
            b"nisi ut aliquip ex ea commodo consequat.",
        ]

        for content in contents:
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
                temp_file.write(content)
                temp_file.flush()
                temp_file.close()
                temp_files.append(temp_file.name)

        data = [
            Data(data={"file_path": file_path, "text": Path(file_path).read_text(encoding="utf-8")})
            for file_path in temp_files
        ]

        yield data

        # Teardown: Explicitly delete the files
        for temp_file in temp_files:
            Path(temp_file).unlink()

    @pytest.fixture
    def azure_container(self) -> str:
        """Generate a unique container name."""
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError:
            pytest.skip("azure-storage-blob is not installed")

        container_name = f"test-container-{uuid.uuid4().hex[:8]}"

        # Initialize BlobServiceClient using environment variables
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

        if connection_string:
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        elif account_name and account_key:
            account_url = f"https://{account_name}.blob.core.windows.net"
            blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)
        else:
            pytest.skip("Azure Storage credentials not available")

        try:
            # Create a container
            container_client = blob_service_client.create_container(container_name)

            yield container_name

        finally:
            # Teardown: Delete the container and its contents
            try:
                container_client = blob_service_client.get_container_client(container_name)
                container_client.delete_container()
            except Exception as e:
                pytest.fail(f"Error during teardown: {e}")

    def test_upload(self, temp_files, azure_container):
        """Test uploading files to Azure Blob Storage."""
        component = AzureBlobUploaderComponent()

        # Set Azure credentials from environment variables
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

        component_attrs = {
            "container_name": azure_container,
            "strategy": "Store Original File",
            "data_inputs": temp_files,
            "blob_prefix": "test",
            "strip_path": True,
            "overwrite": True,
        }

        if connection_string:
            component_attrs["connection_string"] = connection_string
        elif account_name and account_key:
            component_attrs["account_name"] = account_name
            component_attrs["account_key"] = account_key

        component.set_attributes(component_attrs)

        component.process_files()

        # Check if the files were uploaded
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError:
            pytest.skip("azure-storage-blob is not installed")

        if connection_string:
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        else:
            account_url = f"https://{account_name}.blob.core.windows.net"
            blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)

        container_client = blob_service_client.get_container_client(azure_container)

        for temp_file in temp_files:
            blob_name = f"test/{Path(temp_file.data['file_path']).name}"
            blob_client = container_client.get_blob_client(blob_name)
            blob_data = blob_client.download_blob()
            downloaded_content = blob_data.readall()

            with Path(temp_file.data["file_path"]).open("rb") as f:
                assert downloaded_content == f.read()
