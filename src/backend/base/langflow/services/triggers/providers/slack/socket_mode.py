"""Track B: Slack Socket Mode, held by the ``langflow listeners`` process.

Socket Mode is Slack's no-ingress transport. The listener dials out: it calls
``apps.connections.open`` with the app-level token (``xapp-``) to get a one-use
WebSocket URL, connects, and receives the same Events API bodies it would have
been POSTed, each inside an envelope it must acknowledge by echoing
``envelope_id``. This module is that client, written against the protocol
rather than wrapped around a library, because the three things that matter here
are exactly the ones a general client decides for you:

**Write before ack.** Every event is normalized, matched, and committed to the
ledger (``ctx.emit`` commits) *before* its envelope is acknowledged. A failure
between the two leaves the envelope unacknowledged, so Slack redelivers it and
the ledger's ``(trigger, event_id)`` key collapses the copy. Acknowledging first
is the one order that could lose an event.

**Bounded overlap.** Slack warns before it closes a socket (``disconnect`` with
``warning`` or ``refresh_requested``, roughly ten seconds ahead, not
guaranteed). The replacement is opened *before* the retiring socket is closed,
both feed one handler, and the retiring one is drained and closed - never more
than two sockets per connection, inside Slack's ten-per-app budget. Events that
arrive on either socket take the same write-then-ack path, so an event seen on
both is written once.

**Failures surface.** A rejected token is an :class:`AuthExpiredError`, which
the supervisor turns into ``needs_reconnect``; everything else is raised so the
supervisor's backoff is the retry policy. Nothing loops silently on a revoked
token.

**One app, many connections.** Slack spreads an app's events across *all* of
its open sockets. When several people on one instance each connect the same
Slack app, whichever socket receives an event writes it for every armed Socket
Mode trigger of that app - identified by the ``app_id`` Slack reports in each
socket's ``hello`` and recorded on the trigger - not just for the triggers on
the receiving connection. Without that, each person's triggers would silently
miss the share of events that landed on someone else's socket.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionUnresolvedError,
    ProviderUnavailableError,
    RateLimitedError,
)
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.triggers.constants import (
    MECHANISM_SLACK_SOCKET_MODE,
    PROVIDER_SLACK,
    SLACK_PROVIDER_STATE_APP_ID,
    SLACK_TRIGGER_KINDS,
    TRANSPORT_SOCKET,
)
from langflow.services.triggers.ownership import UNUSABLE_CONNECTION_STATUSES, owned_by_trigger_owner
from langflow.services.triggers.providers.slack.events import SlackControl, SlackEvent, normalize
from langflow.services.triggers.providers.slack.filters import matches

if TYPE_CHECKING:
    from collections.abc import Callable
    from urllib.parse import SplitResult
    from uuid import UUID

    from websockets.asyncio.client import ClientConnection

    from langflow.services.triggers.listeners.adapters import ListenerContext, ListenerTrigger

SLACK_API_BASE_URL = "https://slack.com/api"
APP_TOKEN_PREFIX = "xapp-"  # noqa: S105 - Slack's app-level token type prefix, not a credential

#: ``trigger.provider_state`` key recording which Slack app a trigger's
#: connection proved it belongs to, in that socket's ``hello``.
PROVIDER_STATE_APP_ID = SLACK_PROVIDER_STATE_APP_ID

#: ``apps.connections.open`` errors that mean the token itself is no good, so
#: only a human with a new token can fix it.
_TOKEN_ERRORS = frozenset(
    {
        "invalid_auth",
        "not_authed",
        "token_revoked",
        "token_expired",
        "account_inactive",
        "not_allowed_token_type",
    }
)
#: ``disconnect`` reasons that mean the app's Socket Mode is switched off.
_DISABLED_REASONS = frozenset({"link_disabled", "socket_mode_disabled"})
#: A socket plus its replacement during a refresh, never more.
_MAX_SOCKETS_PER_CONNECTION = 2
#: Socket Mode frames carry one event each; message bodies are well under this.
_MAX_FRAME_BYTES = 4 * 1024 * 1024
#: A socket that stayed open this long held, even if nothing was said on it: a
#: quiet workspace can keep a healthy socket silent for hours, and Slack does
#: not always warn before closing one.
_STABLE_SOCKET_S = 60.0


class SlackSocketModeError(RuntimeError):
    """A Socket Mode failure the supervisor should back off and retry."""


class SlackSocketModeDisabledError(SlackSocketModeError):
    """Socket Mode is switched off in the Slack app's configuration."""

    def __init__(self) -> None:
        super().__init__(
            "Slack reports that Socket Mode is turned off for this app. Turn it on under the app's "
            "Socket Mode settings; the trigger resumes on its own once it is."
        )


class SlackConnectionLimitError(SlackSocketModeError):
    """Opening another socket would take the app past its connection budget."""


class SlackSocketClosedError(SlackSocketModeError):
    """The socket closed unexpectedly and reconnecting straight away did not hold."""


def is_slack_socket_url(url: SplitResult) -> bool:
    """Only ever dial Slack: ``wss`` to a ``slack.com`` host.

    The URL comes from Slack's own API over TLS, but it is still a URL a remote
    service chose, and the listener process holds every connection's credentials.
    """
    host = (url.hostname or "").lower()
    return url.scheme == "wss" and (host == "slack.com" or host.endswith(".slack.com"))


@dataclass(frozen=True)
class _SameAppTrigger:
    """What fan-out needs from another connection's trigger, detached from the session."""

    id: UUID
    kind: str
    config: dict[str, Any]


@dataclass(eq=False)
class _Socket:
    """One open WebSocket and what this adapter knows about it."""

    ws: ClientConnection
    app_id: str | None
    #: Event-loop time the handshake completed, to tell a socket that held from
    #: one that dropped straight after opening.
    opened_at: float = 0.0
    reader: asyncio.Task | None = None
    retiring: bool = False
    productive: bool = False
    drain: asyncio.Task | None = field(default=None, repr=False)
    #: Reports the connection as working once this socket has held.
    settle: asyncio.Task | None = field(default=None, repr=False)

    def held(self, now: float) -> bool:
        """Carried traffic, or stayed open long enough that its close is routine."""
        return self.productive or now - self.opened_at >= _STABLE_SOCKET_S

    async def ack(self, envelope_id: str) -> None:
        await self.ws.send(json.dumps({"envelope_id": envelope_id}))

    async def close(self) -> None:
        if self.settle is not None and not self.settle.done():
            self.settle.cancel()
        with contextlib.suppress(Exception):
            await self.ws.close()


class SlackSocketModeAdapter:
    """Hold one Slack app-level-token connection in Socket Mode."""

    transport = TRANSPORT_SOCKET

    def __init__(
        self,
        *,
        max_connections: int = 10,
        api_base_url: str = SLACK_API_BASE_URL,
        http_transport: httpx.AsyncBaseTransport | None = None,
        url_allowed: Callable[[SplitResult], bool] = is_slack_socket_url,
        open_timeout_s: float = 10.0,
        drain_timeout_s: float = 10.0,
        same_app_ttl_s: float = 5.0,
    ) -> None:
        self._max_connections = max_connections
        self._api_base_url = api_base_url
        self._http_transport = http_transport
        self._url_allowed = url_allowed
        self._open_timeout_s = open_timeout_s
        self._drain_timeout_s = drain_timeout_s
        self._same_app_ttl_s = same_app_ttl_s
        #: ``(loaded_at, triggers)`` for :meth:`_same_app_triggers`. A busy
        #: workspace sends events far faster than triggers are armed, so the
        #: set is re-read at most once per reconcile interval rather than once
        #: per event on the path that must acknowledge within Slack's deadline.
        self._same_app_cache: tuple[float, list[_SameAppTrigger]] | None = None
        self._sockets: list[_Socket] = []
        self._refresh = asyncio.Event()
        #: Set by :meth:`stop`. ``_serve`` waits on it alongside ``ctx.stopping``
        #: and every place a socket would be opened checks it, so a ``stop()``
        #: that races a running ``start()`` ends it rather than being followed by
        #: a reconnect that re-opens what it just closed.
        self._halt = asyncio.Event()
        self._app_id: str | None = None
        #: Trigger id -> the snapshot ``_app_id`` was last written against. The
        #: supervisor re-reads every trigger each reconcile, so a *fresh*
        #: snapshot that still lacks the app id means it was cleared - the
        #: trigger moved to another connection and back - and is written again.
        self._recorded: dict[UUID, ListenerTrigger] = {}

    # ------------------------------------------------------------------ #
    # ListenerAdapter
    # ------------------------------------------------------------------ #

    def healthy(self) -> bool:
        return self._app_id is not None and any(not socket.retiring for socket in self._sockets)

    async def stop(self) -> None:
        self._halt.set()
        await self._close_all()

    @property
    def _stopped(self) -> bool:
        return self._halt.is_set()

    async def start(self, ctx: ListenerContext) -> None:
        token = await self._app_token(ctx)
        async with httpx.AsyncClient(
            base_url=self._api_base_url, transport=self._http_transport, timeout=self._open_timeout_s
        ) as http:
            try:
                await self._serve(ctx, http, token)
            finally:
                await self._close_all()

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #

    async def _app_token(self, ctx: ListenerContext) -> str:
        credential = await ctx.resolve_credential()
        token = credential.access_token.get_secret_value()
        if not token.startswith(APP_TOKEN_PREFIX):
            # A Socket Mode connection holds an app-level token by construction;
            # anything else was stored some other way and can never open a socket.
            handle = f"connection:{ctx.connection_id}"
            raise ConnectionUnresolvedError(handle, provider=PROVIDER_SLACK, reason="invalid-access-token")
        return token

    async def _serve(self, ctx: ListenerContext, http: httpx.AsyncClient, token: str) -> None:
        stopping = asyncio.create_task(ctx.stopping.wait())
        halted = asyncio.create_task(self._halt.wait())
        refresh = asyncio.create_task(self._refresh.wait())
        try:
            await self._add_socket(ctx, http, token)
            unexpected_closes = 0
            while not self._stopped:
                readers = {socket.reader for socket in self._sockets if socket.reader is not None}
                done, _ = await asyncio.wait({stopping, halted, refresh, *readers}, return_when=asyncio.FIRST_COMPLETED)
                if stopping in done or halted in done:
                    return
                if refresh in done:
                    self._refresh.clear()
                    refresh = asyncio.create_task(self._refresh.wait())
                    await self._replace_retiring(ctx, http, token)
                    continue
                for socket in [socket for socket in self._sockets if socket.reader in done]:
                    # Out of the list and closed before anything is raised, so a
                    # failing reader can never leave its socket open behind it.
                    self._sockets.remove(socket)
                    await socket.close()
                    if socket.reader is None or socket.reader.cancelled():
                        continue
                    error = socket.reader.exception()
                    if error is not None:
                        raise error
                    if socket.retiring:
                        continue
                    # A socket that held - carried traffic, or simply stayed up -
                    # and then dropped is a routine hiccup; one that drops again
                    # straight after opening is not.
                    held = socket.held(asyncio.get_running_loop().time())
                    unexpected_closes = 0 if held else unexpected_closes + 1
                if self._stopped:
                    return
                if not any(not socket.retiring for socket in self._sockets):
                    if unexpected_closes > 1:
                        msg = "The Slack socket closed again straight after reconnecting."
                        raise SlackSocketClosedError(msg)
                    await logger.ainfo("Slack socket on connection %s closed; reconnecting", ctx.connection_id)
                    await self._add_socket(ctx, http, token)
        finally:
            for waiter in (stopping, halted, refresh):
                waiter.cancel()

    async def _replace_retiring(self, ctx: ListenerContext, http: httpx.AsyncClient, token: str) -> None:
        """Open the replacement for a socket Slack is about to close, then drain the old one.

        A replacement is opened whenever no live (non-retiring) socket remains -
        including when a *second* warning retires the previous replacement while
        the first socket is still draining. Staying within two sockets then means
        cutting the oldest drain short to make room, never skipping the
        replacement: a connection must not be left with nothing but sockets
        Slack has said it is about to close.
        """
        retiring = [socket for socket in self._sockets if socket.retiring and socket.drain is None]
        if not retiring or self._stopped:
            return
        if not any(not socket.retiring for socket in self._sockets):
            while len(self._sockets) >= _MAX_SOCKETS_PER_CONNECTION:
                oldest = next((socket for socket in self._sockets if socket.drain is not None), None)
                if oldest is None:
                    break
                self._sockets.remove(oldest)
                await self._discard(oldest)
            await self._add_socket(ctx, http, token)
        for socket in retiring:
            socket.drain = asyncio.create_task(self._retire(socket))

    async def _retire(self, socket: _Socket) -> None:
        """Let a retiring socket deliver what is already in flight, then close it.

        A cancellation (``stop()``, lease loss) still propagates: only the drain
        timeout and the reader's own failure - which ``_serve`` reports - are
        absorbed here.
        """
        try:
            if socket.reader is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(asyncio.shield(socket.reader), timeout=self._drain_timeout_s)
        finally:
            await socket.close()

    async def _discard(self, socket: _Socket) -> None:
        """Stop a socket's tasks and close it, waiting for the tasks to end."""
        tasks = [task for task in (socket.reader, socket.drain, socket.settle) if task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        await socket.close()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def _add_socket(self, ctx: ListenerContext, http: httpx.AsyncClient, token: str) -> None:
        socket = await self._open(http, token)
        if self._stopped:
            # ``stop()`` ran while this socket was being opened.
            await socket.close()
            return
        self._app_id = socket.app_id or self._app_id
        socket.reader = asyncio.create_task(self._read(ctx, socket))
        self._sockets.append(socket)
        await self._record_app_id(ctx)
        if ctx.mark_connected is not None:
            socket.settle = asyncio.create_task(self._mark_connected_once_held(ctx, socket))

    async def _mark_connected_once_held(self, ctx: ListenerContext, socket: _Socket) -> None:
        """Report a working connection once ``socket`` has stayed up long enough to count.

        Not at ``hello``. Slack can accept a socket and drop it straight away, and
        reporting every hello as a success reset the supervisor's failure count on
        each attempt: a connection that never held retried at the base backoff
        forever and its owner never saw the banner. A socket that carries an
        event proves itself sooner, through ``emit``.
        """
        await asyncio.sleep(_STABLE_SOCKET_S)
        if self._stopped or socket not in self._sockets or ctx.mark_connected is None:
            return
        try:
            await ctx.mark_connected()
        except Exception:  # noqa: BLE001 - clearing a banner is best effort; the socket itself is fine
            await logger.awarning("Could not report connection %s as connected", ctx.connection_id, exc_info=True)

    async def _open(self, http: httpx.AsyncClient, token: str) -> _Socket:
        url = await self._issue_url(http, token)
        ws = await ws_connect(
            url,
            open_timeout=self._open_timeout_s,
            max_size=_MAX_FRAME_BYTES,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        )
        try:
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=self._open_timeout_s))
        except (TimeoutError, asyncio.TimeoutError, ValueError, ConnectionClosed) as exc:
            await ws.close()
            msg = "Slack opened a socket but never said hello."
            raise SlackSocketModeError(msg) from exc
        except BaseException:
            # Cancelled mid-handshake (a stop, a lost lease): the socket is open
            # and counts against the app's ten, so it must not outlive this.
            await ws.close()
            raise
        if not isinstance(hello, dict) or hello.get("type") != "hello":
            await ws.close()
            msg = "Slack's first Socket Mode frame was not a hello."
            raise SlackSocketModeError(msg)
        # Counted by Slack across every process holding this app, including this
        # socket - the only place the app-wide budget is visible to any one of them.
        count = hello.get("num_connections")
        if isinstance(count, int) and count > self._max_connections:
            await ws.close()
            msg = (
                f"The Slack app already holds {count - 1} Socket Mode connection(s); "
                f"opening another would pass the {self._max_connections}-connection budget."
            )
            raise SlackConnectionLimitError(msg)
        info = hello.get("connection_info") if isinstance(hello.get("connection_info"), dict) else {}
        app_id = info.get("app_id") if isinstance(info.get("app_id"), str) else None
        return _Socket(ws=ws, app_id=app_id, opened_at=asyncio.get_running_loop().time())

    async def _issue_url(self, http: httpx.AsyncClient, token: str) -> str:
        """Call ``apps.connections.open`` and return the one-use WebSocket URL."""
        try:
            response = await http.post("/apps.connections.open", headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(provider=PROVIDER_SLACK) from exc
        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            retry_after = _retry_after(response.headers.get("Retry-After"))
            raise RateLimitedError(provider=PROVIDER_SLACK, retry_after=retry_after)
        if response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
            raise ProviderUnavailableError(provider=PROVIDER_SLACK, http_status=response.status_code)
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderUnavailableError(provider=PROVIDER_SLACK, http_status=response.status_code) from exc
        if not isinstance(data, dict) or not data.get("ok"):
            error = data.get("error") if isinstance(data, dict) else None
            if error in _TOKEN_ERRORS:
                raise AuthExpiredError(provider=PROVIDER_SLACK, http_status=response.status_code)
            if error == "ratelimited":
                raise RateLimitedError(provider=PROVIDER_SLACK)
            msg = f"Slack refused to open a Socket Mode connection: {error or 'unknown error'}."
            raise SlackSocketModeError(msg)
        url = data.get("url")
        if not isinstance(url, str) or not self._url_allowed(urlsplit(url)):
            msg = "Slack returned a Socket Mode URL that is not a Slack WebSocket address."
            raise SlackSocketModeError(msg)
        return url

    async def _close_all(self) -> None:
        sockets, self._sockets = self._sockets, []
        for socket in sockets:
            await self._discard(socket)

    # ------------------------------------------------------------------ #
    # Frames
    # ------------------------------------------------------------------ #

    async def _read(self, ctx: ListenerContext, socket: _Socket) -> None:
        """Handle frames until the socket closes. Raises only what must stop the adapter."""
        try:
            async for raw in socket.ws:
                await self._on_frame(ctx, socket, raw)
        except ConnectionClosed:
            return

    async def _on_frame(self, ctx: ListenerContext, socket: _Socket, raw: str | bytes) -> None:
        try:
            frame = json.loads(raw)
        except ValueError:
            await logger.awarning("Ignoring a Socket Mode frame that is not JSON on connection %s", ctx.connection_id)
            return
        if not isinstance(frame, dict):
            return
        kind = frame.get("type")
        envelope_id = frame.get("envelope_id") if isinstance(frame.get("envelope_id"), str) else None
        if kind == "events_api":
            # Write first (``_on_event`` commits every ledger row), acknowledge
            # second. If the write raises, the envelope stays unacknowledged
            # and Slack redelivers it.
            await self._on_event(ctx, frame.get("payload"))
            socket.productive = True
            if envelope_id is not None:
                await socket.ack(envelope_id)
            return
        if kind == "disconnect":
            reason = frame.get("reason")
            if reason in _DISABLED_REASONS:
                raise SlackSocketModeDisabledError
            if reason == "too_many_websockets":
                msg = "Slack closed this socket because the app holds too many Socket Mode connections."
                raise SlackConnectionLimitError(msg)
            await logger.ainfo(
                "Slack asked connection %s to reconnect (%s); opening a replacement first", ctx.connection_id, reason
            )
            socket.retiring = True
            self._refresh.set()
            return
        # Anything else that expects an answer - an interaction or a slash
        # command the app was configured for - is acknowledged with no payload
        # so Slack does not retry it at a user. No trigger subscribes to them.
        if envelope_id is not None:
            await socket.ack(envelope_id)

    async def _on_event(self, ctx: ListenerContext, body: Any) -> None:
        event = normalize(body) if isinstance(body, dict) else None
        if isinstance(event, SlackControl) and event.kind == "app_rate_limited":
            await logger.awarning(
                "Slack is rate limiting events for workspace %s on connection %s", event.team_id, ctx.connection_id
            )
        if isinstance(event, SlackEvent):
            await self._record_app_id(ctx)
            for trigger_id in await self._targets(ctx, event):
                # Committed before the envelope is acknowledged (see module docstring).
                await self._emit(ctx, trigger_id, event)

    async def _emit(self, ctx: ListenerContext, trigger_id: UUID, event: SlackEvent) -> None:
        """Write one trigger's ledger row, skipping a trigger deleted since it was targeted.

        Targets come from the last reconcile and from a same-app read up to
        ``same_app_ttl_s`` old, so a trigger can be deleted in between - with the
        cross-connection fan-out, by another person deleting their own flow. Its
        ledger row then fails the foreign key (Postgres; SQLite does not enforce
        it). Raising would close every socket on this connection over one
        trigger that no longer exists, so only that trigger is skipped. Any other
        write failure still raises, and the envelope stays unacknowledged.
        """
        try:
            await ctx.emit(trigger_id=trigger_id, dedupe_key=event.dedupe_key, payload=event.payload)
        except IntegrityError:
            if await _trigger_exists(trigger_id):
                raise
            self._same_app_cache = None
            await logger.ainfo(
                "Slack event %s on connection %s skipped trigger %s: it was deleted",
                event.event_id,
                ctx.connection_id,
                trigger_id,
            )

    # ------------------------------------------------------------------ #
    # Targets
    # ------------------------------------------------------------------ #

    async def _targets(self, ctx: ListenerContext, event: SlackEvent) -> list[UUID]:
        own = {trigger.id for trigger in ctx.triggers}
        targets = [
            trigger.id
            for trigger in list(ctx.triggers)
            if trigger.mechanism_id == MECHANISM_SLACK_SOCKET_MODE and matches(trigger.kind, trigger.config, event)
        ]
        elsewhere = [
            row.id
            for row in await self._same_app_triggers(ctx)
            if row.id not in own and matches(row.kind, row.config, event)
        ]
        if elsewhere:
            # Provenance for an operator: this socket carried an event another
            # connection's triggers fire on. Both connections proved (by Slack's
            # hello) that they hold a token for the same app.
            await logger.adebug(
                "Slack event %s on connection %s also fires %s trigger(s) on other connections of app %s",
                event.event_id,
                ctx.connection_id,
                len(elsewhere),
                self._app_id,
            )
        return targets + elsewhere

    async def _same_app_triggers(self, ctx: ListenerContext) -> list[_SameAppTrigger]:
        """Armed Socket Mode triggers of this Slack app on *other* connections.

        Cached for ``same_app_ttl_s``. A trigger armed or paused on another
        connection is seen within that interval - the same bound the listener
        itself works to - and a paused one that still receives an event in the
        meantime is refused by the dispatcher, which re-reads the trigger's
        state before it runs anything.
        """
        if self._app_id is None:
            return []
        loop = asyncio.get_running_loop()
        if self._same_app_cache is not None and loop.time() - self._same_app_cache[0] < self._same_app_ttl_s:
            return self._same_app_cache[1]
        rows = await self._load_same_app_triggers(ctx)
        self._same_app_cache = (loop.time(), rows)
        return rows

    async def _load_same_app_triggers(self, ctx: ListenerContext) -> list[_SameAppTrigger]:
        from langflow.services.deps import session_scope

        mechanism = col(Trigger.config)["mechanism_id"].as_string()
        app_id = col(Trigger.provider_state)[PROVIDER_STATE_APP_ID].as_string()
        statement = (
            select(Trigger)
            .join(Connection, col(Connection.id) == col(Trigger.connection_id))
            .where(
                Trigger.state == TriggerState.ACTIVE.value,
                col(Trigger.kind).in_(SLACK_TRIGGER_KINDS),
                mechanism == MECHANISM_SLACK_SOCKET_MODE,
                app_id == self._app_id,
                col(Trigger.connection_id) != ctx.connection_id,
                owned_by_trigger_owner(),
                col(Connection.status).not_in(UNUSABLE_CONNECTION_STATUSES),
            )
            .order_by(col(Trigger.id))
        )
        async with session_scope() as session:
            return [
                _SameAppTrigger(id=row.id, kind=row.kind, config=dict(row.config or {}))
                for row in (await session.exec(statement)).all()
            ]

    async def _record_app_id(self, ctx: ListenerContext) -> None:
        """Record on this connection's triggers which app its socket proved it is.

        That is what lets *another* connection's socket find them when Slack
        routes this app's events there. Only written when it changes.
        """
        if self._app_id is None:
            return
        for trigger in list(ctx.triggers):
            if (trigger.provider_state or {}).get(PROVIDER_STATE_APP_ID) == self._app_id:
                continue
            if self._recorded.get(trigger.id) is trigger:
                continue
            await ctx.save_cursor(
                trigger_id=trigger.id,
                provider_state={**(trigger.provider_state or {}), PROVIDER_STATE_APP_ID: self._app_id},
            )
            self._recorded[trigger.id] = trigger


async def _trigger_exists(trigger_id: UUID) -> bool:
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        return await session.get(Trigger, trigger_id) is not None


def _retry_after(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
