"""Tests for the default LFX AuthorizationService (no-op allow-all implementation)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from lfx.services.authorization.base import (
    AuthorizationMutation,
    AuthorizationMutationKind,
    AuthorizationMutationRejected,
    BaseAuthorizationService,
    DirectoryMembershipSnapshot,
)
from lfx.services.authorization.service import AuthorizationService


@pytest.fixture
def service() -> AuthorizationService:
    """Build a fresh default authorization service."""
    return AuthorizationService()


def test_service_is_ready_and_named(service: AuthorizationService) -> None:
    """The default service initializes ready and uses the canonical service name."""
    assert service.ready is True
    assert service.name == "authorization_service"


def test_service_subclasses_base(service: AuthorizationService) -> None:
    """The default implementation conforms to the BaseAuthorizationService contract."""
    assert isinstance(service, BaseAuthorizationService)


def test_mutation_rejection_exposes_only_public_detail() -> None:
    """Plugins can reject unsafe mutations with an API-safe typed error."""
    rejection = AuthorizationMutationRejected("At least one recovery administrator is required.")
    assert rejection.public_detail == "At least one recovery administrator is required."
    assert str(rejection) == rejection.public_detail


async def test_is_enabled_returns_false(service: AuthorizationService) -> None:
    """The LFX default reports authorization as disabled."""
    assert await service.is_enabled() is False


async def test_enforce_returns_true_for_any_input(service: AuthorizationService) -> None:
    """Default enforce permits every request regardless of arguments."""
    user_id = uuid4()
    assert (
        await service.enforce(
            user_id=user_id,
            domain="*",
            obj="flow:xyz",
            act="write",
        )
        is True
    )
    assert (
        await service.enforce(
            user_id=user_id,
            domain="other",
            obj="project:1",
            act="delete",
            context={"is_superuser": False},
        )
        is True
    )


async def test_batch_enforce_returns_all_true_for_any_length(service: AuthorizationService) -> None:
    """batch_enforce returns a True list matching the request count, for any length."""
    user_id = uuid4()

    empty = await service.batch_enforce(user_id=user_id, domain="*", requests=[])
    assert empty == []

    single = await service.batch_enforce(user_id=user_id, domain="*", requests=[("flow:a", "read")])
    assert single == [True]

    requests = [(f"flow:{i}", "read") for i in range(5)]
    five = await service.batch_enforce(user_id=user_id, domain="*", requests=requests)
    assert five == [True, True, True, True, True]


async def test_get_allowed_actions_returns_full_list(service: AuthorizationService) -> None:
    """get_allowed_actions returns every requested action when default service is used."""
    actions = ["read", "write", "delete", "execute"]
    result = await service.get_allowed_actions(
        user_id=uuid4(),
        domain="*",
        obj="flow:abc",
        actions=actions,
    )
    assert result == actions


async def test_get_effective_permissions_default_returns_all_actions_per_resource(
    service: AuthorizationService,
) -> None:
    """Default impl returns every requested action for every resource (no enforcement)."""
    rids = [uuid4(), uuid4()]
    actions = ["read", "write"]
    result = await service.get_effective_permissions(
        user_id=uuid4(),
        resource_type="flow",
        resource_ids=rids,
        actions=actions,
        domain="*",
    )
    assert result == {rids[0]: actions, rids[1]: actions}


async def test_get_effective_permissions_validates_batch_enforce_length(
    service: AuthorizationService,
) -> None:
    """A plugin returning a wrong-sized batch must raise ValueError, not silently slice.

    Without this guard, a too-short ``flat`` produces empty lists for later
    resources (out-of-bounds slice returns ``[]``) and a too-long ``flat``
    drops the tail — both yielding incorrect per-resource permissions.
    """

    async def bad_batch_enforce(**_kwargs):
        # Caller will pass 2 resources x 2 actions = 4 requests; return only 3.
        return [True, True, True]

    service.batch_enforce = bad_batch_enforce  # type: ignore[assignment]

    with pytest.raises(ValueError, match="returned 3 results for 4 requests"):
        await service.get_effective_permissions(
            user_id=uuid4(),
            resource_type="flow",
            resource_ids=[uuid4(), uuid4()],
            actions=["read", "write"],
            domain="*",
        )


async def test_invalidate_user_is_noop(service: AuthorizationService) -> None:
    """Cache invalidation hooks are no-ops on the default LFX implementation."""
    assert await service.invalidate_user(uuid4()) is None


async def test_invalidate_role_is_noop(service: AuthorizationService) -> None:
    """Cache invalidation hooks are no-ops on the default LFX implementation."""
    assert await service.invalidate_role(uuid4()) is None


async def test_invalidate_all_is_noop(service: AuthorizationService) -> None:
    """Cache invalidation hooks are no-ops on the default LFX implementation."""
    assert await service.invalidate_all() is None


async def test_identity_and_directory_contracts_are_default_noops(service: AuthorizationService) -> None:
    """OSS stays pass-through while exposing stable plugin lifecycle value objects."""
    user_id = uuid4()
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.USER_DISABLED,
        entity_id=user_id,
        affected_user_ids=(user_id,),
    )
    snapshot = DirectoryMembershipSnapshot(
        provider_id="directory-1",
        source="scim",
        observed_at=datetime.now(timezone.utc),
        user_id=user_id,
        provider_user_id="provider-user-1",
        memberships=("engineering", "reviewers"),
    )
    session = object()

    assert await service.validate_identity_mutation(session=session, mutation=mutation) is None
    assert await service.stage_identity_mutation(session=session, event=mutation) is None
    assert await service.identity_mutation_committed(mutation) is None
    assert await service.ingest_directory_membership_snapshot(session=session, snapshot=snapshot) is None


async def test_identity_committed_adapts_to_legacy_invalidation_hooks(
    service: AuthorizationService,
) -> None:
    """Older plugins receive targeted invalidations without implementing the new hook."""
    user_id = uuid4()
    role_id = uuid4()
    service.invalidate_user = AsyncMock()  # type: ignore[method-assign]
    service.invalidate_role = AsyncMock()  # type: ignore[method-assign]
    service.invalidate_all = AsyncMock()  # type: ignore[method-assign]

    await service.identity_mutation_committed(
        AuthorizationMutation(
            kind=AuthorizationMutationKind.ROLE_ASSIGNMENT_CREATED,
            entity_id=uuid4(),
            affected_user_ids=(user_id,),
            role_id=role_id,
        )
    )
    service.invalidate_user.assert_awaited_once_with(user_id)

    await service.identity_mutation_committed(
        AuthorizationMutation(
            kind=AuthorizationMutationKind.ROLE_UPDATED,
            entity_id=role_id,
            role_id=role_id,
        )
    )
    service.invalidate_role.assert_awaited_once_with(role_id)

    await service.identity_mutation_committed(
        AuthorizationMutation(
            kind=AuthorizationMutationKind.TEAM_DELETED,
            entity_id=uuid4(),
        )
    )
    service.invalidate_all.assert_awaited_once_with()
