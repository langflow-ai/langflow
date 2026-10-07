"""Export what Langflow holds about one data subject as a ZIP (Art. 15 access, Art. 20 portability).

The archive is written to a spooled temporary file batch by batch, so a large history is never held in
memory. A builder export never includes the messages of their flows: those belong to other people.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from sqlmodel import col, select

from langflow.services.data_subjects.batching import BATCH_SIZE
from langflow.services.data_subjects.transactions import end_user_transactions
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth.sso import SSOUserProfile
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_storage_service
from langflow.utils.flow_secrets import strip_flow_secrets

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.identity import EndUserKeys
    from langflow.services.database.models.user.model import User

SPOOL_MAX_BYTES = 10 * 1024 * 1024
LIKE_ESCAPE = "\\"


def _json(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, indent=2)


def _safe_member(name: str) -> str:
    return PurePosixPath(name.replace("\\", "/")).name or "file"


class _Archive:
    def __init__(self) -> None:
        self.file = tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_BYTES)  # noqa: SIM115 - handed to the response
        self._zip = zipfile.ZipFile(self.file, mode="w", compression=zipfile.ZIP_DEFLATED)
        self.sections: dict[str, int] = {}

    def write_json(self, member: str, value: Any, *, count: int | None = None) -> None:
        self._zip.writestr(member, _json(value))
        self.sections[member] = count if count is not None else 1

    def write_bytes(self, member: str, data: bytes) -> None:
        self._zip.writestr(member, data)
        self.sections[member] = 1

    def close(self, manifest: dict[str, Any]) -> tempfile.SpooledTemporaryFile:
        manifest["contents"] = self.sections
        self._zip.writestr("manifest.json", _json(manifest))
        self._zip.close()
        self.file.seek(0)
        return self.file


def _manifest(subject_type: str, actor_id: UUID | None) -> dict[str, Any]:
    return {
        "format": "langflow-data-subject-export/1",
        "subject_type": subject_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": str(actor_id) if actor_id else None,
    }


async def _rows(session: AsyncSession, stmt, order_column) -> list:
    rows, offset = [], 0
    while True:
        batch = (await session.exec(stmt.order_by(order_column).offset(offset).limit(BATCH_SIZE))).all()
        rows.extend(batch)
        if len(batch) < BATCH_SIZE:
            return rows
        offset += BATCH_SIZE


async def _builder_files(session: AsyncSession, archive: _Archive, user: User) -> None:
    files = await _rows(session, select(File).where(File.user_id == user.id), col(File.id))
    archive.write_json(
        "files.json",
        [{"name": f.name, "size": f.size, "created_at": f.created_at} for f in files],
        count=len(files),
    )
    storage = get_storage_service()
    for stored in files:
        try:
            data = await storage.get_file(str(user.id), PurePosixPath(stored.path).name)
        except FileNotFoundError:
            continue
        archive.write_bytes(f"files/{stored.id}_{_safe_member(stored.name)}", data)


async def export_builder(session: AsyncSession, user: User, actor_id: UUID | None) -> tempfile.SpooledTemporaryFile:
    archive = _Archive()
    profiles = (await session.exec(select(SSOUserProfile).where(SSOUserProfile.user_id == user.id))).all()
    archive.write_json(
        "account.json",
        {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "created_at": user.create_at,
            "updated_at": user.updated_at,
            "last_login_at": user.last_login_at,
            "sso_profiles": [
                {"provider": p.sso_provider, "email": p.email, "first_name": p.first_name, "last_name": p.last_name}
                for p in profiles
            ],
        },
    )
    folders = await _rows(session, select(Folder).where(Folder.user_id == user.id), col(Folder.id))
    archive.write_json(
        "projects.json",
        [{"id": f.id, "name": f.name, "description": f.description} for f in folders],
        count=len(folders),
    )
    variables = await _rows(session, select(Variable).where(Variable.user_id == user.id), col(Variable.id))
    names = {v.name for v in variables}
    archive.write_json("variables.json", [{"name": v.name, "type": v.type} for v in variables], count=len(variables))
    keys = await _rows(session, select(ApiKey).where(ApiKey.user_id == user.id), col(ApiKey.id))
    archive.write_json(
        "api_keys.json",
        [{"name": k.name, "created_at": k.created_at, "last_used_at": k.last_used_at} for k in keys],
        count=len(keys),
    )
    flows = await _rows(session, select(Flow).where(Flow.user_id == user.id), col(Flow.id))
    for flow in flows:
        envelope = {"id": flow.id, "name": flow.name, "description": flow.description, "data": flow.data}
        archive.write_json(f"flows/{flow.id}.json", strip_flow_secrets(envelope, known_variable_names=names))
    await _builder_files(session, archive, user)
    return archive.close(_manifest("builder", actor_id))


async def export_end_user(
    session: AsyncSession, keys: EndUserKeys, scope: tuple[UUID, ...], actor_id: UUID | None
) -> tempfile.SpooledTemporaryFile:
    archive = _Archive()
    message_stmt = select(MessageTable).where(
        MessageTable.user_id == keys.message_owner_id,
        col(MessageTable.session_id).like(keys.session_like_pattern, escape=LIKE_ESCAPE),
    )
    trace_stmt = select(TraceTable).where(
        col(TraceTable.session_id).like(keys.session_like_pattern, escape=LIKE_ESCAPE)
    )
    if scope:
        message_stmt = message_stmt.where(col(MessageTable.flow_id).in_(scope))
        trace_stmt = trace_stmt.where(col(TraceTable.flow_id).in_(scope))
    messages = await _rows(session, message_stmt, col(MessageTable.timestamp))
    archive.write_json(
        "messages.json",
        [
            {
                "timestamp": m.timestamp,
                "sender": m.sender,
                "text": m.text,
                "session_id": m.session_id,
                "flow_id": m.flow_id,
                "files": m.files,
            }
            for m in messages
        ],
        count=len(messages),
    )
    traces = await _rows(session, trace_stmt, col(TraceTable.start_time))
    archive.write_json(
        "traces.json",
        [{"name": t.name, "status": t.status, "start_time": t.start_time, "session_id": t.session_id} for t in traces],
        count=len(traces),
    )
    transactions = await _rows(
        session, select(TransactionTable).where(end_user_transactions(keys, scope)), col(TransactionTable.timestamp)
    )
    archive.write_json(
        "transactions.json",
        [
            {
                "timestamp": t.timestamp,
                "flow_id": t.flow_id,
                "vertex_id": t.vertex_id,
                "session_id": t.session_id,
                "status": t.status,
                "inputs": t.inputs,
                "outputs": t.outputs,
                "error": t.error,
            }
            for t in transactions
        ],
        count=len(transactions),
    )
    return archive.close(_manifest("end_user", actor_id))
