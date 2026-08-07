"""Unit tests for AzureBlobStorageService input validation.

These tests run offline. They assert that malformed flow_id / file_name values
are rejected at the storage layer BEFORE any Azure call is attempted, mirroring
the equivalent S3/GCS backend tests (regression pattern for GHSA-rcjh-r59h-gq37 --
defense in depth at the object-storage backend).
"""

from unittest.mock import Mock, patch

import pytest
from langflow.services.storage.azure_blob import AzureBlobStorageService

_FAKE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=ZmFrZWtleQ==;EndpointSuffix=core.windows.net"
)


@pytest.fixture
def mock_settings_service(tmp_path):
    """Settings configured for Azure Blob storage with a stable container / prefix."""
    settings_service = Mock()
    settings_service.settings.config_dir = str(tmp_path)
    settings_service.settings.object_storage_bucket_name = "langflow-unit-test-container"
    settings_service.settings.object_storage_prefix = "test-prefix"
    settings_service.settings.object_storage_tags = {}
    return settings_service


@pytest.fixture
def mock_session_service():
    return Mock()


def _build_service(mock_session, mock_settings, monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", _FAKE_CONNECTION_STRING)
    with patch("azure.storage.blob.aio.BlobServiceClient.from_connection_string") as mock_from_cs:
        mock_service_client = Mock()
        mock_service_client.get_container_client.return_value = Mock()
        mock_from_cs.return_value = mock_service_client
        return AzureBlobStorageService(mock_session, mock_settings)


@pytest.fixture
def azure_service_offline(mock_session_service, mock_settings_service, monkeypatch):
    """AzureBlobStorageService that fails loudly if any Azure call is attempted.

    Validation MUST short-circuit before any blob/container client method is
    invoked. If a test reaches one of these assertions, the validation guard is
    missing or bypassed.
    """
    service = _build_service(mock_session_service, mock_settings_service, monkeypatch)

    def _no_azure_calls(*_args, **_kwargs):
        msg = "validation should have rejected this input before reaching Azure"
        raise AssertionError(msg)

    monkeypatch.setattr(service, "_get_blob_client", _no_azure_calls)
    monkeypatch.setattr(service._container_client, "list_blobs", _no_azure_calls)
    return service


def test_init_creates_container_reference(mock_session_service, mock_settings_service, monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", _FAKE_CONNECTION_STRING)
    with patch("azure.storage.blob.aio.BlobServiceClient.from_connection_string") as mock_from_cs:
        service_client = Mock()
        mock_from_cs.return_value = service_client

        service = AzureBlobStorageService(mock_session_service, mock_settings_service)

        service_client.get_container_client.assert_called_once_with("langflow-unit-test-container")
        assert service._container_client is service_client.get_container_client.return_value


def test_init_requires_connection_string_or_account(mock_session_service, mock_settings_service, monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_NAME", raising=False)

    with pytest.raises(ValueError, match="AZURE_STORAGE_CONNECTION_STRING"):
        AzureBlobStorageService(mock_session_service, mock_settings_service)


def test_init_uses_default_azure_credential_with_account_name(mock_session_service, mock_settings_service, monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "myaccount")

    with (
        patch("azure.identity.aio.DefaultAzureCredential") as mock_credential_cls,
        patch("azure.storage.blob.aio.BlobServiceClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.get_container_client.return_value = Mock()

        AzureBlobStorageService(mock_session_service, mock_settings_service)

        mock_client_cls.assert_called_once_with(
            account_url="https://myaccount.blob.core.windows.net",
            credential=mock_credential_cls.return_value,
        )


_MALICIOUS_FLOW_IDS = [
    "/etc",
    "..",
    "../other",
    "..\\other",
    "flow/sub",
    "flow\\sub",
    "with\x00null",
    "",
]

_MALICIOUS_FILE_NAMES = [
    "../passwd",
    "..\\passwd",
    "sub/passwd",
    "sub\\passwd",
    "with\x00null",
    "",
]


@pytest.mark.asyncio
class TestAzureBlobStorageServicePathValidation:
    """GHSA-rcjh-r59h-gq37: Azure Blob backend must reject untrusted identifiers locally."""

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_rejects_malicious_flow_id(self, azure_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await azure_service_offline.get_file(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_save_file_rejects_malicious_flow_id(self, azure_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await azure_service_offline.save_file(malicious_flow_id, "passwd", b"x")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_delete_file_rejects_malicious_flow_id(self, azure_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await azure_service_offline.delete_file(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_size_rejects_malicious_flow_id(self, azure_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await azure_service_offline.get_file_size(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_stream_rejects_malicious_flow_id(self, azure_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            # AsyncIterator functions don't raise until first iteration.
            async for _ in azure_service_offline.get_file_stream(malicious_flow_id, "passwd"):
                pass

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_list_files_rejects_malicious_flow_id(self, azure_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await azure_service_offline.list_files(malicious_flow_id)

    @pytest.mark.parametrize("malicious_file_name", _MALICIOUS_FILE_NAMES)
    async def test_get_file_rejects_malicious_file_name(self, azure_service_offline, malicious_file_name):
        with pytest.raises(ValueError, match="Invalid"):
            await azure_service_offline.get_file("legit_flow", malicious_file_name)

    @pytest.mark.parametrize("malicious_file_name", _MALICIOUS_FILE_NAMES)
    async def test_save_file_rejects_malicious_file_name(self, azure_service_offline, malicious_file_name):
        with pytest.raises(ValueError, match="Invalid"):
            await azure_service_offline.save_file("legit_flow", malicious_file_name, b"x")

    async def test_get_file_rejects_absolute_flow_id_collapse(self, azure_service_offline):
        """Direct regression for the public-build arbitrary-file-read at the Azure layer.

        Pre-vuln shape: ``build_full_path("/etc", "hosts")`` would produce a key that
        resolved to an attacker-controlled blob name. Validation must reject the shape.
        """
        with pytest.raises(ValueError, match="Invalid"):
            await azure_service_offline.get_file("/etc", "hosts")


@pytest.mark.asyncio
async def test_save_file_append_not_supported(azure_service_offline):
    with pytest.raises(NotImplementedError, match="Append"):
        await azure_service_offline.save_file("legit_flow", "file.txt", b"x", append=True)
