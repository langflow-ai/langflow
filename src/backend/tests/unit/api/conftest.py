"""Storage fixtures shared by the v1 and v2 file upload tests."""

from collections.abc import AsyncIterator

import pytest
from langflow.services.deps import get_storage_service


@pytest.fixture(name="save_file_spy")
def save_file_spy_fixture(monkeypatch, files_client):  # noqa: ARG001
    """Record every file name handed to the storage layer, through ``save_file`` or ``save_upload_stream``.

    Rejecting an upload must happen before anything is written, so the upload tests
    assert on this list rather than on the status code alone. Plain uploads stream through
    ``save_upload_stream``; ``save_file`` still takes appends and content read up front.
    """
    # langflow and lfx each ship an unrelated LocalStorageService and either can be live,
    # so spy on the instance the started app hands to its routes, not on a named class.
    storage_service = get_storage_service()
    saved_file_names: list[str] = []
    original_save_file = storage_service.save_file

    async def recording_save_file(flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        saved_file_names.append(file_name)
        await original_save_file(flow_id, file_name, data, append=append)

    monkeypatch.setattr(storage_service, "save_file", recording_save_file)

    original_save_upload_stream = storage_service.save_upload_stream

    # **kwargs forwards S3's optional md5 without passing it to services that don't take one.
    async def recording_save_upload_stream(flow_id: str, file_name: str, chunks: AsyncIterator[bytes], **kwargs) -> int:
        saved_file_names.append(file_name)
        return await original_save_upload_stream(flow_id, file_name, chunks, **kwargs)

    monkeypatch.setattr(storage_service, "save_upload_stream", recording_save_upload_stream)
    return saved_file_names
