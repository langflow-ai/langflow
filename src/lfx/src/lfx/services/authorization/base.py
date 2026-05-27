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

    async def list_visible_resource_ids(
        self,
        *,
        user_id: UUID,
        resource_type: str,
        domain: str = "*",
        act: str = "read",
        context: dict[str, Any] | None = None,
    ) -> list[UUID] | None:
        """Return resource IDs of `resource_type` the user can `act` on, or ``None``.

        Plugin override returns a concrete list — typically by querying its
        policy store (e.g. SQL join on the policy-rule table) so list endpoints
        can prefilter at the DB layer and avoid fetching invisible rows.

        Base returns ``None`` meaning "no prefilter available; caller should
        fetch all candidates and apply :func:`filter_visible_resources` for
        in-memory filtering via :meth:`batch_enforce`." OSS pass-through stays
        on ``None`` so the existing list endpoints behave unchanged.
        """
        _ = (user_id, resource_type, domain, act, context)
        return None

    async def get_effective_permissions(
        self,
        *,
        user_id: UUID,
        resource_type: str,
        resource_ids: Sequence[UUID],
        actions: Sequence[str],
        domain: str = "*",
        context: dict[str, Any] | None = None,
    ) -> dict[UUID, list[str]]:
        """Return per-resource allowed actions for ``user_id``.

        Used by the frontend permission-gating layer to grey out buttons
        without round-tripping to a 403. Default implementation issues a single
        :meth:`batch_enforce` over the cartesian product of ``resource_ids`` x
        ``actions``; plugins can override with a tighter query.
        """
        if not resource_ids or not actions:
            return {rid: [] for rid in resource_ids}

        requests: list[tuple[str, str]] = [
            (f"{resource_type}:{rid}", action) for rid in resource_ids for action in actions
        ]
        flat = await self.batch_enforce(
            user_id=user_id,
            domain=domain,
            requests=requests,
            context=context,
        )
        # Fail fast on contract violation: each request must produce exactly
        # one result, in order. Without this, a too-short result would silently
        # truncate later resources to `[]` (out-of-bounds slice returns empty)
        # and a too-long result would drop tail entries — both yielding wrong
        # per-resource permissions without any error.
        expected = len(requests)
        if len(flat) != expected:
            msg = (
                f"batch_enforce returned {len(flat)} results for {expected} requests "
                f"({len(resource_ids)} resources x {len(actions)} actions); "
                f"plugin must return one result per request in order."
            )
            raise ValueError(msg)

        result: dict[UUID, list[str]] = {}
        action_count = len(actions)
        for index, rid in enumerate(resource_ids):
            start = index * action_count
            slice_ = flat[start : start + action_count]
            result[rid] = [action for action, allowed in zip(actions, slice_, strict=True) if allowed]
        return result

    async def invalidate_user(self, user_id: UUID) -> None:
        """Drop cached policy for a single user. Plugin override; OSS no-op."""

    async def invalidate_role(self, role_id: UUID) -> None:
        """Drop cached policy for a single role. Plugin override; OSS no-op."""

    async def invalidate_all(self) -> None:
        """Drop all cached policy. Plugin override; OSS no-op."""

    async def teardown(self) -> None:
        """No resources to release in the base implementation."""
