import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import anyio
import pytest
from fastapi import UploadFile
from langflow.api.v2.files import UPLOAD_READ_CHUNK, save_file_routine
from langflow.services.storage.local import LocalStorageService


@pytest.fixture
def storage(tmp_path):
    settings = MagicMock()
    settings.settings.config_dir = str(tmp_path)
    return LocalStorageService(MagicMock(), settings)


@pytest.mark.parametrize(
    "data", [b"", b"new content", b"x" * (UPLOAD_READ_CHUNK + 7)], ids=["empty", "small", "chunked"]
)
async def test_upload_can_replace_its_source_file_on_windows(storage, tmp_path, monkeypatch, data):
    destination = tmp_path / "ns" / "report.json"
    destination.parent.mkdir()
    destination.write_bytes(data)
    replace = anyio.Path.replace

    with destination.open("rb") as source:
        upload = UploadFile(file=source, filename=destination.name, size=len(data))

        async def windows_replace(partial, target):
            # Windows refuses to replace an open destination, even when it is the upload source.
            if str(target) == str(destination) and not source.closed:
                msg = "The destination is still open"
                raise PermissionError(msg)
            return await replace(partial, target)

        monkeypatch.setattr(anyio.Path, "replace", windows_replace)
        await save_file_routine(upload, storage, SimpleNamespace(id="u1"), namespace="ns")

        assert source.closed

    assert destination.read_bytes() == data
    assert list((tmp_path / ".uploads").iterdir()) == []


@pytest.mark.parametrize("consume_source", [False, True])
@pytest.mark.parametrize("error", [OSError, asyncio.CancelledError])
async def test_upload_closes_source_when_storage_fails(tmp_path, consume_source, error):
    source_path = tmp_path / "source.bin"
    source_path.write_bytes(b"source content")

    async def fail_upload(_namespace, _name, chunks):
        if consume_source:
            await anext(chunks)
        raise error

    with source_path.open("rb") as source:
        upload = UploadFile(file=source, filename=source_path.name)
        with pytest.raises(error):
            await save_file_routine(
                upload, SimpleNamespace(save_upload_stream=fail_upload), SimpleNamespace(id="u1"), namespace="ns"
            )
        assert source.closed


async def test_failed_source_read_keeps_existing_destination(storage, tmp_path, monkeypatch):
    await storage.save_file("ns", "report.json", b"old content")
    source_path = tmp_path / "source.bin"
    source_path.write_bytes(b"new content")

    with source_path.open("rb") as source:
        upload = UploadFile(file=source, filename="report.json")
        read = upload.read

        async def failing_read(size):
            if source.tell():
                msg = "Source read failed"
                raise OSError(msg)
            return await read(size)

        monkeypatch.setattr(upload, "read", failing_read)
        with pytest.raises(OSError, match="Source read failed"):
            await save_file_routine(upload, storage, SimpleNamespace(id="u1"), namespace="ns")
        assert source.closed

    assert await storage.get_file("ns", "report.json") == b"old content"
    assert list((tmp_path / ".uploads").iterdir()) == []


@pytest.mark.parametrize("consume_source", [False, True])
async def test_upload_closes_source_inside_cancelled_scope(tmp_path, consume_source):
    source_path = tmp_path / "source.bin"
    source_path.write_bytes(b"source content")

    with source_path.open("rb") as source:
        upload = UploadFile(file=source, filename=source_path.name)
        with anyio.CancelScope() as scope:

            async def cancel_upload(_namespace, _name, chunks):
                if consume_source:
                    await anext(chunks)
                scope.cancel()
                await anyio.lowlevel.checkpoint()

            await save_file_routine(
                upload, SimpleNamespace(save_upload_stream=cancel_upload), SimpleNamespace(id="u1"), namespace="ns"
            )
        assert source.closed
