"""Deployment policy consulted before a new API key is issued.

An API key is a durable bearer credential: whoever holds it authenticates as
its owner until it is revoked. A deployment whose sign-in policy has closed an
account out -- SSO-only with no linked identity, say -- must not let that
account mint one, or the key quietly replaces the credential the policy just
took away.

Langflow has no such policy of its own. This is the seam a distribution plugs
one into, and :func:`check_api_key_issuance` is called from the single function
that creates keys, so every route that mints one is covered -- including the
MCP ones that mint implicitly, where the caller never asked for a key and never
sees that one was created.

A policy refuses by raising :class:`ApiKeyIssuanceDeniedError`. It is a
``PermissionError`` so that callers already mapping that to HTTP 403 keep
working unchanged, and a distinct type so that the MCP helpers, which
deliberately swallow registration failures, can let a refusal through instead
of reporting success for a credential they were not allowed to create.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


class ApiKeyIssuanceDeniedError(PermissionError):
    """The deployment's policy refuses to issue an API key to this account."""


class ApiKeyIssuancePolicy(Protocol):
    """Raise :class:`ApiKeyIssuanceDeniedError` to refuse; return to allow."""

    async def __call__(self, session: AsyncSession, user_id: UUID) -> None: ...


_policy: ApiKeyIssuancePolicy | None = None


def set_api_key_issuance_policy(policy: ApiKeyIssuancePolicy | None) -> None:
    """Install the deployment's policy, or ``None`` to remove it."""
    global _policy  # noqa: PLW0603 - one process-wide deployment policy, set at startup
    _policy = policy


def get_api_key_issuance_policy() -> ApiKeyIssuancePolicy | None:
    """Return the installed policy, if any."""
    return _policy


async def check_api_key_issuance(session: AsyncSession, user_id: UUID) -> None:
    """Ask the installed policy whether *user_id* may be issued a key now.

    No policy installed means no restriction, which is stock Langflow. The
    check runs before anything is staged on ``session``, so a refusal leaves
    the caller's transaction exactly as it found it.
    """
    if _policy is None:
        return
    await _policy(session, user_id)
