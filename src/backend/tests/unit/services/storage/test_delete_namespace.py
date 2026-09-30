from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from langflow.services.storage.local import LocalStorageService
from langflow.services.storage.s3 import S3StorageService
from langflow.services.storage.service import validate_namespace

INVALID_NAMESPACES = ["../etc", "/etc", "not-a-uuid", "", "..", "a/b", "C:\\Windows"]


def _settings(tmp_path: Path) -> Mock:
    settings_service = Mock()
    settings_service.settings.config_dir = str(tmp_path)
    settings_service.settings.object_storage_bucket_name = "bucket"
    settings_service.settings.object_storage_prefix = "files"
    settings_service.settings.object_storage_tags = {}
    return settings_service


@pytest.mark.parametrize("namespace", INVALID_NAMESPACES)
def test_should_reject_namespace_when_not_a_uuid(namespace):
    with pytest.raises(ValueError, match="UUID"):
        validate_namespace(namespace)


def test_should_canonicalize_namespace_when_uuid_has_uppercase():
    value = uuid4()

    assert validate_namespace(str(value).upper()) == str(value)


@pytest.mark.asyncio
class TestLocalDeleteNamespace:
    async def test_should_remove_nested_files_when_namespace_exists(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))
        namespace = str(uuid4())
        (tmp_path / namespace / "nested").mkdir(parents=True)
        (tmp_path / namespace / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / namespace / "nested" / "b.txt").write_text("b", encoding="utf-8")
        sibling = tmp_path / str(uuid4())
        sibling.mkdir()
        (sibling / "keep.txt").write_text("keep", encoding="utf-8")

        removed = await service.delete_namespace(namespace)

        assert removed == 2
        assert not (tmp_path / namespace).exists()
        assert (sibling / "keep.txt").exists()

    async def test_should_return_zero_when_namespace_missing(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))

        assert await service.delete_namespace(str(uuid4())) == 0

    async def test_should_be_idempotent_when_called_twice(self, tmp_path):
        service = LocalStorageService(Mock(), _settings(tmp_path))
        namespace = str(uuid4())
        (tmp_path / namespace).mkdir()
        (tmp_path / namespace / "a.txt").write_text("a", encoding="utf-8")

        first = await service.delete_namespace(namespace)
        second = await service.delete_namespace(namespace)

        assert (first, second) == (1, 0)

    @pytest.mark.parametrize("namespace", INVALID_NAMESPACES)
    async def test_should_refuse_traversal_when_namespace_invalid(self, tmp_path, namespace):
        service = LocalStorageService(Mock(), _settings(tmp_path))

        with pytest.raises(ValueError, match="UUID"):
            await service.delete_namespace(namespace)


class _FakePaginator:
    def __init__(self, pages):
        self._pages = pages
        self.prefixes: list[str] = []

    def paginate(self, **kwargs):
        self.prefixes.append(kwargs["Prefix"])
        pages = self._pages

        async def _iterate():
            for page in pages:
                yield page

        return _iterate()


class _FakeS3Client:
    def __init__(self, pages, errors=None):
        self.paginator = _FakePaginator(pages)
        self.deleted: list[str] = []
        self._errors = errors or []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self.paginator

    async def delete_objects(self, **kwargs):
        self.deleted.extend(obj["Key"] for obj in kwargs["Delete"]["Objects"])
        return {"Errors": self._errors} if self._errors else {}


def _s3_service(tmp_path, client):
    service = S3StorageService(Mock(), _settings(tmp_path))

    @asynccontextmanager
    async def _client():
        yield client

    service._get_client = _client
    return service


@pytest.mark.asyncio
class TestS3DeleteNamespace:
    async def test_should_delete_every_page_when_keys_are_nested(self, tmp_path):
        namespace = str(uuid4())
        pages = [
            {"Contents": [{"Key": f"files/{namespace}/a.txt"}, {"Key": f"files/{namespace}/dir/b.txt"}]},
            {"Contents": [{"Key": f"files/{namespace}/c.txt"}]},
            {},
        ]
        client = _FakeS3Client(pages)
        service = _s3_service(tmp_path, client)

        removed = await service.delete_namespace(namespace)

        assert removed == 3
        assert client.paginator.prefixes == [f"files/{namespace}/"]
        assert f"files/{namespace}/dir/b.txt" in client.deleted

    async def test_should_raise_when_s3_reports_errors(self, tmp_path):
        namespace = str(uuid4())
        client = _FakeS3Client([{"Contents": [{"Key": f"files/{namespace}/a.txt"}]}], errors=[{"Key": "x"}])
        service = _s3_service(tmp_path, client)

        with pytest.raises(RuntimeError, match="refused"):
            await service.delete_namespace(namespace)

    @pytest.mark.parametrize("namespace", INVALID_NAMESPACES)
    async def test_should_refuse_before_calling_s3_when_namespace_invalid(self, tmp_path, namespace):
        client = _FakeS3Client([])
        service = _s3_service(tmp_path, client)

        with pytest.raises(ValueError, match="UUID"):
            await service.delete_namespace(namespace)
        assert client.paginator.prefixes == []
