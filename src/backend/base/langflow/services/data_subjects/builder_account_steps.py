"""Builder erase: everything the account owns outside its flows, and references that only name the person."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlmodel import and_, col, or_, select

from langflow.services.data_subjects.audit_redaction import redact_audit_rows
from langflow.services.data_subjects.batching import clear_reference_batch, delete_batch, delete_job_batch
from langflow.services.data_subjects.transactions import builder_transactions
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth.authz import (
    AuthzAuditLog,
    AuthzEditLock,
    AuthzRole,
    AuthzRoleAssignment,
    AuthzShare,
    AuthzTeamMember,
)
from langflow.services.database.models.auth.sso import SSOConfig, SSOUserProfile
from langflow.services.database.models.catalog_policy.model import CatalogPolicyRule
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.ingestion_run.model import IngestionRun
from langflow.services.database.models.jobs.model import Job
from langflow.services.database.models.mcp_server.model import MCPServer
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.policy_bundle.model import PolicyBundleRevision
from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.variable.model import Variable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext

    Step = Callable[[AsyncSession, EraseContext], Awaitable[int]]


def _owned_folder_ids(user_id: UUID):
    return select(Folder.id).where(Folder.user_id == user_id)


async def erase_jobs(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_job_batch(session, Job.user_id == ctx.subject_user_id)


async def erase_messages_elsewhere(session: AsyncSession, ctx: EraseContext) -> int:
    """The person's own messages in flows owned by other people."""
    return await delete_batch(session, MessageTable, MessageTable.user_id == ctx.subject_user_id)


async def erase_transactions_elsewhere(session: AsyncSession, ctx: EraseContext) -> int:
    """Run records of the person's own runs in flows owned by other people."""
    return await delete_batch(session, TransactionTable, builder_transactions(ctx.subject_user_id))


async def erase_ingestion_runs(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(session, IngestionRun, IngestionRun.user_id == ctx.subject_user_id)


async def erase_shares(session: AsyncSession, ctx: EraseContext) -> int:
    """Grants to the person, and grants on the projects they own (flow shares go with each flow)."""
    uid = ctx.subject_user_id
    return await delete_batch(
        session,
        AuthzShare,
        or_(
            AuthzShare.target_id == uid,
            and_(AuthzShare.resource_type == "project", col(AuthzShare.resource_id).in_(_owned_folder_ids(uid))),
        ),
    )


async def erase_role_assignments(session: AsyncSession, ctx: EraseContext) -> int:
    """The person's own assignments, and assignments scoped to projects they own."""
    uid = ctx.subject_user_id
    return await delete_batch(
        session,
        AuthzRoleAssignment,
        or_(
            AuthzRoleAssignment.user_id == uid,
            and_(
                AuthzRoleAssignment.domain_type == "project",
                col(AuthzRoleAssignment.domain_id).in_(_owned_folder_ids(uid)),
            ),
        ),
    )


def _delete_by_user(model: type, column: object) -> Step:
    async def step(session: AsyncSession, ctx: EraseContext) -> int:
        return await delete_batch(session, model, column == ctx.subject_user_id)

    return step


def _clear_reference(model: type, column: object, *, pk: object = None) -> Step:
    async def step(session: AsyncSession, ctx: EraseContext) -> int:
        return await clear_reference_batch(session, model, column, ctx.subject_user_id, pk=pk)

    return step


async def erase_connections(session: AsyncSession, ctx: EraseContext) -> int:
    """Connections owned by the person; their secrets and OAuth rows first (FK cascade is off on SQLite)."""
    from langflow.services.database.models.connection.model import ConnectionSecret

    uid = ctx.subject_user_id
    owned = select(Connection.id).where(Connection.owner_id == uid)
    deleted = await delete_batch(
        session, ConnectionSecret, col(ConnectionSecret.connection_id).in_(owned), pk=ConnectionSecret.connection_id
    )
    deleted += await delete_batch(
        session,
        ConnectionOAuth,
        or_(ConnectionOAuth.user_id == uid, col(ConnectionOAuth.connection_id).in_(owned)),
        pk=ConnectionOAuth.connection_id,
    )
    if deleted:
        return deleted
    return await delete_batch(session, Connection, Connection.owner_id == uid)


async def erase_project_receipts(session: AsyncSession, ctx: EraseContext) -> int:
    """Replacement receipts can hold project content; they are capped per project, so one statement suffices."""
    result = await session.exec(
        delete(ProjectReplacementOperation).where(
            col(ProjectReplacementOperation.project_user_id) == ctx.subject_user_id
        )
    )
    return result.rowcount or 0


async def erase_folders(session: AsyncSession, ctx: EraseContext) -> int:
    """Leaf folders first, so a parent is never deleted while a child still points at it."""
    uid = ctx.subject_user_id
    has_children = select(Folder.parent_id).where(col(Folder.parent_id).is_not(None))
    deleted = await delete_batch(session, Folder, Folder.user_id == uid, col(Folder.id).not_in(has_children))
    if deleted:
        return deleted
    remaining = (await session.exec(select(Folder.id).where(Folder.user_id == uid).limit(1))).first()
    if remaining is None:
        return 0
    return await clear_reference_batch(session, Folder, Folder.parent_id, remaining)


BUILDER_ACCOUNT_STEPS: tuple[tuple[str, Step], ...] = (
    ("jobs", erase_jobs),
    ("messages_elsewhere", erase_messages_elsewhere),
    ("transactions_elsewhere", erase_transactions_elsewhere),
    ("ingestion_runs", erase_ingestion_runs),
    ("mcp_servers", _delete_by_user(MCPServer, MCPServer.user_id)),
    ("files", _delete_by_user(File, File.user_id)),
    ("variables", _delete_by_user(Variable, Variable.user_id)),
    ("api_keys", _delete_by_user(ApiKey, ApiKey.user_id)),
    ("connections", erase_connections),
    ("provider_accounts", _delete_by_user(DeploymentProviderAccount, DeploymentProviderAccount.user_id)),
    ("sso_profiles", _delete_by_user(SSOUserProfile, SSOUserProfile.user_id)),
    ("team_memberships", _delete_by_user(AuthzTeamMember, AuthzTeamMember.user_id)),
    ("edit_locks", _delete_by_user(AuthzEditLock, AuthzEditLock.holder_user_id)),
    ("shares", erase_shares),
    ("role_assignments", erase_role_assignments),
    ("share_creator", _clear_reference(AuthzShare, AuthzShare.created_by)),
    ("assignment_actor", _clear_reference(AuthzRoleAssignment, AuthzRoleAssignment.assigned_by)),
    ("role_creator", _clear_reference(AuthzRole, AuthzRole.created_by)),
    ("catalog_rule_creator", _clear_reference(CatalogPolicyRule, CatalogPolicyRule.created_by)),
    (
        "policy_bundle_creator",
        _clear_reference(PolicyBundleRevision, PolicyBundleRevision.created_by, pk=PolicyBundleRevision.revision),
    ),
    ("flow_editor", _clear_reference(Flow, Flow.last_modified_by)),
    ("flow_version_author", _clear_reference(FlowVersion, FlowVersion.user_id)),
    ("sso_config_creator", _clear_reference(SSOConfig, SSOConfig.created_by)),
    ("sso_config_editor", _clear_reference(SSOConfig, SSOConfig.updated_by)),
    ("audit_redaction", redact_audit_rows),
    ("audit_subject", _clear_reference(AuthzAuditLog, AuthzAuditLog.user_id)),
    ("project_receipts", erase_project_receipts),
    ("folders", erase_folders),
)
