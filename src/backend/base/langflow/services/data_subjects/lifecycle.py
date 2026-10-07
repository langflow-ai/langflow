"""The identity-mutation protocol for erasing an account, shared by approval and the final account delete.

Erasure is reported as ``USER_DELETED`` with the approving admin as actor, so every guard an
authorization plugin attaches to a user delete (break-glass, last recoverable admin) applies unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.authorization import (
    AuthorizationMutation,
    AuthorizationMutationKind,
    AuthorizationMutationRejected,
    UserAuthorizationSnapshot,
)

from langflow.services.authorization.lifecycle import (
    acquire_identity_mutation_lock,
    validate_identity_mutation,
)
from langflow.services.data_subjects.errors import ProtectedAccountError
from langflow.services.deps import get_authorization_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User


def account_deletion_mutation(user: User, actor_id: UUID | None) -> AuthorizationMutation:
    return AuthorizationMutation(
        kind=AuthorizationMutationKind.USER_DELETED,
        entity_id=user.id,
        actor_user_id=actor_id,
        affected_user_ids=(user.id,),
        policy_relevant_fields=("is_active", "is_superuser"),
        user_before=UserAuthorizationSnapshot(is_active=user.is_active, is_superuser=user.is_superuser),
        user_after=None,
    )


async def lock_account(session: AsyncSession, user_id: UUID) -> None:
    await acquire_identity_mutation_lock(
        get_authorization_service(),
        session,
        kind=AuthorizationMutationKind.USER_DELETED,
        entity_id=user_id,
        affected_user_ids=(user_id,),
    )


async def ensure_plugin_allows_deletion(session: AsyncSession, mutation: AuthorizationMutation) -> None:
    try:
        await validate_identity_mutation(get_authorization_service(), session, mutation)
    except AuthorizationMutationRejected as exc:
        raise ProtectedAccountError(exc.public_detail) from exc
