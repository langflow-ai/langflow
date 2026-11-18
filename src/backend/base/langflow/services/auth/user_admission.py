"""Shared admission contract for active user creation paths."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.authorization import AuthorizationMutationKind

from langflow.services.authorization.lifecycle import acquire_identity_mutation_lock
from langflow.services.creation_hooks import (
    RESOURCE_USER,
    PreCreationContext,
    run_pre_creation_hooks,
)

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.authorization.base import BaseAuthorizationService
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User


async def admit_user_creation(
    session: AsyncSession,
    *,
    authorization_service: BaseAuthorizationService,
    candidate: User,
    actor_user_id: UUID | None = None,
    is_public_signup: bool = False,
    kind: AuthorizationMutationKind = AuthorizationMutationKind.USER_CREATED,
) -> None:
    """Lock and admit a user before an active or pending row is inserted.

    The authorization service owns transaction-scoped serialization, while
    registered plugins own resource policy through the OSS pre-creation hook.
    Callers keep the surrounding transaction open so a denial rolls back all
    related profile, folder, audit, or promotion work.
    """
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=kind,
        entity_id=candidate.id,
        affected_user_ids=(candidate.id,),
    )
    await run_pre_creation_hooks(
        PreCreationContext(
            resource=RESOURCE_USER,
            session=session,
            actor_user_id=actor_user_id,
            requested_name=candidate.username,
            is_public_signup=is_public_signup,
            extra={"is_active": candidate.is_active},
        )
    )


__all__ = ["admit_user_creation"]
