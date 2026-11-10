"""Unit tests for S3StorageService input validation.

These tests run offline. They assert that malformed flow_id / file_name values
are rejected at the storage layer BEFORE any AWS call is attempted, so the
boundary fix in chat.py is not the only line of defense for callers that reach
the S3 backend with untrusted identifiers.

Regression for GHSA-rcjh-r59h-gq37 (defense in depth at the S3 backend).
"""

import asyncio
import hashlib
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
OTHER = "92eb5ffee6ae2fec3ad71c777531578f"  # pragma: allowlist secret - md5("b")


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
            # Where the ETag is not an MD5, the label this service writes answers instead.
            ({"ETag": f'"{OTHER}-3"', "Metadata": {"md5": MD5}}, MD5),
            ({"ETag": f'"{OTHER}"', "ServerSideEncryption": "aws:kms", "Metadata": {"md5": MD5}}, MD5),
            ({"ETag": f'"{OTHER}-3"', "Metadata": {"md5": MD5.upper()}}, MD5),
            # The ETag is computed by S3; a label disagreeing with it loses.
            ({"ETag": f'"{MD5}"', "Metadata": {"md5": OTHER}}, MD5),
            # A label that is not an MD5 is not trusted as one.
            ({"ETag": f'"{OTHER}-3"', "Metadata": {"md5": "not-a-checksum"}}, None),
            ({"ETag": f'"{OTHER}-3"', "Metadata": {}}, None),
        ],
    )
    def test_md5_from_head(self, head, expected):
        from langflow.services.storage.s3 import md5_from_head

        assert md5_from_head(head) == expected


class _RecordingS3Client:
    """Records what each write sends; ``copy_error`` makes the label's self-copy fail."""

    def __init__(self, copy_error: Exception | None = None):
        self.calls: list[tuple[str, dict]] = []
        self._copy_error = copy_error

    async def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))

    async def create_multipart_upload(self, **kwargs):
        self.calls.append(("create_multipart_upload", kwargs))
        return {"UploadId": "u1"}

    async def upload_part(self, **kwargs):
        self.calls.append(("upload_part", kwargs))
        return {"ETag": f'"{kwargs["PartNumber"]}"'}

    async def complete_multipart_upload(self, **kwargs):
        self.calls.append(("complete_multipart_upload", kwargs))

    async def copy_object(self, **kwargs):
        self.calls.append(("copy_object", kwargs))
        if self._copy_error is not None:
            raise self._copy_error

    def named(self, name: str) -> list[dict]:
        return [kwargs for call, kwargs in self.calls if call == name]


def _recording_service(mock_session_service, mock_settings_service, client):
    from contextlib import asynccontextmanager

    service = S3StorageService(mock_session_service, mock_settings_service)

    @asynccontextmanager
    async def _client(**_kwargs):
        yield client

    service._get_client = _client
    return service


async def _chunks(*parts: bytes):
    for part in parts:
        yield part


class TestMd5Label:
    """Every object this service writes carries its MD5 as ``x-amz-meta-md5``."""

    async def test_save_file_labels_the_object(self, mock_session_service, mock_settings_service):
        client = _RecordingS3Client()
        service = _recording_service(mock_session_service, mock_settings_service, client)

        await service.save_file("ns", "a.pdf", b"a")

        assert client.named("put_object")[0]["Metadata"] == {"md5": MD5}

    async def test_a_small_stream_is_one_labelled_put(self, mock_session_service, mock_settings_service):
        client = _RecordingS3Client()
        service = _recording_service(mock_session_service, mock_settings_service, client)

        written = await service.save_file_stream("ns", "a.pdf", _chunks(b"a"))

        assert written == 1
        assert [call for call, _ in client.calls] == ["put_object"]
        assert client.named("put_object")[0]["Metadata"] == {"md5": MD5}

    async def test_a_multipart_stream_is_labelled_by_a_copy_onto_itself(
        self, mock_session_service, mock_settings_service
    ):
        from langflow.services.storage.s3 import STREAM_PART_SIZE

        client = _RecordingS3Client()
        service = _recording_service(mock_session_service, mock_settings_service, client)
        body = [b"x" * STREAM_PART_SIZE, b"tail"]

        written = await service.save_file_stream("ns", "big.pdf", _chunks(*body))

        assert written == STREAM_PART_SIZE + 4
        assert [call for call, _ in client.calls][-2:] == ["complete_multipart_upload", "copy_object"]
        copy = client.named("copy_object")[0]
        assert copy["Key"] == copy["CopySource"]["Key"] == "test-prefix/ns/big.pdf"
        assert copy["MetadataDirective"] == "REPLACE"
        assert copy["Metadata"] == {"md5": hashlib.md5(b"".join(body), usedforsecurity=False).hexdigest()}

    async def test_a_failed_label_copy_keeps_the_stored_file(self, mock_session_service, mock_settings_service):
        from langflow.services.storage.s3 import STREAM_PART_SIZE

        client = _RecordingS3Client(copy_error=RuntimeError("AccessDenied"))
        service = _recording_service(mock_session_service, mock_settings_service, client)

        written = await service.save_file_stream("ns", "big.pdf", _chunks(b"x" * STREAM_PART_SIZE))

        assert written == STREAM_PART_SIZE
        assert len(client.named("complete_multipart_upload")) == 1

    async def test_an_upload_link_signs_the_label_only_when_given(
        self, mock_session_service, mock_settings_service, monkeypatch
    ):
        monkeypatch.setenv("AWS_DEFAULT_REGION", "ca-central-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        service = S3StorageService(mock_session_service, mock_settings_service)

        labelled = await service.create_upload_link("ns", "a.pdf", md5=MD5)
        plain = await service.create_upload_link("ns", "a.pdf")

        # The uploader has to send x-amz-meta-md5 and Content-MD5 with these values, or S3
        # refuses the PUT; Content-MD5 is what makes S3 refuse a body that does not match.
        assert "content-md5%3Bhost%3Bx-amz-meta-md5" in labelled
        assert "x-amz-meta-md5" not in plain
        assert "content-md5" not in plain

    @pytest.mark.parametrize("bad", ["not-a-checksum", MD5.upper(), MD5[:-1]])
    async def test_an_upload_link_refuses_a_checksum_that_is_not_an_md5(
        self, mock_session_service, mock_settings_service, monkeypatch, bad
    ):
        monkeypatch.setenv("AWS_DEFAULT_REGION", "ca-central-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        service = S3StorageService(mock_session_service, mock_settings_service)

        with pytest.raises(ValueError, match="md5"):
            await service.create_upload_link("ns", "a.pdf", md5=bad)


class _NetworkError(Exception):
    """What botocore raises when the network fails: a ``response`` attribute that is None."""

    response = None


def _failing_client_service(mock_session_service, mock_settings_service, error):
    from contextlib import asynccontextmanager

    class Client:
        def __getattr__(self, name):
            async def fail(**_kwargs):
                raise error

            return fail

    service = S3StorageService(mock_session_service, mock_settings_service)

    @asynccontextmanager
    async def _client(**_kwargs):
        yield Client()

    service._get_client = _client
    return service


class TestNetworkErrorsKeepTheirType:
    """A network error has no S3 error code to read. It must surface, not crash the handler reading it."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda service: service.get_file("ns", "a.pdf"),
            lambda service: service.get_file_size("ns", "a.pdf"),
            lambda service: service.get_file_md5("ns", "a.pdf"),
            lambda service: service.move_file("source", "target", "a.pdf"),
        ],
        ids=["get_file", "get_file_size", "get_file_md5", "move_file"],
    )
    async def test_a_call_raises_the_network_error(self, mock_session_service, mock_settings_service, call):
        service = _failing_client_service(mock_session_service, mock_settings_service, _NetworkError("no route"))
        with pytest.raises(_NetworkError):
            await call(service)

    async def test_a_stream_raises_the_network_error(self, mock_session_service, mock_settings_service):
        service = _failing_client_service(mock_session_service, mock_settings_service, _NetworkError("no route"))
        with pytest.raises(_NetworkError):
            async for _ in service.get_file_stream("ns", "a.pdf"):
                pass

    async def test_a_missing_key_is_still_file_not_found(self, mock_session_service, mock_settings_service):
        class MissingKeyError(Exception):
            response = {"Error": {"Code": "NoSuchKey"}}

        service = _failing_client_service(mock_session_service, mock_settings_service, MissingKeyError("gone"))
        with pytest.raises(FileNotFoundError):
            await service.get_file_size("ns", "a.pdf")


class _SlowPartsClient(_RecordingS3Client):
    """Parts take a moment each, so overlapping ones show; ``fail_part`` makes that part fail."""

    def __init__(self, fail_part: int | None = None):
        super().__init__()
        self.in_flight = 0
        self.most_in_flight = 0
        self.cancelled = 0
        self._fail_part = fail_part

    async def upload_part(self, **kwargs):
        self.in_flight += 1
        self.most_in_flight = max(self.most_in_flight, self.in_flight)
        try:
            if kwargs["PartNumber"] == self._fail_part:  # at once, while the others are still going
                msg = "part failed"
                raise RuntimeError(msg)
            await asyncio.sleep(0.02)
            return await super().upload_part(**kwargs)
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        finally:
            self.in_flight -= 1

    async def abort_multipart_upload(self, **kwargs):
        self.calls.append(("abort_multipart_upload", kwargs))


class _ForgetfulSlowPartsClient(_RecordingS3Client):
    """Parts take a moment each and are not kept, so what the upload itself holds can be measured."""

    async def upload_part(self, **kwargs):
        await asyncio.sleep(0.005)
        return {"ETag": f'"{kwargs["PartNumber"]}"'}


class TestPartsInFlight:
    """Before: one part at a time, so a 900 MB upload to AWS took 24-45 s and the route gave 504."""

    async def test_parts_overlap_up_to_the_limit_and_complete_in_order(
        self, mock_session_service, mock_settings_service, monkeypatch
    ):
        from langflow.services.storage import s3

        monkeypatch.setattr(s3, "STREAM_PART_SIZE", 4)
        client = _SlowPartsClient()
        service = _recording_service(mock_session_service, mock_settings_service, client)
        body = b"abcd" * 10 + b"z"

        written = await service.save_file_stream("ns", "big.pdf", _chunks(body))

        assert written == len(body)
        assert client.most_in_flight == s3.STREAM_PARTS_IN_FLIGHT
        parts = client.named("complete_multipart_upload")[0]["MultipartUpload"]["Parts"]
        assert [part["PartNumber"] for part in parts] == list(range(1, 12))
        assert [part["ETag"] for part in parts] == [f'"{number}"' for number in range(1, 12)]
        sent = {call["PartNumber"]: call["Body"] for call in client.named("upload_part")}
        assert b"".join(sent[number] for number in sorted(sent)) == body

    async def test_a_known_md5_labels_the_upload_as_it_starts_and_skips_the_copy(
        self, mock_session_service, mock_settings_service, monkeypatch
    ):
        from langflow.services.storage import s3

        monkeypatch.setattr(s3, "STREAM_PART_SIZE", 4)
        client = _SlowPartsClient()
        service = _recording_service(mock_session_service, mock_settings_service, client)

        await service.save_file_stream("ns", "big.pdf", _chunks(b"abcdefghij"), md5=MD5)

        assert client.named("create_multipart_upload")[0]["Metadata"] == {"md5": MD5}
        assert client.named("copy_object") == []

    async def test_a_failed_part_cancels_the_rest_and_aborts(
        self, mock_session_service, mock_settings_service, monkeypatch
    ):
        from langflow.services.storage import s3

        monkeypatch.setattr(s3, "STREAM_PART_SIZE", 4)
        client = _SlowPartsClient(fail_part=2)
        service = _recording_service(mock_session_service, mock_settings_service, client)

        with pytest.raises(RuntimeError, match="part failed"):
            await service.save_file_stream("ns", "big.pdf", _chunks(b"abcd" * 10))

        assert client.cancelled > 0
        assert client.in_flight == 0
        assert len(client.named("abort_multipart_upload")) == 1
        assert client.named("complete_multipart_upload") == []

    async def test_a_part_waiting_for_a_slot_is_held_once(
        self, mock_session_service, mock_settings_service, monkeypatch
    ):
        """Before: the next part was cut before the wait, so the buffer and the cut copy both held it."""
        import tracemalloc

        from langflow.services.storage import s3

        part = 1024 * 1024
        monkeypatch.setattr(s3, "STREAM_PART_SIZE", part)
        service = _recording_service(mock_session_service, mock_settings_service, _ForgetfulSlowPartsClient())

        async def body():
            for _ in range(12 * 16):
                yield os.urandom(part // 16)

        tracemalloc.start()
        try:
            await service.save_file_stream("ns", "big.pdf", body())
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        # The parts in flight plus the one filling; a second copy of that one adds a whole part.
        assert peak < (s3.STREAM_PARTS_IN_FLIGHT + 1.5) * part, f"peak {peak / part:.2f} parts"

    async def test_the_parts_go_on_a_client_of_their_own(self, mock_session_service, mock_settings_service):
        """The shared client's 10 connections serve every other call; an upload must not take them."""
        from contextlib import asynccontextmanager

        service = S3StorageService(mock_session_service, mock_settings_service)
        asked: list[dict] = []

        @asynccontextmanager
        async def _client(**kwargs):
            asked.append(kwargs)
            yield _RecordingS3Client()

        service._get_client = _client

        await service.save_file_stream("ns", "a.pdf", _chunks(b"a"))

        assert asked == [{"shared": False}]

    async def test_a_known_md5_that_is_not_one_is_refused(self, mock_session_service, mock_settings_service):
        service = _recording_service(mock_session_service, mock_settings_service, _RecordingS3Client())
        with pytest.raises(ValueError, match="md5"):
            await service.save_file_stream("ns", "a.pdf", _chunks(b"a"), md5="nope")


class TestSaveUploadStream:
    async def test_it_streams_and_labels_the_file(self, mock_session_service, mock_settings_service):
        client = _RecordingS3Client()
        service = _recording_service(mock_session_service, mock_settings_service, client)

        written = await service.save_upload_stream("ns", "a.pdf", _chunks(b"ab", b"cd"))

        assert written == 4
        assert client.named("put_object")[0]["Body"] == b"abcd"

    async def test_a_missing_bucket_reads_as_save_file_reads_it(self, mock_session_service, mock_settings_service):
        class NoBucketError(Exception):
            response = {"Error": {"Code": "NoSuchBucket", "Message": "no bucket"}}

        service = _failing_client_service(mock_session_service, mock_settings_service, NoBucketError("no bucket"))
        with pytest.raises(FileNotFoundError, match="does not exist"):
            await service.save_upload_stream("ns", "a.pdf", _chunks(b"ab"))


class TestStreamFromAnOffset:
    """A resumed copy must not download again what it has already sent."""

    @staticmethod
    def _service(mock_session_service, mock_settings_service, asked):
        from contextlib import asynccontextmanager

        class Body:
            async def iter_chunks(self, _chunk_size):
                yield b"tail"

        class Client:
            async def get_object(self, **kwargs):
                asked.append(kwargs)
                return {"Body": Body()}

        service = S3StorageService(mock_session_service, mock_settings_service)

        @asynccontextmanager
        async def _client(**_kwargs):
            yield Client()

        service._get_client = _client
        return service

    async def test_it_asks_s3_only_for_the_rest(self, mock_session_service, mock_settings_service):
        asked = []
        service = self._service(mock_session_service, mock_settings_service, asked)
        assert [c async for c in service.get_file_stream("ns", "a.pdf", offset=44)] == [b"tail"]
        assert asked[0]["Range"] == "bytes=44-"

    async def test_without_an_offset_it_asks_for_the_whole_file(self, mock_session_service, mock_settings_service):
        asked = []
        service = self._service(mock_session_service, mock_settings_service, asked)
        assert [c async for c in service.get_file_stream("ns", "a.pdf")] == [b"tail"]
        assert "Range" not in asked[0]
