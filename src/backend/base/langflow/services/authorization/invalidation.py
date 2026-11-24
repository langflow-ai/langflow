"""Post-commit cache-invalidation helpers for authz admin writes.

The admin routes commit a policy-relevant change to the DB *before* asking the
authorization plugin to drop its cached decisions. That ordering is intentional
(the DB row is the source of truth and must land first) but it leaves a window
where the plugin's invalidation call could fail — leaving a stale cache while
the API returns 5xx, so the caller can't even tell the mutation took effect.

These helpers bound that window:

* ``safe_invalidate_user`` / ``safe_invalidate_role`` try the targeted call
  first. On failure they fall back to ``invalidate_all`` — broader hammer,
  same correctness floor — and log the original error.
* ``safe_invalidate_all`` does the same with a single best-effort attempt.

None of them raise: the DB write is already durable, and surfacing a plugin
RPC failure as an API failure would only encourage the caller to retry,
making the bad situation worse. Plugins that detect a stale cache during a
later ``enforce()`` should fail closed; these helpers are the proactive path.

Tests should patch ``invalidate_user`` / ``invalidate_role`` to raise and
assert that (a) the helper does not propagate, and (b) ``invalidate_all`` was
attempted. See ``test_authz_admin_routes.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.authorization.base import BaseAuthorizationService


async def safe_invalidate_user(
    svc: BaseAuthorizationService,
    user_id: UUID,
    *,
    op: str,
) -> None:
    """Drop cached policy for ``user_id``; fall back to ``invalidate_all`` on failure.

    ``op`` is a short string ("role_assignment:create", "team_member:delete", …)
    used only in log lines so an operator chasing a stale-cache report can
    identify which admin write triggered the fallback.
    """
    try:
        await svc.invalidate_user(user_id)
    except Exception as exc:  # noqa: BLE001 — plugin contract is best-effort
        logger.warning(
            "invalidate_user failed after %s for user=%s; falling back to invalidate_all: %s",
            op,
            user_id,
            exc,
        )
    else:
        return
    try:
        await svc.invalidate_all()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "invalidate_all fallback failed after %s for user=%s; cache may be stale: %s",
            op,
            user_id,
            exc,
        )


async def safe_invalidate_role(
    svc: BaseAuthorizationService,
    role_id: UUID,
    *,
    op: str,
) -> None:
    """Drop cached policy for ``role_id``; fall back to ``invalidate_all`` on failure."""
    try:
        await svc.invalidate_role(role_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "invalidate_role failed after %s for role=%s; falling back to invalidate_all: %s",
            op,
            role_id,
            exc,
        )
    else:
        return
    try:
        await svc.invalidate_all()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "invalidate_all fallback failed after %s for role=%s; cache may be stale: %s",
            op,
            role_id,
            exc,
        )


async def safe_invalidate_all(
    svc: BaseAuthorizationService,
    *,
    op: str,
) -> None:
    """Drop all cached policy; log on failure but never raise."""
    try:
        await svc.invalidate_all()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "invalidate_all failed after %s; cache may be stale: %s",
            op,
            exc,
        )


__all__ = ["safe_invalidate_all", "safe_invalidate_role", "safe_invalidate_user"]
