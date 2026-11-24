"""What an erase would remove, counted without changing anything (find and the approval dry-run)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlmodel import col, select

from langflow.services.data_subjects.errors import DeployedResourcesError, LastAdministratorError
from langflow.services.data_subjects.schemas import DryRunSummary
from langflow.services.data_subjects.stop import deployed_resources, ensure_builder_erasable
from langflow.services.data_subjects.transactions import end_user_transactions
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth.authz import AuthzShare, ShareScope
from langflow.services.database.models.data_subject_request.schemas import DataSubjectType
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.jobs.model import Job
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.variable.model import Variable

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.identity import EndUserKeys
    from langflow.services.database.models.user.model import User

MAX_LISTED_SHARED_FLOWS = 20
LIKE_ESCAPE = "\\"


async def _count(session: AsyncSession, model, *where) -> int:
    return int((await session.exec(select(func.count()).select_from(model).where(*where))).one())


async def builder_dry_run(session: AsyncSession, user: User) -> DryRunSummary:
    uid = user.id
    owned_flows = select(Flow.id).where(Flow.user_id == uid)
    shared = select(AuthzShare.resource_id).where(
        AuthzShare.resource_type == "flow",
        AuthzShare.scope != ShareScope.PUBLIC.value,
        col(AuthzShare.resource_id).in_(owned_flows),
    )
    shared_names = (
        await session.exec(
            select(Flow.name).where(col(Flow.id).in_(shared)).order_by(Flow.name).limit(MAX_LISTED_SHARED_FLOWS)
        )
    ).all()
    counts = {
        "flows": await _count(session, Flow, Flow.user_id == uid),
        "shared_flows": await _count(session, Flow, col(Flow.id).in_(shared)),
        "projects": await _count(session, Folder, Folder.user_id == uid),
        "messages": await _count(
            session, MessageTable, (col(MessageTable.flow_id).in_(owned_flows)) | (MessageTable.user_id == uid)
        ),
        "files": await _count(session, File, File.user_id == uid),
        "knowledge_bases": await _count(session, KnowledgeBaseRecord, KnowledgeBaseRecord.user_id == uid),
        "variables": await _count(session, Variable, Variable.user_id == uid),
        "api_keys": await _count(session, ApiKey, ApiKey.user_id == uid),
    }
    summary = DryRunSummary(
        subject_type=DataSubjectType.BUILDER.value,
        counts=counts,
        deployments=await deployed_resources(session, uid),
        shared_flows=[str(name) for name in shared_names],
    )
    try:
        await ensure_builder_erasable(session, user)
    except DeployedResourcesError:
        summary.blocked_by = "deployed_flows"
    except LastAdministratorError:
        summary.blocked_by = "last_administrator"
    return summary


async def end_user_dry_run(session: AsyncSession, keys: EndUserKeys, scope: tuple[UUID, ...]) -> DryRunSummary:
    message_where = [
        MessageTable.user_id == keys.message_owner_id,
        col(MessageTable.session_id).like(keys.session_like_pattern, escape=LIKE_ESCAPE),
    ]
    trace_where = [col(TraceTable.session_id).like(keys.session_like_pattern, escape=LIKE_ESCAPE)]
    job_where = [col(Job.job_metadata)["end_user_id"].as_string() == keys.raw_id]
    if scope:
        message_where.append(col(MessageTable.flow_id).in_(scope))
        trace_where.append(col(TraceTable.flow_id).in_(scope))
        job_where.append(col(Job.flow_id).in_(scope))
    flows_touched = (
        await session.exec(select(func.count(func.distinct(MessageTable.flow_id))).where(*message_where))
    ).one()
    return DryRunSummary(
        subject_type=DataSubjectType.END_USER.value,
        counts={
            "messages": await _count(session, MessageTable, *message_where),
            "traces": await _count(session, TraceTable, *trace_where),
            "transactions": await _count(session, TransactionTable, end_user_transactions(keys, scope)),
            "runs": await _count(session, Job, *job_where),
            "flows": int(flows_touched),
        },
    )
