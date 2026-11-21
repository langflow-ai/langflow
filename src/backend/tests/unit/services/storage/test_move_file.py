"""``move_file`` is the promote step of a deploy's document copy.

Files are staged under the copy job's own namespace and moved onto the keys flows read
only once the whole set has landed, so the cases that matter here are: the bytes survive
the move, nothing is left at the source, and a move that already happened is not an error
— that last one is what lets an interrupted promote be re-run.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from langflow.services.storage.local import LocalStorageService
from langflow.services.storage.s3 import S3StorageService
from langflow.services.storage.service import StorageService


def _settings(tmp_path: Path) -> Mock:
    settings_service = Mock()
    settings_service.settings.config_dir = str(tmp_path)
    settings_service.settings.object_storage_bucket_name = "bucket"
    settings_service.settings.object_storage_prefix = "files"
    settings_service.settings.object_storage_tags = {}
    return settings_service


@pytest.mark.asyncio
class TestLocalMoveFile:
    async def test_should_land_bytes_and_clear_source_when_file_exists(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))
        staging, final = str(uuid4()), str(uuid4())
        (tmp_path / staging).mkdir()
        (tmp_path / staging / "report.pdf").write_bytes(b"new version")

        await service.move_file(staging, final, "report.pdf")

        assert (tmp_path / final / "report.pdf").read_bytes() == b"new version"
        assert not (tmp_path / staging / "report.pdf").exists()

    async def test_should_replace_target_when_an_older_file_is_there(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))
        staging, final = str(uuid4()), str(uuid4())
        (tmp_path / staging).mkdir()
        (tmp_path / final).mkdir()
        (tmp_path / staging / "report.pdf").write_bytes(b"new version")
        (tmp_path / final / "report.pdf").write_bytes(b"old version")

        await service.move_file(staging, final, "report.pdf")

        assert (tmp_path / final / "report.pdf").read_bytes() == b"new version"

    async def test_should_create_target_namespace_when_it_does_not_exist(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))
        staging, final = str(uuid4()), str(uuid4())
        (tmp_path / staging).mkdir()
        (tmp_path / staging / "report.pdf").write_bytes(b"x")

        await service.move_file(staging, final, "report.pdf")

        assert (tmp_path / final / "report.pdf").exists()

    async def test_should_be_idempotent_when_called_twice(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))
        staging, final = str(uuid4()), str(uuid4())
        (tmp_path / staging).mkdir()
        (tmp_path / staging / "report.pdf").write_bytes(b"new version")

        await service.move_file(staging, final, "report.pdf")
        await service.move_file(staging, final, "report.pdf")

        assert (tmp_path / final / "report.pdf").read_bytes() == b"new version"

    async def test_should_raise_when_neither_side_holds_the_file(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))

        with pytest.raises(FileNotFoundError):
            await service.move_file(str(uuid4()), str(uuid4()), "report.pdf")

    @pytest.mark.parametrize("namespace", ["../etc", "a/b", "", "C:\\Windows"])
    async def test_should_refuse_traversal_when_a_namespace_is_malformed(self, tmp_path, namespace):
        service = LocalStorageService(Mock(), _settings(tmp_path))

        with pytest.raises(ValueError, match="Invalid"):
            await service.move_file(namespace, str(uuid4()), "report.pdf")
        with pytest.raises(ValueError, match="Invalid"):
            await service.move_file(str(uuid4()), namespace, "report.pdf")


class _MissingKeyError(Exception):
    """What botocore raises for a copy whose source is not there."""

    response = {"Error": {"Code": "NoSuchKey"}}


class _DeniedError(Exception):
    """Anything that is not a missing source, which must not be swallowed."""

    response = {"Error": {"Code": "AccessDenied"}}


class _FakeS3Client:
    def __init__(self, objects: set[str], copy_error: Exception | None = None):
        self.objects = objects
        self._copy_error = copy_error
        self.copies: list[tuple[str, str]] = []
        self.copy_kwargs: dict = {}
        self.deleted: list[str] = []
        self.heads: list[str] = []

    async def copy_object(self, **kwargs):
        if self._copy_error is not None:
            raise self._copy_error
        self.copy_kwargs = kwargs
        source = kwargs["CopySource"]["Key"]
        if source not in self.objects:
            raise _MissingKeyError
        self.copies.append((source, kwargs["Key"]))
        self.objects.add(kwargs["Key"])

    async def delete_object(self, **kwargs):
        self.deleted.append(kwargs["Key"])
        self.objects.discard(kwargs["Key"])

    async def head_object(self, **kwargs):
        self.heads.append(kwargs["Key"])
        if kwargs["Key"] not in self.objects:
            raise _MissingKeyError
        return {"ContentLength": 1}


def _s3_service(tmp_path, client):
    service = S3StorageService(Mock(), _settings(tmp_path))

    @asynccontextmanager
    async def _client():
        yield client

    service._get_client = _client
    return service


@pytest.mark.asyncio
class TestS3MoveFile:
    async def test_should_copy_server_side_then_delete_source(self, tmp_path):
        staging, final = str(uuid4()), str(uuid4())
        client = _FakeS3Client({f"files/{staging}/report.pdf"})
        service = _s3_service(tmp_path, client)

        await service.move_file(staging, final, "report.pdf")

        assert client.copies == [(f"files/{staging}/report.pdf", f"files/{final}/report.pdf")]
        assert client.deleted == [f"files/{staging}/report.pdf"]

    async def test_should_be_idempotent_when_source_is_gone_and_target_is_there(self, tmp_path):
        staging, final = str(uuid4()), str(uuid4())
        client = _FakeS3Client({f"files/{final}/report.pdf"})
        service = _s3_service(tmp_path, client)

        await service.move_file(staging, final, "report.pdf")

        assert client.copies == []
        assert client.deleted == []
        assert client.heads == [f"files/{final}/report.pdf"]

    async def test_should_raise_not_found_when_neither_side_holds_the_object(self, tmp_path):
        client = _FakeS3Client(set())
        service = _s3_service(tmp_path, client)

        with pytest.raises(FileNotFoundError):
            await service.move_file(str(uuid4()), str(uuid4()), "report.pdf")

    async def test_should_not_swallow_an_error_that_is_not_a_missing_source(self, tmp_path):
        staging, final = str(uuid4()), str(uuid4())
        client = _FakeS3Client({f"files/{staging}/report.pdf"}, copy_error=_DeniedError())
        service = _s3_service(tmp_path, client)

        with pytest.raises(_DeniedError):
            await service.move_file(staging, final, "report.pdf")
        assert client.deleted == []

    @pytest.mark.parametrize("namespace", ["../etc", "a/b", "", "C:\\Windows"])
    async def test_should_refuse_before_calling_s3_when_a_namespace_is_malformed(self, tmp_path, namespace):
        client = _FakeS3Client(set())
        service = _s3_service(tmp_path, client)

        with pytest.raises(ValueError, match="Invalid"):
            await service.move_file(namespace, str(uuid4()), "report.pdf")
        with pytest.raises(ValueError, match="Invalid"):
            await service.move_file(str(uuid4()), namespace, "report.pdf")
        assert client.copies == []


@pytest.mark.asyncio
class TestMoveFileTags:
    """A promoted object carries the configured tags even though the staged one had none."""

    async def test_should_write_configured_tags_when_promoting(self, tmp_path):
        staging, final = str(uuid4()), str(uuid4())
        settings = _settings(tmp_path)
        settings.settings.object_storage_tags = {"owner": "langflow", "tier": "cold"}
        service = S3StorageService(Mock(), settings)
        client = _FakeS3Client({f"files/{staging}/report.pdf"})

        @asynccontextmanager
        async def _client():
            yield client

        service._get_client = _client

        await service.move_file(staging, final, "report.pdf")

        assert client.copy_kwargs["Tagging"] == "owner=langflow&tier=cold"
        assert client.copy_kwargs["TaggingDirective"] == "REPLACE"

    async def test_should_send_no_tagging_when_none_configured(self, tmp_path):
        staging, final = str(uuid4()), str(uuid4())
        client = _FakeS3Client({f"files/{staging}/report.pdf"})
        service = _s3_service(tmp_path, client)

        await service.move_file(staging, final, "report.pdf")

        assert "Tagging" not in client.copy_kwargs
        assert "TaggingDirective" not in client.copy_kwargs


@pytest.mark.asyncio
class TestCreateUploadLink:
    async def test_should_return_none_for_local_storage(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))

        assert await service.create_upload_link(str(uuid4()), "report.pdf") is None

    async def test_should_sign_with_sigv4_and_carry_the_expiry(self, tmp_path, monkeypatch):
        # us-east-1 is the case that matters: its default signing is v2, which newer
        # regions refuse, so the pinned s3v4 has to win over the region's default.
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        namespace = str(uuid4())
        service = S3StorageService(Mock(), _settings(tmp_path))

        url = await service.create_upload_link(namespace, "report.pdf", expires_in=120)

        assert "X-Amz-Signature=" in url
        assert "AWSAccessKeyId=" not in url
        assert "X-Amz-Expires=120" in url
        assert f"files/{namespace}/report.pdf" in url

    async def test_should_scope_the_link_to_one_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWS_DEFAULT_REGION", "ca-central-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        first, second = str(uuid4()), str(uuid4())
        service = S3StorageService(Mock(), _settings(tmp_path))

        one = await service.create_upload_link(first, "a.pdf")
        two = await service.create_upload_link(second, "a.pdf")

        assert f"files/{first}/a.pdf" in one
        assert f"files/{second}/a.pdf" not in one
        assert one.split("?")[0] != two.split("?")[0]

    async def test_should_sign_for_the_regional_host_when_on_aws(self, tmp_path, monkeypatch):
        # The global host answers a new bucket outside us-east-1 with a 307 to the regional
        # one, and a redirected PUT never lands -- found on a real ca-central-1 bucket.
        monkeypatch.setenv("AWS_DEFAULT_REGION", "ca-central-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)
        monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
        service = S3StorageService(Mock(), _settings(tmp_path))

        url = await service.create_upload_link(str(uuid4()), "report.pdf")

        assert url.startswith("https://bucket.s3.ca-central-1.amazonaws.com/files/")

    async def test_should_keep_the_custom_endpoint_host_when_one_is_set(self, tmp_path, monkeypatch):
        # A virtual host would put the bucket into MinIO's hostname, which does not resolve.
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
        monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "http://minio:9000")
        service = S3StorageService(Mock(), _settings(tmp_path))

        url = await service.create_upload_link(str(uuid4()), "report.pdf")

        assert url.startswith("http://minio:9000/bucket/files/")

    @pytest.mark.parametrize("namespace", ["../etc", "a/b", "", "C:\\Windows"])
    async def test_should_refuse_before_signing_when_namespace_is_malformed(self, tmp_path, namespace):
        service = S3StorageService(Mock(), _settings(tmp_path))

        with pytest.raises(ValueError, match="Invalid"):
            await service.create_upload_link(namespace, "report.pdf")


@pytest.mark.asyncio
class TestRefusesABadMove:
    @pytest.mark.parametrize("name", ["", ".", ".."])
    async def test_should_not_move_a_whole_namespace_when_the_name_is_not_a_file(self, tmp_path, name):
        # An empty name resolves to the staging directory itself on local disk, and a rename
        # would then promote every staged file at once, unverified.
        service = LocalStorageService(Mock(), _settings(tmp_path))
        staging, final = str(uuid4()), str(uuid4())
        (tmp_path / staging).mkdir()
        (tmp_path / staging / "a.pdf").write_bytes(b"staged")

        with pytest.raises(ValueError, match="file name"):
            await service.move_file(staging, final, name)

        assert (tmp_path / staging / "a.pdf").read_bytes() == b"staged"
        assert not (tmp_path / final).exists()

    async def test_should_not_delete_the_only_copy_when_moving_onto_itself(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))
        namespace = str(uuid4())
        (tmp_path / namespace).mkdir()
        (tmp_path / namespace / "a.pdf").write_bytes(b"only copy")

        # The read-write-delete default every outside backend inherits.
        with pytest.raises(ValueError, match="same namespace"):
            await StorageService.move_file(service, namespace, namespace, "a.pdf")

        assert (tmp_path / namespace / "a.pdf").read_bytes() == b"only copy"

    async def test_should_refuse_before_calling_s3(self, tmp_path):
        client = _FakeS3Client({f"files/{uuid4()}/a.pdf"})

        with pytest.raises(ValueError, match="file name"):
            await _s3_service(tmp_path, client).move_file(str(uuid4()), str(uuid4()), "")

        assert client.copies == []
