"""Unit tests for GCSStorageService input validation.

These tests run offline. They assert that malformed flow_id / file_name values
are rejected at the storage layer BEFORE any GCS call is attempted, mirroring
the equivalent S3 backend tests (regression pattern for GHSA-rcjh-r59h-gq37 --
defense in depth at the object-storage backend).
"""

from unittest.mock import Mock

import pytest
from langflow.services.storage.gcs import GCSStorageService


@pytest.fixture
def mock_settings_service(tmp_path):
    """Settings configured for GCS with a stable bucket / prefix."""
    settings_service = Mock()
    settings_service.settings.config_dir = str(tmp_path)
    settings_service.settings.object_storage_bucket_name = "langflow-unit-test-bucket"
    settings_service.settings.object_storage_prefix = "test-prefix"
    settings_service.settings.object_storage_tags = {}
    return settings_service


@pytest.fixture
def mock_session_service():
    return Mock()


@pytest.fixture
def gcs_service_offline(mock_session_service, mock_settings_service, monkeypatch):
    """GCSStorageService that fails loudly if any GCS call is attempted.

    Validation MUST short-circuit before any of the blocking helper methods
    (which run in a worker thread via asyncio.to_thread) are invoked. If a test
    reaches one of these assertions, the validation guard is missing or bypassed.
    """
    monkeypatch.setattr("google.cloud.storage.Client", lambda: Mock())
    service = GCSStorageService(mock_session_service, mock_settings_service)

    def _no_gcs_calls(*_args, **_kwargs):
        msg = "validation should have rejected this input before reaching GCS"
        raise AssertionError(msg)

    for method_name in (
        "_get_blob",
        "_upload_blob",
        "_download_blob",
        "_get_existing_blob",
        "_delete_blob",
        "_list_blob_names",
    ):
        monkeypatch.setattr(service, method_name, _no_gcs_calls)
    return service


def test_init_creates_bucket_reference(mock_session_service, mock_settings_service, monkeypatch):
    client = Mock()
    monkeypatch.setattr("google.cloud.storage.Client", lambda: client)

    service = GCSStorageService(mock_session_service, mock_settings_service)

    client.bucket.assert_called_once_with("langflow-unit-test-bucket")
    assert service._bucket is client.bucket.return_value


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
class TestGCSStorageServicePathValidation:
    """GHSA-rcjh-r59h-gq37: GCS backend must reject untrusted identifiers locally."""

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_rejects_malicious_flow_id(self, gcs_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await gcs_service_offline.get_file(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_save_file_rejects_malicious_flow_id(self, gcs_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await gcs_service_offline.save_file(malicious_flow_id, "passwd", b"x")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_delete_file_rejects_malicious_flow_id(self, gcs_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await gcs_service_offline.delete_file(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_size_rejects_malicious_flow_id(self, gcs_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await gcs_service_offline.get_file_size(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_stream_rejects_malicious_flow_id(self, gcs_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            # AsyncIterator functions don't raise until first iteration.
            async for _ in gcs_service_offline.get_file_stream(malicious_flow_id, "passwd"):
                pass

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_list_files_rejects_malicious_flow_id(self, gcs_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await gcs_service_offline.list_files(malicious_flow_id)

    @pytest.mark.parametrize("malicious_file_name", _MALICIOUS_FILE_NAMES)
    async def test_get_file_rejects_malicious_file_name(self, gcs_service_offline, malicious_file_name):
        with pytest.raises(ValueError, match="Invalid"):
            await gcs_service_offline.get_file("legit_flow", malicious_file_name)

    @pytest.mark.parametrize("malicious_file_name", _MALICIOUS_FILE_NAMES)
    async def test_save_file_rejects_malicious_file_name(self, gcs_service_offline, malicious_file_name):
        with pytest.raises(ValueError, match="Invalid"):
            await gcs_service_offline.save_file("legit_flow", malicious_file_name, b"x")

    async def test_get_file_rejects_absolute_flow_id_collapse(self, gcs_service_offline):
        """Direct regression for the public-build arbitrary-file-read at the GCS layer.

        Pre-vuln shape: ``build_full_path("/etc", "hosts")`` would produce a key that
        resolved to an attacker-controlled object path. Validation must reject the shape.
        """
        with pytest.raises(ValueError, match="Invalid"):
            await gcs_service_offline.get_file("/etc", "hosts")


@pytest.mark.asyncio
async def test_save_file_append_not_supported(gcs_service_offline):
    with pytest.raises(NotImplementedError, match="Append"):
        await gcs_service_offline.save_file("legit_flow", "file.txt", b"x", append=True)
