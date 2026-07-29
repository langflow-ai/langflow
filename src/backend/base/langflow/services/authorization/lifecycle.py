"""Transactional lifecycle helpers for authorization plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.services.authorization.base import AuthorizationMutation, BaseAuthorizationService
    from sqlmodel.ext.asyncio.session import AsyncSession


async def validate_identity_mutation(
    service: BaseAuthorizationService,
    session: AsyncSession,
    mutation: AuthorizationMutation,
) -> None:
    """Run the plugin's pre-mutation identity guard in the caller's transaction."""
    await service.validate_identity_mutation(
        session=session,
        mutation=mutation,
    )


async def stage_identity_mutation(
    service: BaseAuthorizationService,
    session: AsyncSession,
    mutation: AuthorizationMutation,
) -> None:
    """Stage derived policy before commit; failures abort the canonical write."""
    await service.stage_identity_mutation(
        session=session,
        event=mutation,
    )


async def safe_identity_mutation_committed(
    service: BaseAuthorizationService,
    mutation: AuthorizationMutation,
) -> None:
    """Publish a committed change without misreporting the durable DB result.

    Staging is the correctness boundary. Publication is a post-commit
    convergence optimization, so a plugin failure is logged and left to the
    plugin's durable retry/reconciliation path rather than surfaced as a 5xx
    that could encourage a duplicate write.
    """
    try:
        await service.identity_mutation_committed(mutation)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Authorization lifecycle publication failed after %s for entity=%s",
            mutation.kind.value,
            mutation.entity_id,
        )
