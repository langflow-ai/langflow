"""The adapter seam: what a Track B source has to implement, and nothing more.

An adapter is three methods - ``start``, ``stop``, ``healthy`` - plus a
transport word. The supervisor owns everything an adapter must not have to think
about: which replica holds the connection, when to back off, when to give up,
and how an event becomes a run. That split is what lets TRG-5 add Slack Socket
Mode and TRG-6 add Graph delta polling without touching supervision again.

Two transports, one protocol:

``socket``
    The adapter owns a long-lived connection and decides its own cadence.
    ``start`` returns only when the supervisor cancels it or the connection
    fails; a failure is raised, not swallowed, because the supervisor's backoff
    is the retry policy.
``poll``
    The adapter implements :meth:`PollingListenerAdapter.poll` and the generic
    loop in this module calls it on an interval with jitter. TRG-3 ships that
    loop so a pull source is a single method.

Adapters never execute flows and never acknowledge a provider before the ledger
row is committed: they call :meth:`ListenerContext.emit`, which commits, and
only then may the adapter tell the provider it is done with the message.
"""

from __future__ import annotations

import abc
import asyncio
import contextlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, runtime_checkable

from lfx.log.logger import logger

from langflow.services.triggers.constants import (
    LISTENER_FAKE_DEDUPE_PREFIX,
    LISTENER_FAKE_KIND,
    LISTENER_FAKE_MECHANISM,
    TRANSPORT_POLL,
    TRANSPORT_SOCKET,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID


@dataclass(frozen=True)
class ListenerTrigger:
    """An immutable snapshot of one trigger row, as an adapter sees it.

    A snapshot rather than the ORM row on purpose: the adapter runs for minutes
    or hours between reconciles, and a detached row that silently refreshes
    under it would make "which configuration is this connection running?"
    unanswerable.
    """

    id: UUID
    flow_id: UUID
    user_id: UUID
    kind: str
    provider: str | None
    mechanism_id: str | None
    config: dict[str, Any] = field(default_factory=dict)
    provider_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class ListenerContext:
    """Everything an adapter is allowed to touch.

    ``triggers`` is every trigger the connection feeds: one Slack connection can
    back several triggers on several flows, and one socket serves all of them.
    Fanning out from one connection is the supervisor's job, so an adapter reads
    the list and emits per trigger rather than opening a connection per trigger.
    """

    connection_id: UUID
    triggers: list[ListenerTrigger]
    emit: Callable[..., Awaitable[bool]]
    save_cursor: Callable[..., Awaitable[None]]
    resolve_credential: Callable[..., Awaitable[Any]]
    stopping: asyncio.Event


@runtime_checkable
class ListenerAdapter(Protocol):
    """A source that Langflow dials out to."""

    transport: str

    async def start(self, ctx: ListenerContext) -> None:
        """Hold the connection until cancelled. Raise to trigger backoff."""

    async def stop(self) -> None:
        """Release provider resources. Must be safe to call more than once."""

    def healthy(self) -> bool:
        """False while the adapter is connected but not usable."""


class PollingListenerAdapter(abc.ABC):
    """Base class for pull sources: implement :meth:`poll` and nothing else.

    The loop applies jitter to every sleep. Without it, a hundred triggers armed
    by one import all poll on the same second forever, which turns a provider's
    per-user rate limit into an outage on the minute.
    """

    transport = TRANSPORT_POLL

    def __init__(self, *, interval_s: float) -> None:
        self.interval_s = interval_s
        self._healthy = True

    @abc.abstractmethod
    async def poll(self, ctx: ListenerContext) -> int:
        """One pass. Returns how many ledger rows it appended."""

    async def start(self, ctx: ListenerContext) -> None:
        while not ctx.stopping.is_set():
            appended = await self.poll(ctx)
            if appended:
                await logger.adebug("Listener connection %s appended %s event(s)", ctx.connection_id, appended)
            delay = self.interval_s * random.uniform(0.85, 1.15)  # noqa: S311 - jitter, not crypto
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(ctx.stopping.wait(), timeout=delay)

    async def stop(self) -> None:
        return

    def healthy(self) -> bool:
        return self._healthy


class SelfTestAdapter(PollingListenerAdapter):
    """The one adapter TRG-3 ships: it proves the process, not a provider.

    It exists so every packaging shape can be verified end to end - process
    boots, lease is taken, adapter runs, ledger row appears, SIGTERM stops it
    cleanly - before any provider credential is in play. TRG-5 and TRG-6 replace
    it as the first real sources; it stays as the operator's smoke test.

    The dedupe key is the interval bucket, never ``now``: a restart inside the
    same bucket re-emits the same key and the ledger's unique index collapses
    it, which is the at-least-once contract demonstrated in one adapter.
    """

    def __init__(self, *, interval_s: float) -> None:
        super().__init__(interval_s=interval_s)

    async def poll(self, ctx: ListenerContext) -> int:
        bucket = int(datetime.now(timezone.utc).timestamp() // max(self.interval_s, 1.0))
        appended = 0
        for trigger in ctx.triggers:
            created = await ctx.emit(
                trigger_id=trigger.id,
                dedupe_key=f"{LISTENER_FAKE_DEDUPE_PREFIX}:{bucket}",
                payload={
                    "source": LISTENER_FAKE_MECHANISM,
                    "connection_id": str(ctx.connection_id),
                    "bucket": bucket,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            appended += int(created)
        return appended


#: What a bundle hands :func:`register_adapter`: given one trigger snapshot,
#: build the adapter that will hold its connection.
AdapterFactory: TypeAlias = "Callable[[ListenerTrigger], ListenerAdapter]"

#: ``(kind, mechanism_id)`` -> factory. ``mechanism_id`` of ``None`` is the
#: wildcard for a kind that has exactly one transport.
_REGISTRY: dict[tuple[str, str | None], AdapterFactory] = {}


def register_adapter(*, kind: str, mechanism: str | None, factory: AdapterFactory) -> None:
    """Register an adapter factory for a trigger kind (and optional mechanism).

    Registration is by ``(kind, mechanism_id)`` because a provider trigger names
    its transport in ``config.mechanism_id`` (``trigger-contract.md`` section 1):
    one Slack ``message`` kind is the Events API on hosted and Socket Mode on a
    firewalled instance, and only the mechanism tells them apart.
    """
    key = (kind, mechanism)
    if key in _REGISTRY:
        msg = f"A listener adapter is already registered for {key!r}."
        raise ValueError(msg)
    _REGISTRY[key] = factory


def unregister_adapter(*, kind: str, mechanism: str | None) -> None:
    """Remove a registration. Used by tests; harmless when absent."""
    _REGISTRY.pop((kind, mechanism), None)


def registered_adapter_keys() -> set[tuple[str, str | None]]:
    return set(_REGISTRY)


def build_adapter(trigger: ListenerTrigger) -> ListenerAdapter | None:
    """The adapter this trigger needs, or None when it is not a Track B source.

    Returning None rather than raising is deliberate: a schedule trigger and a
    TRG-4 push trigger both live in the same table, and the listener must walk
    past them silently rather than logging an error once every reconcile.
    """
    factory = _REGISTRY.get((trigger.kind, trigger.mechanism_id)) or _REGISTRY.get((trigger.kind, None))
    if factory is None:
        return None
    return factory(trigger)


def is_listener_kind(trigger: ListenerTrigger) -> bool:
    """True when some registered adapter claims this trigger."""
    return (trigger.kind, trigger.mechanism_id) in _REGISTRY or (trigger.kind, None) in _REGISTRY


def _selftest_factory(trigger: ListenerTrigger) -> ListenerAdapter:
    from langflow.services.deps import get_settings_service

    default = get_settings_service().settings.listener_poll_interval_s
    configured = (trigger.config or {}).get("interval_s", default)
    try:
        interval = float(configured)
    except (TypeError, ValueError):
        interval = default
    return SelfTestAdapter(interval_s=max(interval, 1.0))


def register_builtin_adapters() -> None:
    """Register the adapters langflow-base owns. Idempotent."""
    if (LISTENER_FAKE_KIND, None) in _REGISTRY:
        return
    register_adapter(kind=LISTENER_FAKE_KIND, mechanism=None, factory=_selftest_factory)


__all__ = [
    "TRANSPORT_POLL",
    "TRANSPORT_SOCKET",
    "AdapterFactory",
    "ListenerAdapter",
    "ListenerContext",
    "ListenerTrigger",
    "PollingListenerAdapter",
    "SelfTestAdapter",
    "build_adapter",
    "is_listener_kind",
    "register_adapter",
    "register_builtin_adapters",
    "registered_adapter_keys",
    "unregister_adapter",
]
