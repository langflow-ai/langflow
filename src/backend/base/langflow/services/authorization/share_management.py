"""Transactional canonical share mutation and recipient validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.services.authorization.base import ShareRuleSnapshot
from sqlalchemy import delete, or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.services.authorization.audit import stage_mutation_audit
from langflow.services.authorization.concurrency import RevisionPreconditionError, require_revision_precondition
from langflow.services.authorization.repository import ResourceRecord, load_resource, supported_actions
from langflow.services.authorization.team_management import team_is_valid_recipient
from langflow.services.database.lock_retry import RetryableTransactionError
from langflow.services.database.models.auth import (
    AuthzShare,
    SharePermissionLevel,
    ShareScope,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True, slots=True)
class ShareMutationResult:
    row: AuthzShare
    resource: ResourceRecord
    changed: bool


@dataclass(frozen=True, slots=True)
class ShareDeletionResult:
    snapshot: ShareRuleSnapshot
    resource: ResourceRecord


class ShareManagementError(Exception):
    """Stable domain failure translated at the HTTP boundary."""

    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    @property
    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class _ShareLockSetChangedError(ShareManagementError, RetryableTransactionError):
    """Request a bounded replay after stored share identity fields change."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="SHARE_CHANGED",
            message="The share changed while the operation was being prepared.",
        )


def _error(status_code: int, code: str, message: str) -> ShareManagementError:
    return ShareManagementError(status_code=status_code, code=code, message=message)


def _validate_value_contract(*, resource_type: str, scope: str, permission_level: str) -> None:
    if not supported_actions(resource_type):
        raise _error(422, "SHARE_RESOURCE_UNSUPPORTED", "This resource type cannot be shared.")
    try:
        resolved_scope = ShareScope(scope)
        resolved_permission = SharePermissionLevel(permission_level)
    except ValueError as exc:
        raise _error(422, "SHARE_VALUE_INVALID", "The share scope or permission is invalid.") from exc
    if (
        resource_type == "flow"
        and resolved_scope is ShareScope.PUBLIC
        and resolved_permission is not SharePermissionLevel.EXECUTE
    ):
        raise _error(
            422,
            "SHARE_PUBLIC_FLOW_EXECUTE_REQUIRED",
            "Public flow shares require execute permission.",
        )


async def validate_share_recipient(
    session: AsyncSession,
    *,
    scope: str,
    target_id: UUID | None,
    lock: bool,
    require_eligible: bool = True,
) -> None:
    """Validate the current canonical recipient under the mutation lock."""
    if scope in {ShareScope.PRIVATE.value, ShareScope.PUBLIC.value}:
        if target_id is not None:
            raise _error(422, "SHARE_TARGET_FORBIDDEN", "This share scope cannot have a recipient.")
        return
    if target_id is None:
        raise _error(422, "SHARE_TARGET_REQUIRED", "This share scope requires a recipient.")
    if scope == ShareScope.USER.value:
        if lock and session.get_bind().dialect.name == "sqlite":
            await session.exec(update(User).where(User.id == target_id).values(updated_at=User.updated_at))
        statement = select(User).where(User.id == target_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        user = (await session.exec(statement)).first()
        if require_eligible and (user is None or user.is_active is not True):
            raise _error(422, "SHARE_RECIPIENT_INELIGIBLE", "The selected user is not an active recipient.")
        return
    if scope == ShareScope.TEAM.value:
        try:
            valid = await team_is_valid_recipient(session, target_id, lock=lock)
        except RetryableTransactionError as exc:
            raise _ShareLockSetChangedError from exc
        if require_eligible and not valid:
            raise _error(422, "SHARE_RECIPIENT_INELIGIBLE", "The selected team is not an active valid recipient.")
        return
    raise _error(422, "SHARE_VALUE_INVALID", "The share scope is invalid.")


async def resolve_resource_for_share(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    lock: bool = False,
) -> ResourceRecord:
    resource = await load_resource(
        session,
        resource_type=resource_type,
        resource_id=resource_id,
        lock=lock,
    )
    if resource is None:
        raise _error(404, "SHARE_RESOURCE_NOT_FOUND", "Resource not found.")
    return resource


async def get_share_for_authorization(session: AsyncSession, share_id: UUID) -> tuple[AuthzShare, ResourceRecord]:
    """Resolve stored share/resource context before an authorization decision."""
    row = await session.get(AuthzShare, share_id)
    if row is None:
        raise _error(404, "SHARE_NOT_FOUND", "Share not found.")
    resource = await resolve_resource_for_share(
        session,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
    )
    return row, resource


async def create_share(
    session: AsyncSession,
    *,
    actor_id: UUID,
    resource_type: str,
    resource_id: UUID,
    scope: str,
    target_id: UUID | None,
    permission_level: str,
) -> ShareMutationResult:
    """Create one unique grant and its audit record in the same transaction."""
    await get_authorization_service().acquire_share_mutation_lock(session=session)
    _validate_value_contract(
        resource_type=resource_type,
        scope=scope,
        permission_level=permission_level,
    )
    await validate_share_recipient(session, scope=scope, target_id=target_id, lock=True)
    resource = await resolve_resource_for_share(
        session,
        resource_type=resource_type,
        resource_id=resource_id,
        lock=True,
    )

    duplicate = select(AuthzShare.id).where(
        AuthzShare.resource_type == resource_type,
        AuthzShare.resource_id == resource_id,
        AuthzShare.scope == scope,
    )
    duplicate = duplicate.where(
        AuthzShare.target_id == target_id if target_id is not None else col(AuthzShare.target_id).is_(None)
    )
    if (await session.exec(duplicate.with_for_update())).first() is not None:
        raise _error(409, "SHARE_EXISTS", "A share already exists for this recipient and resource.")

    now = datetime.now(timezone.utc)
    row = AuthzShare(
        resource_type=resource_type,
        resource_id=resource_id,
        scope=scope,
        target_id=target_id,
        permission_level=permission_level,
        revision=1,
        created_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    stage_mutation_audit(
        session=session,
        user_id=actor_id,
        action="share:create",
        obj=f"{resource_type}:{resource_id}",
        details={
            "share_id": str(row.id),
            "scope": scope,
            "target_id": str(target_id) if target_id else None,
            "permission_level": permission_level,
            "revision": row.revision,
        },
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        raise _error(409, "SHARE_EXISTS", "A share already exists for this recipient and resource.") from exc
    await _stage_share(session, row)
    return ShareMutationResult(row=row, resource=resource, changed=True)


async def _lock_stored_share(
    session: AsyncSession,
    *,
    share_id: UUID,
    require_eligible_recipient: bool,
) -> tuple[AuthzShare, ResourceRecord]:
    """Lock recipient, resource, then share and verify the preliminary hint."""
    await get_authorization_service().acquire_share_mutation_lock(session=session)
    hint_statement = select(AuthzShare).where(AuthzShare.id == share_id).execution_options(populate_existing=True)
    hint_row = (await session.exec(hint_statement)).first()
    if hint_row is None:
        raise _error(404, "SHARE_NOT_FOUND", "Share not found.")
    identity_hint = (
        hint_row.resource_type,
        hint_row.resource_id,
        hint_row.scope,
        hint_row.target_id,
    )

    await validate_share_recipient(
        session,
        scope=hint_row.scope,
        target_id=hint_row.target_id,
        lock=True,
        require_eligible=require_eligible_recipient,
    )
    resource = await resolve_resource_for_share(
        session,
        resource_type=hint_row.resource_type,
        resource_id=hint_row.resource_id,
        lock=True,
    )
    locked_statement = (
        select(AuthzShare).where(AuthzShare.id == share_id).with_for_update().execution_options(populate_existing=True)
    )
    row = (await session.exec(locked_statement)).first()
    if row is None:
        raise _error(404, "SHARE_NOT_FOUND", "Share not found.")
    if (row.resource_type, row.resource_id, row.scope, row.target_id) != identity_hint:
        raise _ShareLockSetChangedError
    return row, resource


async def update_share(
    session: AsyncSession,
    *,
    actor_id: UUID,
    share_id: UUID,
    permission_level: str,
    if_match: str | None,
    precondition_required: bool,
) -> ShareMutationResult:
    """Update one grant against its locked canonical revision."""
    row, resource = await _lock_stored_share(
        session,
        share_id=share_id,
        require_eligible_recipient=True,
    )
    _validate_value_contract(
        resource_type=row.resource_type,
        scope=row.scope,
        permission_level=permission_level,
    )
    try:
        require_revision_precondition(
            resource_type="share",
            resource_id=row.id,
            current_revision=row.revision,
            if_match=if_match,
            required=precondition_required,
            changed_code="SHARE_CHANGED",
        )
    except RevisionPreconditionError as exc:
        raise _error(exc.status_code, exc.code, exc.message) from exc

    if row.permission_level == permission_level:
        return ShareMutationResult(row=row, resource=resource, changed=False)

    previous = row.permission_level
    row.permission_level = permission_level
    row.revision += 1
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    stage_mutation_audit(
        session=session,
        user_id=actor_id,
        action="share:update",
        obj=f"{row.resource_type}:{row.resource_id}",
        details={
            "share_id": str(row.id),
            "previous_permission_level": previous,
            "permission_level": row.permission_level,
            "revision": row.revision,
        },
    )
    await session.flush()
    await _stage_share(session, row)
    return ShareMutationResult(row=row, resource=resource, changed=True)


async def delete_share(
    session: AsyncSession,
    *,
    actor_id: UUID,
    share_id: UUID,
    if_match: str | None,
    precondition_required: bool,
) -> ShareDeletionResult:
    """Delete exactly one locked grant and atomically retain its audit trail."""
    row, resource = await _lock_stored_share(
        session,
        share_id=share_id,
        require_eligible_recipient=False,
    )
    try:
        require_revision_precondition(
            resource_type="share",
            resource_id=row.id,
            current_revision=row.revision,
            if_match=if_match,
            required=precondition_required,
            changed_code="SHARE_CHANGED",
        )
    except RevisionPreconditionError as exc:
        raise _error(exc.status_code, exc.code, exc.message) from exc

    snapshot = ShareRuleSnapshot(
        share_id=row.id,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        scope=row.scope,
        target_id=row.target_id,
        permission_level=row.permission_level,
    )
    stage_mutation_audit(
        session=session,
        user_id=actor_id,
        action="share:delete",
        obj=f"{row.resource_type}:{row.resource_id}",
        details={
            "share_id": str(row.id),
            "scope": row.scope,
            "target_id": str(row.target_id) if row.target_id else None,
            "permission_level": row.permission_level,
            "revision": row.revision,
        },
    )
    await session.delete(row)
    await session.flush()
    await get_authorization_service().stage_share_mutation(session=session, snapshot=snapshot)
    return ShareDeletionResult(snapshot=snapshot, resource=resource)


async def delete_resource_shares(
    session: AsyncSession,
    *,
    actor_id: UUID,
    resources: tuple[tuple[str, UUID], ...],
) -> tuple[ShareRuleSnapshot, ...]:
    """Remove grants for resources being deleted without touching recipients."""
    if not resources:
        return ()
    await get_authorization_service().acquire_share_mutation_lock(session=session)
    ordered_resources = sorted(set(resources), key=lambda item: (item[0], str(item[1])))
    rows: list[AuthzShare] = []
    for offset in range(0, len(ordered_resources), 200):
        statement = (
            select(AuthzShare)
            .where(
                or_(
                    *(
                        (AuthzShare.resource_type == resource_type) & (AuthzShare.resource_id == resource_id)
                        for resource_type, resource_id in ordered_resources[offset : offset + 200]
                    )
                )
            )
            .order_by(col(AuthzShare.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        rows.extend((await session.exec(statement)).all())
    rows.sort(key=lambda row: str(row.id))
    snapshots = tuple(
        ShareRuleSnapshot(
            share_id=row.id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            scope=row.scope,
            target_id=row.target_id,
            permission_level=row.permission_level,
        )
        for row in rows
    )
    for row in rows:
        stage_mutation_audit(
            session=session,
            user_id=actor_id,
            action="share:delete",
            obj=f"{row.resource_type}:{row.resource_id}",
            details={
                "share_id": str(row.id),
                "reason": "resource_deleted",
                "scope": row.scope,
                "target_id": str(row.target_id) if row.target_id else None,
                "permission_level": row.permission_level,
                "revision": row.revision,
            },
        )
    if rows:
        for offset in range(0, len(rows), 500):
            await session.exec(
                delete(AuthzShare).where(col(AuthzShare.id).in_([row.id for row in rows[offset : offset + 500]]))
            )
        await session.flush()
        targeted = next((snapshot for snapshot in snapshots if snapshot.scope in {"user", "team"}), snapshots[0])
        await get_authorization_service().stage_share_mutation(session=session, snapshot=targeted)
    return snapshots


async def _stage_share(session: AsyncSession, row: AuthzShare) -> None:
    await get_authorization_service().stage_share_mutation(
        session=session,
        snapshot=ShareRuleSnapshot(
            row.id,
            row.resource_type,
            row.resource_id,
            row.scope,
            row.target_id,
            row.permission_level,
        ),
    )


__all__ = [
    "ShareDeletionResult",
    "ShareManagementError",
    "ShareMutationResult",
    "create_share",
    "delete_resource_shares",
    "delete_share",
    "get_share_for_authorization",
    "resolve_resource_for_share",
    "update_share",
    "validate_share_recipient",
]
