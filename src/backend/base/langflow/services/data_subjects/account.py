"""The last step of a builder erase: the account row, through the same protocol as a user delete.

Lock, read, validate, delete, stage, commit, publish, audit: authorization plugins verify this order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.authorization import AuthorizationMutationKind, AuthorizationMutationRejected

from langflow.services.authorization.audit import AUDIT_EVENT_MUTATION, audit_decision, stage_audit_decision
from langflow.services.authorization.lifecycle import (
    acquire_identity_mutation_lock,
    safe_identity_mutation_committed,
    stage_identity_mutation,
    validate_identity_mutation,
)
from langflow.services.data_subjects.errors import ProtectedAccountError
from langflow.services.data_subjects.lifecycle import account_deletion_mutation
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service, session_scope

if TYPE_CHECKING:
    from uuid import UUID


async def delete_account(request_id: UUID, user_id: UUID, actor_id: UUID | None) -> None:
    authorization_service = get_authorization_service()
    async with session_scope() as session:
        await acquire_identity_mutation_lock(
            authorization_service,
            session,
            kind=AuthorizationMutationKind.USER_DELETED,
            entity_id=user_id,
            affected_user_ids=(user_id,),
        )
        user = await session.get(User, user_id)
        if user is None:
            return
        mutation = account_deletion_mutation(user, actor_id)
        try:
            await validate_identity_mutation(authorization_service, session, mutation)
        except AuthorizationMutationRejected as exc:
            raise ProtectedAccountError(exc.public_detail) from exc
        details = {
            "event": AUDIT_EVENT_MUTATION,
            "target_was_active": mutation.user_before.is_active,
            "target_was_superuser": mutation.user_before.is_superuser,
            "data_subject_request_id": str(request_id),
        }
        await session.delete(user)
        await session.flush()
        await stage_identity_mutation(authorization_service, session, mutation)
        staged = stage_audit_decision(
            session=session,
            user_id=actor_id,
            action="user:delete",
            obj=f"user:{user_id}",
            result="allow",
            details=details,
        )
        await session.commit()
    await safe_identity_mutation_committed(authorization_service, mutation)
    if not staged:
        await audit_decision(
            user_id=actor_id, action="user:delete", obj=f"user:{user_id}", result="allow", details=details
        )
