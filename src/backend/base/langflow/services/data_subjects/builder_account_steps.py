"""Builder erase: everything the account owns outside its flows, and references that only name the person."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, update
from sqlmodel import and_, col, or_, select

from langflow.services.data_subjects.audit_redaction import redact_audit_rows
from langflow.services.data_subjects.batching import BATCH_SIZE, clear_reference_batch, delete_batch, delete_job_batch
from langflow.services.data_subjects.evaluation_steps import EVALUATION_STEPS
from langflow.services.data_subjects.transactions import builder_transactions
from langflow.services.data_subjects.upgrade_reports import erase_upgrade_reports
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth.authz import (
    AuthzAccessException,
    AuthzAuditLog,
    AuthzEditLock,
    AuthzRole,
    AuthzRoleAssignment,
    AuthzShare,
    AuthzTeamMember,
)
from langflow.services.database.models.auth.refresh_token import RefreshTokenSession
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
from langflow.services.database.models.maintenance import MAINTENANCE_ID, MaintenanceState
from langflow.services.database.models.mcp_server.model import MCPServer
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.policy_bundle.model import PolicyBundleRevision
from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.upgrade_report import UpgradeReportRepair
from langflow.services.database.models.variable.model import Variable
from langflow.services.deletion_hooks import (
    RESOURCE_FILE,
    RESOURCE_PROJECT,
    RESOURCE_VARIABLE,
    VIA_ERASE,
    DeletionContext,
    registered_post_deletion_hooks,
    registered_pre_deletion_hooks,
    run_post_deletion_after_commit,
    run_pre_deletion_hooks,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext, EraseStepPending

    Step = Callable[[AsyncSession, EraseContext], Awaitable[int | EraseStepPending]]


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


async def erase_refresh_sessions(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(
        session,
        RefreshTokenSession,
        RefreshTokenSession.user_id == ctx.subject_user_id,
        pk=RefreshTokenSession.session_digest,
    )


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


async def _erase_resources(
    session: AsyncSession,
    model: type[File | Folder | Variable],
    resource: str,
    *where: ColumnElement[bool],
) -> int:
    """Preserve bounded erase batches while guarding and reporting each resource."""
    if not (registered_pre_deletion_hooks(resource) or registered_post_deletion_hooks(resource)):
        return await delete_batch(session, model, *where)
    rows = (await session.exec(select(model).where(*where).limit(BATCH_SIZE))).all()
    contexts = [
        DeletionContext(
            resource=resource,
            resource_id=row.id,
            owner_id=row.user_id,
            name=row.name,
            via=VIA_ERASE,
            session=session,
            extra={"path": row.path} if isinstance(row, File) else {},
        )
        for row in rows
        if row.id is not None
    ]
    if not contexts:
        return 0
    for context in contexts:
        await run_pre_deletion_hooks(context)
    removed = await session.execute(
        delete(model).where(col(model.id).in_([context.resource_id for context in contexts])).returning(model.id)
    )
    ids = set(removed.scalars())
    for context in contexts:
        if context.resource_id in ids:
            run_post_deletion_after_commit(session, context)
    return len(ids)


async def erase_files(session: AsyncSession, ctx: EraseContext) -> int:
    return await _erase_resources(session, File, RESOURCE_FILE, File.user_id == ctx.subject_user_id)


async def erase_variables(session: AsyncSession, ctx: EraseContext) -> int:
    return await _erase_resources(session, Variable, RESOURCE_VARIABLE, Variable.user_id == ctx.subject_user_id)


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


async def clear_maintenance_actor(session: AsyncSession, ctx: EraseContext) -> int:
    """Clear the erased actor without overwriting a concurrent maintenance change."""
    result = await session.exec(
        update(MaintenanceState)
        .where(MaintenanceState.id == MAINTENANCE_ID, MaintenanceState.set_by == ctx.subject_user_id)
        .values(set_by=None)
    )
    return result.rowcount or 0


async def erase_folders(session: AsyncSession, ctx: EraseContext) -> int:
    """Leaf folders first, so a parent is never deleted while a child still points at it."""
    uid = ctx.subject_user_id
    has_children = select(Folder.parent_id).where(col(Folder.parent_id).is_not(None))
    deleted = await _erase_resources(
        session, Folder, RESOURCE_PROJECT, Folder.user_id == uid, col(Folder.id).not_in(has_children)
    )
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
    *EVALUATION_STEPS,
    ("mcp_servers", _delete_by_user(MCPServer, MCPServer.user_id)),
    ("files", erase_files),
    ("variables", erase_variables),
    ("api_keys", _delete_by_user(ApiKey, ApiKey.user_id)),
    ("refresh_sessions", erase_refresh_sessions),
    ("connections", erase_connections),
    ("provider_accounts", _delete_by_user(DeploymentProviderAccount, DeploymentProviderAccount.user_id)),
    ("sso_profiles", _delete_by_user(SSOUserProfile, SSOUserProfile.user_id)),
    ("team_memberships", _delete_by_user(AuthzTeamMember, AuthzTeamMember.user_id)),
    ("edit_locks", _delete_by_user(AuthzEditLock, AuthzEditLock.holder_user_id)),
    ("shares", erase_shares),
    ("role_assignments", erase_role_assignments),
    ("access_exceptions", _delete_by_user(AuthzAccessException, AuthzAccessException.user_id)),
    ("share_creator", _clear_reference(AuthzShare, AuthzShare.created_by)),
    ("access_exception_creator", _clear_reference(AuthzAccessException, AuthzAccessException.created_by)),
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
    # Append steps to preserve the positions saved in in-flight request cursors.
    ("maintenance_setter", clear_maintenance_actor),
    ("upgrade_repair_author", _delete_by_user(UpgradeReportRepair, UpgradeReportRepair.created_by)),
    ("upgrade_reports", erase_upgrade_reports),
)
