"""Storage fixtures shared by the v1 and v2 file upload tests."""

import pytest
from langflow.services.storage.local import LocalStorageService


@pytest.fixture(name="save_file_spy")
def save_file_spy_fixture(monkeypatch):
    """Record every file name handed to the storage layer.

    Rejecting an upload must happen before anything is written, so the upload tests
    assert on this list rather than on the status code alone.
    """
    saved_file_names: list[str] = []
    original_save_file = LocalStorageService.save_file

    async def recording_save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        saved_file_names.append(file_name)
        await original_save_file(self, flow_id, file_name, data, append=append)

    monkeypatch.setattr(LocalStorageService, "save_file", recording_save_file)
    return saved_file_names
