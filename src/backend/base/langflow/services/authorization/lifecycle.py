"""Transactional lifecycle helpers for authorization plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy import func
from sqlmodel import col, select

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.authorization.base import (
        AuthorizationMutation,
        AuthorizationMutationKind,
        BaseAuthorizationService,
        ShareRuleSnapshot,
    )
    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True, slots=True)
class OwnedResourceImpact:
    """Bounded, non-secret summary used to reject unsafe account deletion."""

    total: int
    counts: dict[str, int]
    sample_ids: dict[str, tuple[str, ...]]

    @property
    def exists(self) -> bool:
        return self.total > 0

    def public_detail(self) -> dict[str, object]:
        return {
            "code": "RESOURCE_OWNERSHIP_REQUIRES_DISPOSITION",
            "message": "This user still owns resources. Reassign or delete them before deleting the account.",
            "owned_resource_count": self.total,
            "owned_resources": self.counts,
            "sample_resource_ids": self.sample_ids,
            "sample_truncated": any(self.counts[key] > len(ids) for key, ids in self.sample_ids.items()),
        }


async def owned_resource_impact(
    session: AsyncSession,
    *,
    user_id: UUID,
    sample_limit: int = 3,
) -> OwnedResourceImpact:
    """Find every canonical resource that would be orphaned or cascaded."""
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.file.model import File
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
    from langflow.services.database.models.memory_base.model import MemoryBase
    from langflow.services.database.models.variable.model import Variable

    families = (
        ("project", Folder),
        ("flow", Flow),
        ("deployment", Deployment),
        ("knowledge_base", KnowledgeBaseRecord),
        ("memory_base", MemoryBase),
        ("variable", Variable),
        ("file", File),
        ("provider_account", DeploymentProviderAccount),
    )
    counts: dict[str, int] = {}
    samples: dict[str, tuple[str, ...]] = {}
    for resource_type, model in families:
        owner_column = model.user_id
        count = int((await session.exec(select(func.count()).select_from(model).where(owner_column == user_id))).one())
        if count == 0:
            continue
        rows = (
            await session.exec(
                select(model.id).where(owner_column == user_id).order_by(col(model.id)).limit(sample_limit)
            )
        ).all()
        counts[resource_type] = count
        samples[resource_type] = tuple(str(resource_id) for resource_id in rows)
    return OwnedResourceImpact(total=sum(counts.values()), counts=counts, sample_ids=samples)


async def acquire_identity_mutation_lock(
    service: BaseAuthorizationService,
    session: AsyncSession,
    *,
    kind: AuthorizationMutationKind,
    entity_id: UUID | None = None,
    affected_user_ids: tuple[UUID, ...] = (),
) -> None:
    """Run the plugin's lock-only preflight before canonical identity reads."""
    await service.acquire_identity_mutation_lock(
        session=session,
        kind=kind,
        entity_id=entity_id,
        affected_user_ids=affected_user_ids,
    )


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


async def stage_resource_mutation(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    changed_fields: tuple[str, ...] = (),
    deleted: bool = False,
) -> None:
    """Stage changed canonical scope after the caller's complete resource mutation."""
    from lfx.services.authorization.base import ResourcePolicyMutation

    from langflow.services.deps import get_authorization_service

    if changed_fields or deleted:
        await get_authorization_service().stage_resource_mutation(
            session=session,
            event=ResourcePolicyMutation(
                resource_type,
                resource_id,
                changed_fields,
                deleted,
            ),
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


async def safe_directory_membership_committed(
    service: BaseAuthorizationService,
    *,
    user_id: UUID,
    changed: bool,
) -> None:
    """Publish committed directory membership without misreporting durable success."""
    try:
        await service.directory_membership_committed(user_id=user_id, changed=changed)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Authorization directory publication failed after commit for user=%s",
            user_id,
        )


async def safe_share_rules_removed(
    service: BaseAuthorizationService,
    snapshots: tuple[ShareRuleSnapshot, ...],
) -> None:
    """Publish grant removals after commit without weakening DB correctness."""
    if not snapshots:
        return
    try:
        for snapshot in snapshots:
            await service.remove_share_rules(snapshot)
    except Exception:  # noqa: BLE001 - post-commit compatibility fallback
        logger.exception("Authorization share cleanup publication failed; invalidating all policy")
        try:
            await service.invalidate_all()
        except Exception:  # noqa: BLE001 - durable rows already committed
            logger.exception("Authorization invalidation failed after durable share cleanup")
