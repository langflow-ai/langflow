"""Abstract base class for authorization services."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, ClassVar

from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID


class BaseAuthorizationService(Service, abc.ABC):
    """Abstract base class for authorization (RBAC) services.

    Authentication establishes identity; authorization decides what that identity may do.
    Enterprise plugins provide Casbin-backed implementations; OSS ships a no-op default.
    """

    name = ServiceType.AUTHORIZATION_SERVICE.value

    # Capability flag. Implementations that can authorize non-owner access (share
    # grants, domain roles) set this to True so share-aware fetch helpers load
    # resources by id and rely on enforce() to gate access. The OSS pass-through
    # leaves this False so fetch helpers keep their owner-scoped queries — that
    # way enabling AUTHZ_ENABLED without an enterprise plugin does not silently
    # widen visibility.
    SUPPORTS_CROSS_USER_FETCH: ClassVar[bool] = False

    async def supports_cross_user_fetch(self) -> bool:
        """Return True when this service can authorize non-owner resource access."""
        return self.SUPPORTS_CROSS_USER_FETCH

    @abc.abstractmethod
    async def is_enabled(self) -> bool:
        """Return True when authorization enforcement is active."""

    @abc.abstractmethod
    async def enforce(
        self,
        *,
        user_id: UUID,
        domain: str,
        obj: str,
        act: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Return True if the user may perform `act` on `obj` within `domain`."""

    @abc.abstractmethod
    async def batch_enforce(
        self,
        *,
        user_id: UUID,
        domain: str,
        requests: Sequence[tuple[str, str]],
        context: dict[str, Any] | None = None,
    ) -> list[bool]:
        """Evaluate multiple (obj, act) pairs. Order matches `requests`."""

    async def get_allowed_actions(
        self,
        *,
        user_id: UUID,
        domain: str,
        obj: str,
        actions: Sequence[str],
        context: dict[str, Any] | None = None,
    ) -> list[str]:
        """Return the subset of `actions` that are allowed for this user/object."""
        results = await self.batch_enforce(
            user_id=user_id,
            domain=domain,
            requests=[(obj, action) for action in actions],
            context=context,
        )
        return [action for action, allowed in zip(actions, results, strict=True) if allowed]

    async def invalidate_user(self, user_id: UUID) -> None:
        """Drop cached policy for a single user. Plugin override; OSS no-op."""

    async def invalidate_role(self, role_id: UUID) -> None:
        """Drop cached policy for a single role. Plugin override; OSS no-op."""

    async def invalidate_all(self) -> None:
        """Drop all cached policy. Plugin override; OSS no-op."""

    async def teardown(self) -> None:
        """No resources to release in the base implementation."""
