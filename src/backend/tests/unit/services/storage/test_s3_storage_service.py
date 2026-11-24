"""Unit tests for S3StorageService input validation.

These tests run offline. They assert that malformed flow_id / file_name values
are rejected at the storage layer BEFORE any AWS call is attempted, so the
boundary fix in chat.py is not the only line of defense for callers that reach
the S3 backend with untrusted identifiers.

Regression for GHSA-rcjh-r59h-gq37 (defense in depth at the S3 backend).
"""

import asyncio
import os
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import web
from botocore.endpoint import MAX_POOL_CONNECTIONS
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

    def _no_aws_calls(**_kwargs):
        msg = "validation should have rejected this input before reaching S3"
        raise AssertionError(msg)

    monkeypatch.setattr(service, "_get_client", _no_aws_calls)
    return service


async def test_get_client_builds_one_aiobotocore_client_per_loop(mock_session_service, mock_settings_service):
    service = S3StorageService(mock_session_service, mock_settings_service)
    session = Mock()
    client = object()
    session.create_client.return_value.__aenter__ = AsyncMock(return_value=client)
    session.create_client.return_value.__aexit__ = AsyncMock(return_value=None)
    service.session = session

    async with service._get_client() as first, service._get_client() as second:
        pass

    session.create_client.assert_called_once_with("s3")
    assert first is second is client
    # Leaving the block does not close it; teardown does.
    session.create_client.return_value.__aexit__.assert_not_called()
    await service.teardown()
    session.create_client.return_value.__aexit__.assert_called_once()


async def test_open_downloads_leave_the_shared_client_free(mock_session_service, mock_settings_service, monkeypatch):
    # A download holds its connection until the HTTP client reading it is done, as long as
    # that takes. This local S3 sends half of each object and waits.
    release = asyncio.Event()

    async def s3(request):
        if request.method == "HEAD":
            return web.Response(headers={"Content-Length": "5"})
        response = web.StreamResponse(headers={"Content-Length": "16384"})
        await response.prepare(request)
        await response.write(b"x" * 8192)
        await release.wait()
        return response

    app = web.Application()
    app.router.add_route("*", "/{key:.*}", s3)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", os.devnull)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", os.devnull)
    monkeypatch.setenv("AWS_ENDPOINT_URL", f"http://127.0.0.1:{runner.addresses[0][1]}")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    service = S3StorageService(mock_session_service, mock_settings_service)

    downloads = [service.get_file_stream("flow", f"download-{i}.bin") for i in range(MAX_POOL_CONNECTIONS)]
    try:
        for download in downloads:
            await anext(download)
        # The size check a new download runs first, on the same loop as the open ones.
        assert await asyncio.wait_for(service.get_file_size("flow", "small.txt"), timeout=5) == 5
    finally:
        for download in downloads:
            await download.aclose()
        release.set()
        await service.teardown()
        await runner.cleanup()


async def test_a_closed_loop_another_thread_drops_first_is_skipped(mock_session_service, mock_settings_service):
    # Every thread drops the closed loops it finds, so another one can drop a loop while
    # this one is still going through them.
    service = S3StorageService(mock_session_service, mock_settings_service)

    class ClosedLoop:
        def is_closed(self):
            service._clients.pop(self, None)
            return True

    loop = asyncio.get_running_loop()
    client = object()
    service._clients = {ClosedLoop(): None, ClosedLoop(): None, loop: (None, client)}

    async with service._get_client() as got:
        assert got is client
    assert list(service._clients) == [loop]


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


class TestS3BuildFullPathValidation:
    """``build_full_path`` is a public key builder, so it validates its own inputs.

    Path shape must never stand in for authorization: a caller that composes a key without
    going through one of the file operations still cannot address a foreign namespace.
    """

    @pytest.mark.parametrize("malicious_flow_id", [fid for fid in _MALICIOUS_FLOW_IDS if fid])
    def test_build_full_path_rejects_malicious_flow_id(self, s3_service_offline, malicious_flow_id):
        with pytest.raises(ValueError, match="Invalid"):
            s3_service_offline.build_full_path(malicious_flow_id, "file.txt")

    @pytest.mark.parametrize("malicious_file_name", [name for name in _MALICIOUS_FILE_NAMES if name])
    def test_build_full_path_rejects_malicious_file_name(self, s3_service_offline, malicious_file_name):
        with pytest.raises(ValueError, match="Invalid"):
            s3_service_offline.build_full_path("legit_flow", malicious_file_name)

    def test_build_full_path_allows_empty_file_name_for_listing_prefix(self, s3_service_offline):
        """``list_files`` builds a prefix with an empty file name; that must keep working."""
        assert s3_service_offline.build_full_path("legit_flow", "") == "test-prefix/legit_flow/"

    def test_build_full_path_accepts_legitimate_identifiers(self, s3_service_offline):
        assert s3_service_offline.build_full_path("legit_flow", "file.txt") == "test-prefix/legit_flow/file.txt"


MD5 = "0cc175b9c0f1b6a831c399e269772661"  # pragma: allowlist secret - md5("a")


class TestEtagAsMd5:
    """An ETag is the body's MD5 only for a single-part upload without KMS or customer keys."""

    @pytest.mark.parametrize(
        ("head", "expected"),
        [
            ({"ETag": f'"{MD5}"'}, MD5),
            (
                {"ETag": f'"{MD5}"', "ServerSideEncryption": "AES256"},
                MD5,
            ),
            ({"ETag": f'"{MD5}-3"'}, None),
            ({"ETag": f'"{MD5}"', "ServerSideEncryption": "aws:kms"}, None),
            ({"ETag": f'"{MD5}"', "ServerSideEncryption": "aws:kms:dsse"}, None),
            ({"ETag": f'"{MD5}"', "SSECustomerAlgorithm": "AES256"}, None),
            ({}, None),
        ],
    )
    def test_md5_from_head(self, head, expected):
        from langflow.services.storage.s3 import md5_from_head

        assert md5_from_head(head) == expected
