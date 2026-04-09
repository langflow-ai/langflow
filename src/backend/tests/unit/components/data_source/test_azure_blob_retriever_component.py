import os
import tempfile
import uuid
from pathlib import Path

import pytest
from lfx.components.azure.azure_blob_retriever import AzureBlobRetrieverComponent

from tests.base import ComponentTestBaseWithoutClient


@pytest.mark.skipif(
    not os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    and not (os.environ.get("AZURE_STORAGE_ACCOUNT_NAME") and os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")),
    reason="Azure Storage credentials not defined (need AZURE_STORAGE_CONNECTION_STRING or both "
    "AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY).",
)
class TestAzureBlobRetrieverComponent(ComponentTestBaseWithoutClient):
    """Unit tests for the AzureBlobRetrieverComponent.

    This test class inherits from ComponentTestBaseWithoutClient and includes several pytest fixtures and test methods
    to verify the functionality of the AzureBlobRetrieverComponent.

    Fixtures:
        component_class: Returns the component class to be tested.
        file_names_mapping: Returns an empty list since this component doesn't have version-specific files.
        default_kwargs: Returns an empty dictionary since this component doesn't have any default arguments.
        azure_container_with_files: Creates a unique container with test files for testing retrieval.

    Test Methods:
        test_retrieve_single_blob: Tests retrieving a single blob by name.
        test_retrieve_multiple_blobs: Tests retrieving multiple blobs with a prefix.
    """

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return AzureBlobRetrieverComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""

    @pytest.fixture
    def default_kwargs(self):
        """Return an empty dictionary since this component doesn't have any default arguments."""
        return {}

    @pytest.fixture
    def azure_container_with_files(self) -> tuple[str, list[str]]:
        """Create a container and upload test files."""
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

        # Create container
        container_client = blob_service_client.create_container(container_name)

        # Upload test files
        test_files = []
        test_contents = [
            b"Test content 1",
            b"Test content 2",
            b"Test content 3",
        ]

        try:
            for i, content in enumerate(test_contents):
                blob_name = f"test/file{i + 1}.txt"
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(content, overwrite=True)
                test_files.append(blob_name)

            yield container_name, test_files

        finally:
            # Teardown: Delete the container and its contents
            try:
                container_client.delete_container()
            except Exception as e:
                pytest.fail(f"Error during teardown: {e}")

    def test_retrieve_single_blob(self, azure_container_with_files):
        """Test retrieving a single blob from Azure Blob Storage."""
        container_name, test_files = azure_container_with_files
        component = AzureBlobRetrieverComponent()

        # Set Azure credentials from environment variables
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

        component_attrs = {
            "container_name": container_name,
            "blob_name": test_files[0],
            "list_all": False,
        }

        if connection_string:
            component_attrs["connection_string"] = connection_string
        elif account_name and account_key:
            component_attrs["account_name"] = account_name
            component_attrs["account_key"] = account_key

        component.set_attributes(component_attrs)

        # Retrieve the blob
        results = component.retrieve_blobs()

        # Verify results
        assert len(results) == 1
        assert results[0].data["blob_name"] == test_files[0]
        assert results[0].data["text"] == "Test content 1"

    def test_retrieve_multiple_blobs(self, azure_container_with_files):
        """Test retrieving multiple blobs with a prefix from Azure Blob Storage."""
        container_name, test_files = azure_container_with_files
        component = AzureBlobRetrieverComponent()

        # Set Azure credentials from environment variables
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

        component_attrs = {
            "container_name": container_name,
            "blob_prefix": "test/",
            "list_all": True,
            "max_results": 0,  # No limit
        }

        if connection_string:
            component_attrs["connection_string"] = connection_string
        elif account_name and account_key:
            component_attrs["account_name"] = account_name
            component_attrs["account_key"] = account_key

        component.set_attributes(component_attrs)

        # Retrieve all blobs with prefix
        results = component.retrieve_blobs()

        # Verify results
        assert len(results) == 3
        retrieved_names = [result.data["blob_name"] for result in results]
        assert set(retrieved_names) == set(test_files)

    def test_retrieve_with_download_path(self, azure_container_with_files):
        """Test retrieving a blob and saving it to a local path."""
        container_name, test_files = azure_container_with_files
        component = AzureBlobRetrieverComponent()

        # Set Azure credentials from environment variables
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

        # Create a temporary directory for downloads
        with tempfile.TemporaryDirectory() as temp_dir:
            component_attrs = {
                "container_name": container_name,
                "blob_name": test_files[0],
                "list_all": False,
                "download_path": temp_dir,
            }

            if connection_string:
                component_attrs["connection_string"] = connection_string
            elif account_name and account_key:
                component_attrs["account_name"] = account_name
                component_attrs["account_key"] = account_key

            component.set_attributes(component_attrs)

            # Retrieve the blob
            results = component.retrieve_blobs()

            # Verify file was downloaded
            assert len(results) == 1
            assert "file_path" in results[0].data
            downloaded_file = Path(results[0].data["file_path"])
            assert downloaded_file.exists()
            assert downloaded_file.read_text() == "Test content 1"
