"""Both message-edit routes accept only attachments in authorized upload namespaces."""

from uuid import uuid4

import pytest
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope


@pytest.fixture(params=[False, True], ids=["owned-flow", "shared-flow"])
async def editable_attachment_message(request, active_user):
    """Persist an editable owned or virtual-flow message for the authenticated user."""
    source_flow_id = uuid4()
    shared = request.param
    flow_id = (
        compute_virtual_flow_id(active_user.id, source_flow_id, principal_type="user") if shared else source_flow_id
    )
    async with session_scope() as session:
        if not shared:
            session.add(Flow(id=flow_id, name="Attachment test flow", user_id=active_user.id, data={}))
            await session.flush()
        message = MessageTable(
            text="attachment test turn",
            sender="User",
            sender_name="User",
            session_id="attachment-test-session",
            flow_id=flow_id,
            user_id=active_user.id,
            category="message",
            files=[],
            properties={},
            content_blocks=[],
        )
        session.add(message)
        await session.flush()
        message_id = message.id

    suffix = f"shared/{message_id}?source_flow_id={source_flow_id}" if shared else str(message_id)
    return {
        "url": f"api/v1/monitor/messages/{suffix}",
        "id": message_id,
        "flow_id": flow_id,
        "source_flow_id": source_flow_id,
    }


@pytest.mark.parametrize(
    "file",
    [
        "/private/tmp/outside-canary.txt",
        "C:/outside-canary.txt",
        r"\\canary.invalid\share\upload.txt",
        "flow-id/../outside-canary.txt",
        "flow-id/nested/upload.txt",
    ],
)
async def test_message_edit_rejects_filesystem_paths(client, logged_in_headers, editable_attachment_message, file):
    """Reject malformed or unconfined paths without persisting an attachment reference."""
    response = await client.put(editable_attachment_message["url"], headers=logged_in_headers, json={"files": [file]})

    assert response.status_code == 400
    async with session_scope() as session:
        message = await session.get(MessageTable, editable_attachment_message["id"])
        assert message.files == []


async def test_message_edit_rejects_foreign_upload_namespace(client, logged_in_headers, editable_attachment_message):
    """Prevent message edits from selecting another user's upload namespace."""
    response = await client.put(
        editable_attachment_message["url"], headers=logged_in_headers, json={"files": [f"{uuid4()}/upload.txt"]}
    )

    assert response.status_code == 400
    async with session_scope() as session:
        message = await session.get(MessageTable, editable_attachment_message["id"])
        assert message.files == []


@pytest.mark.parametrize("namespace", ["user", "flow"])
async def test_message_edit_accepts_own_upload_keys(
    client, logged_in_headers, active_user, editable_attachment_message, namespace
):
    """Preserve upload keys belonging to the authenticated user or the message's flow."""
    scope = active_user.id if namespace == "user" else editable_attachment_message["flow_id"]
    files = [f"{scope}/upload.txt"]
    response = await client.put(editable_attachment_message["url"], headers=logged_in_headers, json={"files": files})

    assert response.status_code == 200
    assert response.json()["files"] == files


async def test_message_edit_can_remove_attachments(client, logged_in_headers, editable_attachment_message):
    """Allow an authorized edit to remove all attachments."""
    response = await client.put(editable_attachment_message["url"], headers=logged_in_headers, json={"files": []})

    assert response.status_code == 200
    assert response.json()["files"] == []


@pytest.mark.parametrize("namespace", ["user", "flow", "source-flow"])
@pytest.mark.parametrize("edit", ["text", "feedback"])
async def test_persisted_absolute_upload_round_trips_on_message_edit(
    client, logged_in_headers, active_user, editable_attachment_message, tmp_path, monkeypatch, namespace, edit
):
    """Keep authorized absolute upload paths when the frontend edits text or feedback."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "storage_type", "local")
    monkeypatch.setattr(settings, "restrict_local_file_access", True)
    monkeypatch.setattr(settings, "config_dir", str(tmp_path))
    scope = {
        "user": active_user.id,
        "flow": editable_attachment_message["flow_id"],
        "source-flow": editable_attachment_message["source_flow_id"],
    }[namespace]
    upload = tmp_path / str(scope) / "upload.txt"
    upload.parent.mkdir()
    upload.write_text("persisted upload canary")
    files = [str(upload)]
    # Component parameter processing resolves local keys to absolute paths before
    # MessageTable persists them. The frontend returns those paths on normal edits.
    async with session_scope() as session:
        message = await session.get(MessageTable, editable_attachment_message["id"])
        message.files = files
        session.add(message)

    payload = {"files": files}
    if edit == "text":
        payload["text"] = "edited turn"
    else:
        payload["properties"] = {"positive_feedback": True}
    response = await client.put(editable_attachment_message["url"], headers=logged_in_headers, json=payload)

    assert response.status_code == 200
    assert response.json()["files"] == files
    if edit == "text":
        assert response.json()["text"] == "edited turn"
    else:
        assert response.json()["properties"]["positive_feedback"] is True


@pytest.mark.parametrize("target", ["outside", "foreign", "reserved", "symlink"])
async def test_message_edit_rejects_unsafe_absolute_uploads(
    client, logged_in_headers, active_user, editable_attachment_message, tmp_path, monkeypatch, target
):
    """Reject outside, foreign, reserved, and symlink-escaped absolute attachments."""
    from langflow.services.deps import get_settings_service

    storage = tmp_path / "storage"
    storage.mkdir()
    owned = storage / str(active_user.id)
    owned.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside canary")
    foreign = storage / str(uuid4()) / "upload.txt"
    foreign.parent.mkdir()
    foreign.write_text("foreign canary")
    reserved = storage / "secret_key"
    reserved.write_text("reserved canary")
    link = owned / "alias.txt"
    link.symlink_to(outside)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "storage_type", "local")
    monkeypatch.setattr(settings, "restrict_local_file_access", True)
    monkeypatch.setattr(settings, "config_dir", str(storage))
    file = {"outside": outside, "foreign": foreign, "reserved": reserved, "symlink": link}[target]

    response = await client.put(
        editable_attachment_message["url"], headers=logged_in_headers, json={"files": [str(file)]}
    )

    assert response.status_code == 400
