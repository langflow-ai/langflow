"""Deletion hooks: a stable extension point for what must happen when a resource is deleted.

Mirrors :mod:`langflow.services.creation_hooks`. Enterprise (or any downstream) plugins register async callables that
run *before* OSS deletes a knowledge base, memory base, variable, file, project or flow, and may refuse the deletion,
and others that run *after* the deletion committed, to remove what belongs with the resource (a share, a policy rule,
a binding row). OSS knows nothing about *why* a hook refuses or what it cleans: with nothing registered both runners
are no-ops and every delete behaves exactly as before.

Two phases, two registries
--------------------------
* **Pre-deletion** hooks run before the row (or its storage) is touched, on the caller's session when the call point
  has one (``context.session``), so a hook reads the same transaction the delete runs in. Raising ``HTTPException``
  refuses the deletion and is propagated verbatim. Any *other* exception also stops the deletion (the hook is a
  guard, so it fails closed, unlike a pre-*creation* hook); the caller turns it into its usual 500.
* **Post-deletion** hooks run after the deletion committed, once per deleted resource, with no session (the row is
  gone, a hook opens its own). They cannot veto. An ``HTTPException`` raised by a hook propagates (the resource is
  gone but the request fails, which is the hook's way of saying "the clean-up failed, look at it"); any other
  exception is logged and ignored, like a post-creation hook.

``context.via`` says why the deletion happened: ``request`` (an API call asked for exactly this resource), ``cascade``
(it went with something else, for example a flow's memory bases) or ``erase`` (a data-subject erase of its owner). A
guard that protects a resource from being deleted *on purpose* looks at ``request`` only.

Call points (OSS)
-----------------
The hooks sit where every route and job funnels in, not in each route:

* ``knowledge_base``: ``api.utils.knowledge_base_service.delete_record`` (single and bulk routes, the memory base
  service, the flow cascade and the data-subject erase all end there) and the storage clean-up that removes a
  record whose storage deletion was already requested (``services.knowledge_base_storage.cleanup``).
* ``memory_base``: ``MemoryBaseService.delete`` and the flow cascade (``purge_flow_memory_bases``).
* ``variable``: the variable service's ``delete_variable`` and ``delete_variable_by_id``.
* ``file``: the v2 files routes that delete a tracked file (single, batch, delete-all).
* ``project``: ``DELETE /projects/{id}`` (``folders.py`` only redirects there).
* ``flow``: :func:`langflow.api.utils.flow_utils.cascade_delete_flow`.

A call point that deletes inside the caller's transaction (a flow, a variable) does not know when the caller commits,
so it calls :func:`run_post_deletion_after_commit`: the event is attached to the session and runs, in the
background, once that session commits; a rollback drops it. A call point that commits itself awaits
:func:`run_post_deletion_hooks` directly. Either way no caller has to remember anything.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from lfx.log.logger import logger
from sqlalchemy import event

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session, SessionTransaction
    from sqlmodel.ext.asyncio.session import AsyncSession

RESOURCE_KNOWLEDGE_BASE = "knowledge_base"
RESOURCE_MEMORY_BASE = "memory_base"
RESOURCE_VARIABLE = "variable"
RESOURCE_FILE = "file"
RESOURCE_PROJECT = "project"
RESOURCE_FLOW = "flow"

DELETION_RESOURCES: tuple[str, ...] = (
    RESOURCE_KNOWLEDGE_BASE,
    RESOURCE_MEMORY_BASE,
    RESOURCE_VARIABLE,
    RESOURCE_FILE,
    RESOURCE_PROJECT,
    RESOURCE_FLOW,
)

VIA_REQUEST = "request"
VIA_CASCADE = "cascade"
VIA_ERASE = "erase"


@dataclass(frozen=True)
class DeletionContext:
    """What a hook is told about a resource that is being (or was) deleted.

    ``session`` is set for a pre-deletion hook whose call point has a session, and is always ``None`` for a
    post-deletion hook. ``owner_id`` is ``None`` for an ownerless resource.
    """

    resource: str
    resource_id: UUID
    owner_id: UUID | None = None
    name: str | None = None
    via: str = VIA_REQUEST
    session: AsyncSession | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


DeletionHook = Callable[[DeletionContext], Awaitable[None]]

_pre_deletion_hooks: dict[str, list[DeletionHook]] = {resource: [] for resource in DELETION_RESOURCES}
_post_deletion_hooks: dict[str, list[DeletionHook]] = {resource: [] for resource in DELETION_RESOURCES}


def _register(registry: dict[str, list[DeletionHook]], phase: str, resource: str, hook: DeletionHook) -> bool:
    if resource not in registry:
        msg = f"Unknown {phase}-deletion resource {resource!r}; expected one of {', '.join(DELETION_RESOURCES)}"
        raise ValueError(msg)
    hooks = registry[resource]
    if hook in hooks:
        return False
    hooks.append(hook)
    return True


def register_pre_deletion_hook(resource: str, hook: DeletionHook) -> bool:
    """Register ``hook`` to run before ``resource`` is deleted; ``False`` if it was already registered.

    Raises ``ValueError`` for an unknown resource so a typo fails loudly at registration instead of never running.
    """
    return _register(_pre_deletion_hooks, "pre", resource, hook)


def register_post_deletion_hook(resource: str, hook: DeletionHook) -> bool:
    """Register ``hook`` to run after ``resource`` was deleted; ``False`` if it was already registered."""
    return _register(_post_deletion_hooks, "post", resource, hook)


def registered_pre_deletion_hooks(resource: str) -> list[DeletionHook]:
    """Return a copy of the pre-deletion hooks for ``resource`` (empty if unknown)."""
    return list(_pre_deletion_hooks.get(resource, []))


def registered_post_deletion_hooks(resource: str) -> list[DeletionHook]:
    """Return a copy of the post-deletion hooks for ``resource`` (empty if unknown)."""
    return list(_post_deletion_hooks.get(resource, []))


def _hook_name(hook: DeletionHook) -> str:
    return getattr(hook, "__name__", getattr(hook, "__qualname__", type(hook).__name__))


async def run_pre_deletion_hooks(context: DeletionContext) -> None:
    """Run every pre-deletion hook for ``context.resource``; the first refusal or failure stops the deletion."""
    for hook in list(_pre_deletion_hooks.get(context.resource, [])):
        await hook(context)


async def run_post_deletion_hooks(context: DeletionContext) -> None:
    """Run every post-deletion hook for ``context.resource``; see the module contract."""
    committed = replace(context, session=None)
    for hook in list(_post_deletion_hooks.get(context.resource, [])):
        try:
            await hook(committed)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(
                f"Post-deletion hook {_hook_name(hook)} for {context.resource!r} failed and was ignored: "
                f"{type(exc).__name__}"
            )


_PENDING_KEY = "langflow_post_deletion_pending"
_background_runs: set[asyncio.Task] = set()


def run_post_deletion_after_commit(session: AsyncSession, context: DeletionContext) -> None:
    """Run the post-deletion hooks for ``context`` once ``session`` commits; drop them if it rolls back.

    For a delete that rides in the caller's transaction. The hooks run as a background task right after the commit
    (the commit cannot await them), so their failures are logged, never raised: a hook that must report a failure
    does so through its own durable state, which is what a repair or sweep reads. Safe to call several times.
    Releasing a savepoint promotes its events to the parent transaction. Rolling a transaction back discards only
    the events in that transaction, including any savepoints it had released.
    """
    if not _post_deletion_hooks.get(context.resource):
        return
    sync_session = session.sync_session
    transaction = sync_session.get_nested_transaction() or sync_session.get_transaction()
    if transaction is None:
        transaction = sync_session.begin()
    pending: dict[SessionTransaction, list[DeletionContext]] | None = sync_session.info.get(_PENDING_KEY)
    if pending is None:
        pending = sync_session.info[_PENDING_KEY] = {}

        def _on_commit(committing_session: Session) -> None:
            committed = committing_session.get_nested_transaction() or committing_session.get_transaction()
            if committed is None:
                return
            events = pending.pop(committed, [])
            if not events:
                return
            if committed.parent is not None:
                pending.setdefault(committed.parent, []).extend(events)
                return
            loop = asyncio.get_running_loop()
            for event_context in events:
                task = loop.create_task(_run_logged(event_context))
                _background_runs.add(task)
                task.add_done_callback(_background_runs.discard)

        def _on_transaction_end(_session: Session, ended: SessionTransaction) -> None:
            # A commit moved its events already. This also covers implicit rollback on session close.
            pending.pop(ended, None)

        event.listen(sync_session, "after_commit", _on_commit)
        event.listen(sync_session, "after_transaction_end", _on_transaction_end)
    pending.setdefault(transaction, []).append(replace(context, session=None))


async def _run_logged(context: DeletionContext) -> None:
    try:
        await run_post_deletion_hooks(context)
    except Exception as exc:  # noqa: BLE001 - nobody is waiting for a background run
        await logger.awarning(f"Post-deletion hooks for {context.resource!r} {context.resource_id} failed: {exc!r}")


async def wait_for_post_deletion_runs() -> None:
    """Wait for the background runs started by :func:`run_post_deletion_after_commit` (shutdown, tests)."""
    while _background_runs:
        await asyncio.gather(*list(_background_runs), return_exceptions=True)


__all__ = [
    "DELETION_RESOURCES",
    "RESOURCE_FILE",
    "RESOURCE_FLOW",
    "RESOURCE_KNOWLEDGE_BASE",
    "RESOURCE_MEMORY_BASE",
    "RESOURCE_PROJECT",
    "RESOURCE_VARIABLE",
    "VIA_CASCADE",
    "VIA_ERASE",
    "VIA_REQUEST",
    "DeletionContext",
    "DeletionHook",
    "register_post_deletion_hook",
    "register_pre_deletion_hook",
    "registered_post_deletion_hooks",
    "registered_pre_deletion_hooks",
    "run_post_deletion_after_commit",
    "run_post_deletion_hooks",
    "run_pre_deletion_hooks",
    "wait_for_post_deletion_runs",
]
