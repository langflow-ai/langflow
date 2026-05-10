"""Unit tests for S3StorageService input validation.

These tests run offline. They assert that malformed flow_id / file_name values
are rejected at the storage layer BEFORE any AWS call is attempted, so the
boundary fix in chat.py is not the only line of defense for callers that reach
the S3 backend with untrusted identifiers.

Regression for GHSA-rcjh-r59h-gq37 (defense in depth at the S3 backend).
"""

from unittest.mock import Mock

import pytest
from langflow.services.storage.s3 import S3StorageService


@pytest.fixture
def mock_settings_service(tmp_path):
    """Settings configured for S3 with a stable bucket / prefix."""
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
def s3_service_offline(mock_session_service, mock_settings_service, monkeypatch):
    """S3StorageService that fails loudly if any AWS call is attempted.

    Validation MUST short-circuit before _get_client is invoked. If a test
    reaches this assertion, the validation guard is missing or bypassed.
    """
    service = S3StorageService(mock_session_service, mock_settings_service)

    def _no_aws_calls():
        msg = "validation should have rejected this input before reaching S3"
        raise AssertionError(msg)

    monkeypatch.setattr(service, "_get_client", _no_aws_calls)
    return service


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
class TestS3StorageServicePathValidation:
    """GHSA-rcjh-r59h-gq37: S3 backend must reject untrusted identifiers locally."""

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_rejects_malicious_flow_id(self, s3_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await s3_service_offline.get_file(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_save_file_rejects_malicious_flow_id(self, s3_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await s3_service_offline.save_file(malicious_flow_id, "passwd", b"x")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_delete_file_rejects_malicious_flow_id(self, s3_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await s3_service_offline.delete_file(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_size_rejects_malicious_flow_id(self, s3_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await s3_service_offline.get_file_size(malicious_flow_id, "passwd")

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_get_file_stream_rejects_malicious_flow_id(self, s3_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            # AsyncIterator functions don't raise until first iteration.
            async for _ in s3_service_offline.get_file_stream(malicious_flow_id, "passwd"):
                pass

    @pytest.mark.parametrize("malicious_flow_id", _MALICIOUS_FLOW_IDS)
    async def test_list_files_rejects_malicious_flow_id(self, s3_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            await s3_service_offline.list_files(malicious_flow_id)

    @pytest.mark.parametrize("malicious_file_name", _MALICIOUS_FILE_NAMES)
    async def test_get_file_rejects_malicious_file_name(self, s3_service_offline, malicious_file_name):
        with pytest.raises(ValueError, match="Invalid"):
            await s3_service_offline.get_file("legit_flow", malicious_file_name)

    @pytest.mark.parametrize("malicious_file_name", _MALICIOUS_FILE_NAMES)
    async def test_save_file_rejects_malicious_file_name(self, s3_service_offline, malicious_file_name):
        with pytest.raises(ValueError, match="Invalid"):
            await s3_service_offline.save_file("legit_flow", malicious_file_name, b"x")

    async def test_get_file_rejects_absolute_flow_id_collapse(self, s3_service_offline):
        """Direct regression for the public-build arbitrary-file-read at the S3 layer.

        Pre-vuln: ``build_full_path("/etc", "hosts")`` produced a key that resolved
        to an attacker-controlled S3 path. Validation must reject the shape.
        """
        with pytest.raises(ValueError, match="Invalid"):
            await s3_service_offline.get_file("/etc", "hosts")
