"""Attachment path rewrites use the stored files as their authority, without S3 access."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.utils import file_relocation
from langflow.services.database.models.message.model import MessageTable


@pytest.fixture
async def attachment_session(async_session, monkeypatch):
    @asynccontextmanager
    async def scope():
        yield async_session

    monkeypatch.setattr(file_relocation, "session_scope", scope)
    return async_session


@pytest.mark.parametrize("path_style", ["local", "old_posix", "windows", "windows_forward", "unc"])
@pytest.mark.parametrize("dry_run", [False, True])
async def test_absolute_attachments_resolve_to_stored_files(attachment_session, tmp_path, path_style, dry_run):
    flow_id = uuid4()
    name = "notes.txt"
    root = tmp_path / "storage"
    entries = {
        "local": str(root / str(flow_id) / name),
        "old_posix": f"/old/config/{flow_id}/{name}",
        "windows": rf"C:\old\config\{flow_id}\{name}",
        "windows_forward": f"C:/old/config/{flow_id}/{name}",
        "unc": rf"\\server\share\{flow_id}\{name}",
    }
    entry = entries[path_style]
    message = MessageTable(sender="User", sender_name="User", session_id=str(flow_id), flow_id=flow_id, files=[entry])
    attachment_session.add(message)
    await attachment_session.commit()

    results = await file_relocation._repoint_message_attachments(
        SimpleNamespace(data_dir=root), {(str(flow_id), name)}, [str(flow_id)], dry_run=dry_run
    )

    await attachment_session.refresh(message)
    assert message.files == [entry if dry_run else f"{flow_id}/{name}"]
    assert [result.status for result in results] == ["would_repoint" if dry_run else "repointed"]


@pytest.mark.parametrize("dry_run", [False, True])
async def test_missing_local_attachment_is_reported_and_preserved(attachment_session, tmp_path, dry_run):
    flow_id = uuid4()
    root = tmp_path / "storage"
    entry = str(root / str(flow_id) / "gone.txt")
    message = MessageTable(sender="User", sender_name="User", session_id=str(flow_id), flow_id=flow_id, files=[entry])
    attachment_session.add(message)
    await attachment_session.commit()

    results = await file_relocation._repoint_message_attachments(
        SimpleNamespace(data_dir=root), set(), [str(flow_id)], dry_run=dry_run
    )

    await attachment_session.refresh(message)
    assert message.files == [entry]
    assert [result.status for result in results] == ["failed"]
    assert str(message.id) in results[0].reason
    assert results[0].code == "attachment_unmatched"
