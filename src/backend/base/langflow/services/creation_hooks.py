"""Pre-creation hook registry — a stable enterprise extension point.

Enterprise (or any downstream) plugins register async callables that run
*before* OSS creates a project, a user or a role, and may veto the creation.
OSS knows nothing about *why* a hook denies: it only knows how to run the
hooks and how to turn a :class:`PreCreationDenied` into an HTTP response.

Usage from a plugin's ``register()``::

    from langflow.services.creation_hooks import (
        PreCreationContext,
        PreCreationDenied,
        RESOURCE_PROJECT,
        register_pre_creation_hook,
    )

    async def limit_projects(context: PreCreationContext) -> None:
        if await _over_limit(context.session):
            raise PreCreationDenied(
                "Your plan allows 3 projects.",
                details={"resource": "projects", "limit": 3, "current": 3, "tier": "trial"},
            )

    register_pre_creation_hook(RESOURCE_PROJECT, limit_projects)

Contract
--------
* Hooks are awaited in registration order, inside the caller's request
  transaction, **before** the row is added to the session. A hook may read
  ``context.session`` to count existing rows in that same transaction.
* Raising :class:`PreCreationDenied` is the ONLY authoritative way to stop a
  creation. It short-circuits the remaining hooks and the caller maps it to
  HTTP 403 through :func:`pre_creation_denied_to_http`.
* Any other exception **fails open**: it is logged at WARNING and creation
  proceeds. A broken plugin must not take user/project/role creation down.
  (Same posture as the enterprise lifespan hooks in ``langflow.main``.)
* :class:`PreCreationDenied` is deliberately NOT an
  ``AuthorizationMutationRejected``: that exception has an app-wide 409
  handler in the enterprise plugin, and a limit denial is a 403 with a
  structured body.

Call points (OSS)
-----------------
* ``project``  — ``langflow.api.v1.projects._new_project`` (``POST /projects/``
  and the create branch of ``PUT /projects/{project_id}``) and
  ``langflow.api.v1.projects_files.upload_project_flows``
  (``POST /projects/upload/``), all through :func:`enforce_pre_creation`.
  The per-user default/assistant folders and the null-owner starter project
  are created outside the API (``langflow.initial_setup.setup``) and are
  deliberately NOT hooked, so a limit implementation must exclude them from
  whatever it counts.
* ``user``     — ``langflow.api.v1.users.add_user`` (admin "add user" AND
  public signup; ``context.is_public_signup`` distinguishes them).
* ``role``     — ``langflow.api.v1.authz_roles.create_role`` (custom,
  ``is_system=False`` roles only; system roles are seeded by plugins).

For ``user`` and ``role`` the hook runs *after* ``acquire_identity_mutation_lock``,
so a count-then-insert is serialized by whatever lock the authorization plugin
takes. That lock is a no-op on non-PostgreSQL backends, and project creation
takes no lock at all, so concurrent creates can exceed a limit by one there.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from lfx.log.logger import logger

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

# Resource keys the registry accepts. Kept as plain strings so plugins can
# register without importing an enum.
RESOURCE_PROJECT = "project"
RESOURCE_USER = "user"
RESOURCE_ROLE = "role"

RESOURCES: tuple[str, ...] = (RESOURCE_PROJECT, RESOURCE_USER, RESOURCE_ROLE)

# The two error codes the denial contract defines. OSS never decides which one
# applies — the denying hook does — but they are named here so both planes
# spell them identically.
ERROR_CODE_TIER_LIMIT_REACHED = "tier_limit_reached"
ERROR_CODE_FEATURE_NOT_IN_TIER = "feature_not_in_tier"

# Response header carrying the machine-readable code, matching the convention
# already used by users.py (``superuser_required``, ``access_ceiling``) and
# read by the admin CLI client.
ERROR_CODE_HEADER = "X-Langflow-Error-Code"

DENIED_STATUS_CODE = 403


@dataclass(frozen=True)
class PreCreationContext:
    """Everything a hook is given about a creation that has not happened yet.

    ``session`` is the caller's live request session: a hook may run queries on
    it (e.g. count existing rows) but must not commit, roll back or add rows.
    """

    resource: str
    session: AsyncSession | None = None
    actor_user_id: UUID | None = None
    workspace_id: UUID | None = None
    requested_name: str | None = None
    is_public_signup: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)


class PreCreationDenied(Exception):  # noqa: N818
    """A hook refused a creation.

    ``message`` is the human-readable sentence shown to the caller.
    ``details`` carries the machine-readable fields of the denial contract
    (``resource``/``limit``/``current``/``tier`` for a numeric limit,
    ``feature``/``required_tiers``/``tier`` for a capability gate). OSS passes
    them through untouched: it does not know what a tier is.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = ERROR_CODE_TIER_LIMIT_REACHED,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or ERROR_CODE_TIER_LIMIT_REACHED
        self.details: dict[str, Any] = dict(details or {})

    def to_detail(self) -> dict[str, Any]:
        """Build the response ``detail`` body for this denial.

        ``error_code`` and ``message`` are authoritative and cannot be
        overwritten by ``details``.
        """
        return {**self.details, "error_code": self.error_code, "message": self.message}


PreCreationHook = Callable[[PreCreationContext], Awaitable[None]]

# Module-level registry. Plugins append at registration time (``register()``
# runs while the app is being built, before any request is served), mirroring
# ``langflow.main._enterprise_lifespan_hooks`` and
# ``langflow.api.health_check_router._enterprise_readiness_checks``.
_pre_creation_hooks: dict[str, list[PreCreationHook]] = {resource: [] for resource in RESOURCES}


def register_pre_creation_hook(resource: str, hook: PreCreationHook) -> bool:
    """Register ``hook`` for ``resource``; return False if it was already registered.

    Raises ``ValueError`` for an unknown resource so a typo in a plugin fails
    loudly at registration instead of silently never running.
    """
    if resource not in _pre_creation_hooks:
        msg = f"Unknown pre-creation resource {resource!r}; expected one of {', '.join(RESOURCES)}"
        raise ValueError(msg)
    hooks = _pre_creation_hooks[resource]
    if hook in hooks:
        return False
    hooks.append(hook)
    return True


def registered_pre_creation_hooks(resource: str) -> list[PreCreationHook]:
    """Return a copy of the hooks registered for ``resource`` (empty if unknown)."""
    return list(_pre_creation_hooks.get(resource, []))


def _hook_name(hook: PreCreationHook) -> str:
    return getattr(hook, "__name__", getattr(hook, "__qualname__", type(hook).__name__))


async def run_pre_creation_hooks(context: PreCreationContext) -> None:
    """Run every hook registered for ``context.resource``.

    Re-raises the first :class:`PreCreationDenied`. Any other exception is
    logged and swallowed (fail open) so a broken plugin cannot block creation.
    """
    for hook in list(_pre_creation_hooks.get(context.resource, [])):
        try:
            await hook(context)
        except PreCreationDenied:
            raise
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(
                f"Pre-creation hook {_hook_name(hook)} for {context.resource!r} failed "
                f"and was ignored (creation allowed): {exc}"
            )


def pre_creation_denied_to_http(exc: PreCreationDenied) -> HTTPException:
    """Map a denial onto the single OSS wire shape: 403 + code header + structured detail."""
    return HTTPException(
        status_code=DENIED_STATUS_CODE,
        detail=exc.to_detail(),
        headers={ERROR_CODE_HEADER: exc.error_code},
    )


async def enforce_pre_creation(context: PreCreationContext) -> None:
    """Run the hooks and raise the mapped ``HTTPException`` on denial.

    The one helper every call point that has nothing extra to do (project
    creation) uses. Call points that must also write an audit row catch
    :class:`PreCreationDenied` themselves and call
    :func:`pre_creation_denied_to_http`.
    """
    try:
        await run_pre_creation_hooks(context)
    except PreCreationDenied as exc:
        raise pre_creation_denied_to_http(exc) from exc


__all__ = [
    "DENIED_STATUS_CODE",
    "ERROR_CODE_FEATURE_NOT_IN_TIER",
    "ERROR_CODE_HEADER",
    "ERROR_CODE_TIER_LIMIT_REACHED",
    "RESOURCES",
    "RESOURCE_PROJECT",
    "RESOURCE_ROLE",
    "RESOURCE_USER",
    "PreCreationContext",
    "PreCreationDenied",
    "PreCreationHook",
    "enforce_pre_creation",
    "pre_creation_denied_to_http",
    "register_pre_creation_hook",
    "registered_pre_creation_hooks",
    "run_pre_creation_hooks",
]
