"""Replacement hook registry: an extension point inside ``PUT /projects/{id}/replacement-operations/{op}``.

A downstream plugin registers async callables that take part in a project replacement (a deploy). Nothing is
registered by default and stock behaviour is unchanged.

Two phases, two registries:

* **In-transaction hooks** (:func:`register_replacement_hook`) run after the flows are written and before the
  receipt is added and the transaction commits. They get the live session, so rows they add commit or roll back with
  the project, the flows and the receipt. They may add rows and flush; they must not commit or roll back. An
  ``HTTPException`` is propagated as is and rolls everything back, receipt included. Any other exception also rolls
  everything back and answers 500 ``replacement_hook_failed``: unlike ``creation_hooks`` these hooks **fail closed**,
  because a hook that guards a deploy must never be skipped silently. A database error (deadlock, lock timeout)
  propagates unchanged so the route's whole-transaction retry still works.
* **Committed hooks** (:func:`register_replacement_committed_hook`) run after the commit, with no session, for work
  that cannot run inside the transaction (for example a policy reload that opens its own session). They also run when
  a retry **replays a stored receipt** (``replayed=True``), so work a failed first attempt missed is done on the
  retry. A committed hook must therefore be safe to repeat. An ``HTTPException`` propagates as is; any other
  exception answers 500 ``replacement_committed_hook_failed``. The replacement is already durable either way, and the
  caller's retry replays the receipt and runs the hooks again.

Only the body field ``execution_principal_id`` of the request is generic: the route validates nothing about it and a
plugin that registers no hook ignores it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from lfx.log.logger import logger
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.api.v1.schemas.replacement_operations import ProjectReplacementRequest
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.user.model import User

ERROR_CODE_HEADER = "X-Langflow-Error-Code"
HOOK_FAILED_CODE = "replacement_hook_failed"
COMMITTED_HOOK_FAILED_CODE = "replacement_committed_hook_failed"


@dataclass(frozen=True)
class ReplacementContext:
    """What an in-transaction hook is told. ``session`` is the replacement transaction.

    ``request`` is the body as received (before the route fills in folder and workspace ids). ``flows_before`` and
    ``flows_after`` map flow id to name for the project's flows before and after this replacement.
    """

    session: AsyncSession
    current_user: User
    project: Folder
    created: bool
    request: ProjectReplacementRequest
    flows_before: Mapping[UUID, str]
    flows_after: Mapping[UUID, str]


@dataclass(frozen=True)
class ReplacementCommittedContext:
    """What a committed hook is told. ``flows_before`` is ``None`` when ``replayed``: a receipt keeps no before."""

    current_user: User
    project_id: UUID
    project_user_id: UUID
    operation_id: UUID
    request: ProjectReplacementRequest
    flows_before: Mapping[UUID, str] | None
    flows_after: Mapping[UUID, str]
    replayed: bool


ReplacementHook = Callable[[ReplacementContext], Awaitable[None]]
ReplacementCommittedHook = Callable[[ReplacementCommittedContext], Awaitable[None]]

_replacement_hooks: list[ReplacementHook] = []
_replacement_committed_hooks: list[ReplacementCommittedHook] = []


def register_replacement_hook(hook: ReplacementHook) -> bool:
    """Register an in-transaction hook; return False if it was already registered."""
    if hook in _replacement_hooks:
        return False
    _replacement_hooks.append(hook)
    return True


def register_replacement_committed_hook(hook: ReplacementCommittedHook) -> bool:
    """Register a committed hook; return False if it was already registered."""
    if hook in _replacement_committed_hooks:
        return False
    _replacement_committed_hooks.append(hook)
    return True


def registered_replacement_hooks() -> list[ReplacementHook]:
    """Return a copy of the registered in-transaction hooks."""
    return list(_replacement_hooks)


def registered_replacement_committed_hooks() -> list[ReplacementCommittedHook]:
    """Return a copy of the registered committed hooks."""
    return list(_replacement_committed_hooks)


def _hook_name(hook: Callable) -> str:
    return getattr(hook, "__name__", getattr(hook, "__qualname__", type(hook).__name__))


def _failed(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message,
        headers={ERROR_CODE_HEADER: code},
    )


async def run_replacement_hooks(context: ReplacementContext) -> None:
    """Await every in-transaction hook in registration order; see the module docstring for failure handling."""
    for hook in registered_replacement_hooks():
        try:
            await hook(context)
        except (HTTPException, DBAPIError):
            raise
        except Exception as exc:
            await logger.aexception(f"Replacement hook {_hook_name(hook)} failed; the replacement was refused")
            msg = "A replacement hook failed; nothing was changed."
            raise _failed(HOOK_FAILED_CODE, msg) from exc


async def run_replacement_committed_hooks(context: ReplacementCommittedContext) -> None:
    """Await every committed hook in registration order; see the module docstring for failure handling."""
    for hook in registered_replacement_committed_hooks():
        try:
            await hook(context)
        except HTTPException:
            raise
        except Exception as exc:
            await logger.aexception(
                f"Replacement committed hook {_hook_name(hook)} failed after the replacement was saved"
            )
            msg = "The replacement was saved but a follow-up step failed. Retry the same operation to complete it."
            raise _failed(COMMITTED_HOOK_FAILED_CODE, msg) from exc


__all__ = [
    "COMMITTED_HOOK_FAILED_CODE",
    "HOOK_FAILED_CODE",
    "ReplacementCommittedContext",
    "ReplacementCommittedHook",
    "ReplacementContext",
    "ReplacementHook",
    "register_replacement_committed_hook",
    "register_replacement_hook",
    "registered_replacement_committed_hooks",
    "registered_replacement_hooks",
    "run_replacement_committed_hooks",
    "run_replacement_hooks",
]
