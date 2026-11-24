"""Seed a builder with data in every table an erase must reach, plus a colleague whose data must survive."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.a2a.model import A2ATask
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth.authz import AuthzAuditLog, AuthzShare
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import AccessTypeEnum, Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.jobs.model import Job, JobEvent, JobStatus
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanKind, SpanStatus, SpanTable, SpanType, TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.deps import get_settings_service, session_scope
from lfx.memory.flow_context import derive_message_owner_uuid


@dataclass
class SeededBuilder:
    user_id: UUID
    username: str
    flow_id: UUID
    folder_id: UUID
    colleague_id: UUID
    colleague_flow_id: UUID
    file_path: Path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def message(flow_id: UUID, session_id: str, text: str, user_id: UUID | None) -> MessageTable:
    return MessageTable(
        sender="User", sender_name="User", session_id=session_id, text=text, flow_id=flow_id, user_id=user_id
    )


def end_user_message(flow_id: UUID, end_user_id: str, text: str) -> MessageTable:
    return message(flow_id, f"{end_user_id}::s1", text, derive_message_owner_uuid(end_user_id))


async def create_user(username: str, *, superuser: bool = False) -> UUID:
    async with session_scope() as session:
        user = User(
            username=username,
            password=get_password_hash("test-password-123"),
            is_active=True,
            is_superuser=superuser,
        )
        session.add(user)
        await session.flush()
        return user.id


def _flow_history(flow_id: UUID, owner_id: UUID) -> list:
    trace = TraceTable(name="run", status=SpanStatus.OK, flow_id=flow_id, session_id="alice::s1")
    job = Job(
        job_id=uuid4(),
        flow_id=flow_id,
        status=JobStatus.COMPLETED,
        created_timestamp=_now(),
        user_id=owner_id,
        job_metadata={"end_user_id": "alice"},
    )
    return [
        end_user_message(flow_id, "alice", "alice@example.com wrote this"),
        TransactionTable(vertex_id="v1", status="success", flow_id=flow_id, inputs={"text": "alice@example.com"}),
        VertexBuildTable(id="v1", valid=True, flow_id=flow_id, job_id=job.job_id, data={"text": "alice@example.com"}),
        trace,
        SpanTable(
            name="span",
            span_type=SpanType.CHAIN,
            status=SpanStatus.OK,
            span_kind=SpanKind.INTERNAL,
            trace_id=trace.id,
        ),
        job,
        JobEvent(job_id=job.job_id, seq=1, event_type="run_started", created_at=_now()),
        A2ATask(id="task-1", owner=f"{flow_id}:{owner_id}", task={"text": "alice@example.com"}),
    ]


async def seed_builder(username: str = "maria") -> SeededBuilder:
    user_id = await create_user(username)
    colleague_id = await create_user(f"{username}-colleague")
    config_dir = Path(get_settings_service().settings.config_dir)
    async with session_scope() as session:
        folder = Folder(name="Maria project", user_id=user_id)
        colleague_folder = Folder(name="Colleague project", user_id=colleague_id)
        session.add_all([folder, colleague_folder])
        await session.flush()
        flow = Flow(name="maria-flow", user_id=user_id, folder_id=folder.id, access_type=AccessTypeEnum.PUBLIC)
        colleague_flow = Flow(name="colleague-flow", user_id=colleague_id, folder_id=colleague_folder.id)
        session.add_all([flow, colleague_flow])
        await session.flush()
        stored = config_dir / str(user_id) / "cv.txt"
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_text("maria cv", encoding="utf-8")
        session.add_all(
            [
                *_flow_history(flow.id, user_id),
                message(colleague_flow.id, str(colleague_flow.id), "maria testing a colleague flow", user_id),
                message(colleague_flow.id, str(colleague_flow.id), "colleague's own message", colleague_id),
                Variable(name="OPENAI_KEY", value="secret", user_id=user_id),
                ApiKey(name="maria key", api_key=f"sk-{uuid4().hex}", user_id=user_id),
                File(user_id=user_id, name="cv.txt", path=f"{user_id}/cv.txt", size=8),
                AuthzShare(
                    resource_type="flow",
                    resource_id=flow.id,
                    scope="user",
                    target_id=colleague_id,
                    permission_level="read",
                    created_by=user_id,
                    created_at=_now(),
                ),
                AuthzShare(
                    resource_type="flow",
                    resource_id=colleague_flow.id,
                    scope="user",
                    target_id=user_id,
                    permission_level="write",
                    created_by=colleague_id,
                    created_at=_now(),
                ),
                AuthzAuditLog(
                    user_id=user_id,
                    actor_id=user_id,
                    action="cli_admin_password_reset",
                    result="allow",
                    details={"username": username, "client_ip": "10.0.0.7", "event": "mutation"},
                    timestamp=_now(),
                ),
            ]
        )
        return SeededBuilder(
            user_id=user_id,
            username=username,
            flow_id=flow.id,
            folder_id=folder.id,
            colleague_id=colleague_id,
            colleague_flow_id=colleague_flow.id,
            file_path=stored,
        )
