"""Abstract base class for authorization services."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict
from uuid import UUID as _UUID

from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID


class AuthzContext(TypedDict, total=False):
    """Documented keys for the enforce/batch_enforce context dict."""

    is_superuser: bool
    flow_user_id: _UUID | None
    deployment_user_id: _UUID | None
    project_user_id: _UUID | None
    knowledge_base_user_id: _UUID | None
    variable_user_id: _UUID | None
    file_user_id: _UUID | None
    share_user_id: _UUID | None
    workspace_id: _UUID | None
    folder_id: _UUID | None


class BaseAuthorizationService(Service, abc.ABC):
    """Abstract base class for authorization (RBAC) services."""

    name = ServiceType.AUTHORIZATION_SERVICE.value

    # True when the service can authorize non-owner access (share-aware fetch).
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
