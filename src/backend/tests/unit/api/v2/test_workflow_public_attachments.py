"""A shareable-playground message can carry a file the visitor attached.

The playground uploads through ``/api/v1/files/upload/{flow_id}``, which stores
the file in the flow's typed namespace (``flow-<flow_id>/<name>``), and then
sends that path to the public run. The path gate must accept it while still
refusing anything outside the flow's own namespace.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient, codes
from langflow.api.utils.flow_utils import validate_public_files
from langflow.services.database.models.message.model import MessageTable
from lfx.services.deps import get_storage_service, session_scope
from lfx.utils.file_path_security import flow_storage_scope
from sqlmodel import select

FLOW_ID = UUID("d3a93ec1-c6a7-4c68-84d5-52b3453c280e")


@pytest.mark.parametrize(
    "path",
    [
        f"flow-{FLOW_ID}/2026-11-10_11-18-51_meeting-notes-final-v2.txt",
        f"{FLOW_ID}/2026-11-10_11-18-51_meeting-notes-final-v2.txt",
    ],
)
def test_a_path_in_the_flows_own_namespace_is_accepted(path) -> None:
    validate_public_files([path], FLOW_ID)


@pytest.mark.parametrize(
    "path",
    [
        f"flow-{uuid4()}/notes.txt",
        f"flow-{FLOW_ID}/../notes.txt",
        f"flow-{FLOW_ID}/nested/notes.txt",
        f"flow-flow-{FLOW_ID}/notes.txt",
        f"user-{FLOW_ID}/notes.txt",
        f"/flow-{FLOW_ID}/notes.txt",
        # Uploads use the lower-case id; another casing would pass the gate and then fail the build silently.
        f"flow-{str(FLOW_ID).upper()}/notes.txt",
    ],
)
def test_a_path_outside_the_flows_namespace_is_still_refused(path) -> None:
    with pytest.raises(HTTPException) as refused:
        validate_public_files([path], FLOW_ID)
    assert refused.value.status_code == codes.BAD_REQUEST


async def test_a_visitor_sends_a_message_with_a_file_uploaded_for_the_flow(
    client: AsyncClient, json_memory_chatbot_no_llm, logged_in_headers
):
    from tests.unit.build_utils import create_flow

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    response = await client.patch(f"api/v1/flows/{flow_id}", json={"access_type": "PUBLIC"}, headers=logged_in_headers)
    assert response.status_code == codes.OK
    # Stored where ``/api/v1/files/upload/{flow_id}`` puts a playground attachment.
    namespace, file_name = flow_storage_scope(flow_id), "2026-11-10_11-18-51_meeting-notes-final-v2.txt"
    await get_storage_service().save_file(flow_id=namespace, file_name=file_name, data=b"meeting notes")
    file_path = f"{namespace}/{file_name}"

    client.cookies.clear()
    client.cookies.set("client_id", "attachment-visitor")
    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={"flow_id": str(flow_id), "input_value": "see attached", "files": [file_path]},
        headers={"Content-Type": "application/json"},
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])
    assert response.status_code == codes.OK, body

    async with session_scope() as session:
        messages = (await session.exec(select(MessageTable).where(MessageTable.text == "see attached"))).all()
    stored = [str(path).replace("\\", "/") for message in messages for path in message.files or []]
    assert any(path.endswith(file_path) for path in stored), stored
