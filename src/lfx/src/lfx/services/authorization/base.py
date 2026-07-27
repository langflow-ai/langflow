"""Abstract base class for authorization services."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict
from uuid import UUID as _UUID

from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
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
    provider_account_user_id: _UUID | None
    voice_user_id: _UUID | None
    workspace_id: _UUID | None
    folder_id: _UUID | None
    auth_method: str | None
    api_key_id: _UUID | None
    api_key_source: str | None
    external_provider: str | None


@dataclass(frozen=True, slots=True)
class ShareRuleSnapshot:
    """Framework-neutral share data needed to remove derived policy rules.

    Delete hooks run after the durable share row is gone, so plugins cannot
    reload it from the application database. This immutable value object keeps
    the hook independent of Langflow's ORM model while carrying every field a
    policy adapter needs to identify the rules that were derived from the row.
    """

    share_id: UUID
    resource_type: str
    resource_id: UUID
    scope: str
    target_id: UUID | None
    permission_level: str


class AuthorizationMutationKind(str, Enum):
    """Canonical policy-relevant lifecycle mutations emitted by Langflow."""

    USER_CREATED = "user.created"
    USER_DISABLED = "user.disabled"
    USER_SUPERUSER_DEMOTED = "user.superuser_demoted"
    USER_DELETED = "user.deleted"
    ROLE_CREATED = "role.created"
    ROLE_UPDATED = "role.updated"
    ROLE_DELETED = "role.deleted"
    ROLE_ASSIGNMENT_CREATED = "role_assignment.created"
    ROLE_ASSIGNMENT_DELETED = "role_assignment.deleted"
    TEAM_CREATED = "team.created"
    TEAM_UPDATED = "team.updated"
    TEAM_DELETED = "team.deleted"
    TEAM_MEMBER_ADDED = "team_member.added"
    TEAM_MEMBER_REMOVED = "team_member.removed"
    API_KEY_CREATED = "api_key.created"  # pragma: allowlist secret
    API_KEY_DELETED = "api_key.deleted"  # pragma: allowlist secret


class AuthorizationMutationRejected(Exception):  # noqa: N818 - public contract uses rejection terminology
    """Policy-safe rejection raised before a canonical identity mutation.

    ``public_detail`` is intentionally suitable for an API response. Plugins
    should keep provider, policy-engine, and subject internals in their audit
    trail rather than embedding them here.
    """

    def __init__(self, public_detail: str) -> None:
        super().__init__(public_detail)
        self.public_detail = public_detail


@dataclass(frozen=True, slots=True)
class UserAuthorizationSnapshot:
    """Minimal, non-secret user state needed by lifecycle guards."""

    is_active: bool
    is_superuser: bool


@dataclass(frozen=True, slots=True)
class AuthorizationMutation:
    """Immutable, ORM-free contract for canonical authorization mutations.

    ``stage_identity_mutation`` receives this value while the caller's database
    transaction is still open. Plugins can therefore compile derived policy or
    persist a durable retry marker atomically with the canonical row change.
    ``identity_mutation_committed`` receives the same value only after commit.

    IDs and field names are intentionally the only general-purpose payload.
    API-key material, identity-provider claims, and ORM objects must never be
    added to this contract.
    """

    kind: AuthorizationMutationKind
    entity_id: UUID
    actor_user_id: UUID | None = None
    affected_user_ids: tuple[UUID, ...] = ()
    role_id: UUID | None = None
    team_id: UUID | None = None
    domain_type: str | None = None
    domain_id: UUID | None = None
    policy_relevant_fields: tuple[str, ...] = ()
    user_before: UserAuthorizationSnapshot | None = None
    user_after: UserAuthorizationSnapshot | None = None
    previous_identifier: str | None = None


@dataclass(frozen=True, slots=True)
class DirectoryMembershipSnapshot:
    """Provider-neutral authoritative directory membership snapshot.

    ``memberships`` contains normalized, non-secret group identifiers, not raw
    identity-provider claims. Providers own paging, record/runtime bounds, and
    cursor persistence before presenting a complete snapshot here.
    """

    provider_id: str
    source: str
    observed_at: datetime
    user_id: UUID
    provider_user_id: str | None
    memberships: tuple[str, ...]
    authoritative: bool = True
    complete: bool = True


@dataclass(frozen=True, slots=True)
class ResourceVisibilityScope:
    """Compact SQL-prefilter contract for resource-list authorization.

    ``resource_ids`` represents concrete grants such as user/team shares.
    ``workspace_ids`` and ``project_ids`` represent wildcard role grants at
    those domains without expanding them to every resource UUID. A global
    wildcard is represented by ``all_resources``.
    """

    all_resources: bool = False
    resource_ids: tuple[UUID, ...] = ()
    workspace_ids: tuple[UUID, ...] = ()
    project_ids: tuple[UUID, ...] = ()

    @property
    def has_cross_user_access(self) -> bool:
        """Return whether the scope can widen an owner-only query."""
        return bool(self.all_resources or self.resource_ids or self.workspace_ids or self.project_ids)


class BaseAuthorizationService(Service, abc.ABC):
    """Abstract base class for authorization (RBAC) services."""

    name = ServiceType.AUTHORIZATION_SERVICE.value

    # True when the service can authorize non-owner access (share-aware fetch).
    SUPPORTS_CROSS_USER_FETCH: ClassVar[bool] = False
    # True when the service honors API-key credential context as a possible
    # restriction on top of the resolved user. When enabled, Langflow lets the
    # plugin evaluate owner-owned resources for API-key requests instead of
    # applying the built-in owner override first.
    SUPPORTS_API_KEY_SCOPES: ClassVar[bool] = False

    async def supports_cross_user_fetch(self) -> bool:
        """Return True when this service can authorize non-owner resource access."""
        return self.SUPPORTS_CROSS_USER_FETCH

    async def supports_api_key_scopes(self) -> bool:
        """Return True when API-key requests should be enforced even for owners."""
        return self.SUPPORTS_API_KEY_SCOPES

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

    async def get_resource_visibility(
        self,
        *,
        user_id: UUID,
        resource_type: str,
        domain: str = "*",
        act: str = "read",
        context: dict[str, Any] | None = None,
    ) -> ResourceVisibilityScope | None:
        """Return a compact visibility scope, or ``None`` to decline SQL prefiltering.

        The default adapts the original concrete-ID hook so existing plugins
        remain source-compatible. Plugins with global or domain-wildcard grants
        should override this method and return ``all_resources`` or domain IDs
        instead of enumerating every resource row.
        """
        visible_ids = await self.list_visible_resource_ids(
            user_id=user_id,
            resource_type=resource_type,
            domain=domain,
            act=act,
            context=context,
        )
        if visible_ids is None:
            return None
        return ResourceVisibilityScope(resource_ids=tuple(visible_ids))

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

    async def sync_shares(self) -> None:
        """Refresh policy derived from authz_share rows. Plugin override; OSS no-op."""

    async def sync_share(self, share_id: UUID) -> None:
        """Refresh policy derived from one durable share row. Plugin override; OSS no-op."""
        _ = share_id

    async def remove_share_rules(self, snapshot: ShareRuleSnapshot) -> None:
        """Remove policy derived from a deleted share snapshot. Plugin override; OSS no-op."""
        _ = snapshot

    async def validate_identity_mutation(
        self,
        *,
        session: Any,
        mutation: AuthorizationMutation,
    ) -> None:
        """Validate an identity mutation before the canonical row is changed.

        Plugins may acquire a transaction-scoped lock and raise to protect a
        last-recoverable-administrator invariant. The default is a no-op so OSS
        and older plugins preserve their existing behavior.
        """
        _ = (session, mutation)

    async def stage_identity_mutation(
        self,
        *,
        session: Any,
        event: AuthorizationMutation,
    ) -> None:
        """Compile policy or persist retry state in the canonical transaction.

        The supplied session is the mutation caller's open transaction. Plugin
        implementations must not commit or roll it back.
        """
        _ = (session, event)

    async def identity_mutation_committed(self, event: AuthorizationMutation) -> None:
        """Adapt lifecycle events to the legacy cache-invalidation hooks.

        Plugins that implement this lifecycle hook own publication entirely.
        Plugins written against the earlier ``invalidate_*`` contract inherit
        this adapter, so moving route handlers to lifecycle events does not
        silently leave their authorization caches stale.
        """
        role_kinds = {
            AuthorizationMutationKind.ROLE_UPDATED,
            AuthorizationMutationKind.ROLE_DELETED,
        }
        user_kinds = {
            AuthorizationMutationKind.USER_CREATED,
            AuthorizationMutationKind.USER_DISABLED,
            AuthorizationMutationKind.USER_SUPERUSER_DEMOTED,
            AuthorizationMutationKind.USER_DELETED,
            AuthorizationMutationKind.ROLE_ASSIGNMENT_CREATED,
            AuthorizationMutationKind.ROLE_ASSIGNMENT_DELETED,
            AuthorizationMutationKind.TEAM_MEMBER_ADDED,
            AuthorizationMutationKind.TEAM_MEMBER_REMOVED,
            AuthorizationMutationKind.API_KEY_CREATED,
            AuthorizationMutationKind.API_KEY_DELETED,
        }

        if event.kind is AuthorizationMutationKind.ROLE_CREATED:
            await self.invalidate_all()
            return

        if event.kind in role_kinds:
            try:
                await self.invalidate_role(event.role_id or event.entity_id)
            except Exception:  # noqa: BLE001 - compatibility fallback must be broad
                await self.invalidate_all()
            return

        if event.kind is AuthorizationMutationKind.TEAM_DELETED or (
            event.kind is AuthorizationMutationKind.TEAM_UPDATED and event.policy_relevant_fields
        ):
            await self.invalidate_all()
            return

        if event.kind in user_kinds:
            affected_user_ids = event.affected_user_ids
            if not affected_user_ids and event.kind.value.startswith("user."):
                affected_user_ids = (event.entity_id,)
            if not affected_user_ids:
                await self.invalidate_all()
                return
            for user_id in dict.fromkeys(affected_user_ids):
                try:
                    await self.invalidate_user(user_id)
                except Exception:  # noqa: BLE001 - compatibility fallback must be broad
                    await self.invalidate_all()
                    return

    async def ingest_directory_membership_snapshot(
        self,
        *,
        session: Any,
        snapshot: DirectoryMembershipSnapshot,
    ) -> None:
        """Ingest one complete provider snapshot in the caller's transaction.

        The base implementation is intentionally inert. Directory polling and
        provider-specific pagination remain plugin responsibilities.
        """
        _ = (session, snapshot)

    async def teardown(self) -> None:
        """No resources to release in the base implementation."""
