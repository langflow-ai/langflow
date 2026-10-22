"""A fenced Discord Gateway client supervised by the listener process."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import time
from urllib.parse import urlsplit

from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ProviderUnavailableError,
    RateLimitedError,
)
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_discord._client import DiscordClient, redact
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from langflow.services.triggers.providers.discord.events import normalize

# Gateway frames contain bot credentials and private message content.
# Keep this logger private and detached from application logging settings.
_WEBSOCKET_LOGGER = logging.Logger("langflow.discord.gateway.transport", level=logging.CRITICAL + 1)  # noqa: LOG001
_WEBSOCKET_LOGGER.addHandler(logging.NullHandler())
_WEBSOCKET_LOGGER.propagate = False

OP_HELLO = 10
OP_HEARTBEAT_ACK = 11
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
AUTH_FAILED = 4004
MIN_HEARTBEAT_MS = 1000
MAX_HEARTBEAT_MS = 120000
MAX_SESSION_LENGTH = 256
STABLE_CONNECTION_SECONDS = 60


def gateway_url(value: str) -> str:
    if not isinstance(value, str):
        raise ProviderUnavailableError(provider="discord")
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "wss"
        or not (host == "gateway.discord.gg" or host.endswith(".gateway.discord.gg"))
        or parsed.port is not None
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ProviderUnavailableError(provider="discord")
    return f"wss://{host}/?v=10&encoding=json"


class DiscordGatewayAdapter:
    transport = "socket"

    def __init__(self, trigger):
        self.state = dict(trigger.provider_state or {})
        self.ws = None
        self.halt = asyncio.Event()
        self.connected = False
        self.acked = True

    def healthy(self) -> bool:
        return self.connected

    async def stop(self) -> None:
        self.halt.set()
        self.connected = False
        if self.ws is not None:
            await self.ws.close(code=4000)

    async def _save(self, ctx, trigger):
        await ctx.save_cursor(trigger_id=trigger.id, provider_state=dict(self.state))

    async def _heartbeat(self, interval: float):
        await asyncio.sleep(interval * random.random())  # noqa: S311 - protocol heartbeat jitter
        while True:
            if not self.acked:
                await self.ws.close(code=4000)
                raise ProviderUnavailableError(provider="discord")
            self.acked = False
            await self.ws.send(json.dumps({"op": 1, "d": self.state.get("seq")}))
            await asyncio.sleep(interval)

    async def start(self, ctx) -> None:
        if self.halt.is_set() or ctx.stopping.is_set():
            return
        if len(ctx.triggers) != 1:
            raise ConnectionNotAuthorizedError(provider="discord", hint="Use one receiver per Discord bot.")
        trigger = ctx.triggers[0]
        config = trigger.config

        class Resolver:
            async def resolve(self, _request):
                return await ctx.resolve_credential(trigger_id=trigger.id)

        lease = CredentialLease(
            Resolver(),
            ConnectionResolutionRequest(
                ref=ConnectionRef.parse(config["connection"]),
                principal=ExecutionPrincipal(
                    kind="flow_owner", user_id=str(trigger.user_id), actor_id=str(trigger.user_id), interactive=False
                ),
            ),
        )
        async with DiscordClient(lease) as client:
            bot = await client.identity()
            if bot["id"] != self.state.get("bot_id"):
                raise ConnectionNotAuthorizedError(
                    provider="discord", hint="Reconnect the bot reserved for this trigger."
                )
            for channel_id in config["channel_ids"]:
                await client.channel(config["guild_id"], channel_id)
            if trigger.kind == "discord.message" and not bot["content_enabled"]:
                raise ConnectionNotAuthorizedError(
                    provider="discord", hint="Enable and, when required, obtain approval for Message Content Intent."
                )
            credential = await lease.get_credential()
            token = credential.access_token.get_secret_value()
            resume = bool(
                self.state.get("session_id") and type(self.state.get("seq")) is int and self.state.get("resume_url")
            )
            if resume:
                url = gateway_url(self.state["resume_url"])
            else:
                info = await client.request("GET", "/gateway/bot")
                limits = info.get("session_start_limit", {})
                if info.get("shards") != 1 or type(limits.get("remaining")) is not int:
                    raise ConnectionNotAuthorizedError(
                        provider="discord", hint="This receiver supports single-shard Discord bots only."
                    )
                if limits["remaining"] < 1:
                    raise RateLimitedError(
                        provider="discord",
                        retry_after=max(1, min(float(limits.get("reset_after", 60000)) / 1000, 86400)),
                    )
                delay = 5.1 - (time.time() - self.state.get("identified_at", 0))
                if delay > 0:
                    raise RateLimitedError(provider="discord", retry_after=min(delay, 5.1))
                url = gateway_url(info.get("url"))
            heartbeat = None
            stopping = None
            settled = None
            try:
                self.ws = await ws_connect(
                    url,
                    open_timeout=10,
                    close_timeout=5,
                    max_size=1024 * 1024,
                    ping_interval=None,
                    logger=_WEBSOCKET_LOGGER,
                )
                if self.halt.is_set() or ctx.stopping.is_set():
                    return
                hello = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=10))
                hello_data = hello.get("d") if isinstance(hello, dict) else None
                interval = hello_data.get("heartbeat_interval") if isinstance(hello_data, dict) else None
                if (
                    not isinstance(hello, dict)
                    or hello.get("op") != OP_HELLO
                    or type(interval) not in {int, float}
                    or not MIN_HEARTBEAT_MS <= interval <= MAX_HEARTBEAT_MS
                ):
                    raise ProviderUnavailableError(provider="discord")
                self.acked = True
                heartbeat = asyncio.create_task(self._heartbeat(interval / 1000))
                if resume:
                    auth = {
                        "op": 6,
                        "d": {"token": token, "session_id": self.state["session_id"], "seq": self.state["seq"]},
                    }
                else:
                    self.state = {"bot_id": bot["id"], "identified_at": time.time()}
                    await self._save(ctx, trigger)
                    intents = 1 | (1 << 9) | ((1 << 15) if trigger.kind == "discord.message" else 0)
                    auth = {
                        "op": 2,
                        "d": {
                            "token": token,
                            "intents": intents,
                            "properties": {"os": "linux", "browser": "langflow", "device": "langflow"},
                        },
                    }
                await self.ws.send(json.dumps(auth))
                stopping = asyncio.create_task(ctx.stopping.wait())
                settled = asyncio.create_task(self._settle(ctx))
                await self._read(ctx, trigger, bot["id"], token, heartbeat, stopping, resuming=resume)
            except ConnectionClosed as exc:
                code = exc.rcvd.code if exc.rcvd else None
                if code in {4007, 4009}:
                    self.state = {"bot_id": bot["id"], "identified_at": self.state.get("identified_at", 0)}
                    await self._save(ctx, trigger)
                if code == AUTH_FAILED:
                    raise AuthExpiredError(provider="discord") from None
                if code in {4010, 4011, 4012, 4013, 4014}:
                    raise ConnectionNotAuthorizedError(
                        provider="discord", hint="Check the bot intents and single-shard configuration."
                    ) from None
                raise ProviderUnavailableError(provider="discord") from None
            except (OSError, ValueError, TimeoutError):
                raise ProviderUnavailableError(provider="discord") from None
            finally:
                self.connected = False
                for task in (heartbeat, stopping, settled):
                    if task:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError, Exception):
                            await task
                if self.ws:
                    with contextlib.suppress(Exception):
                        await self.ws.close(code=4000)
                    self.ws = None

    async def _settle(self, ctx):
        await asyncio.sleep(STABLE_CONNECTION_SECONDS)
        if self.connected and not ctx.stopping.is_set() and not self.halt.is_set() and ctx.mark_connected:
            await ctx.mark_connected()

    async def _read(self, ctx, trigger, bot_id, token, heartbeat, stopping, *, resuming=False):
        while not self.halt.is_set():
            reader = asyncio.create_task(self.ws.recv())
            try:
                done, _ = await asyncio.wait({reader, heartbeat, stopping}, return_when=asyncio.FIRST_COMPLETED)
                if stopping in done:
                    return
                if heartbeat in done:
                    await heartbeat
                frame = json.loads(await reader)
            finally:
                if not reader.done():
                    reader.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await reader
            if not isinstance(frame, dict):
                raise ProviderUnavailableError(provider="discord")
            op = frame.get("op")
            if op == OP_HEARTBEAT_ACK:
                self.acked = True
            elif op == 1:
                await self.ws.send(json.dumps({"op": 1, "d": self.state.get("seq")}))
            elif op == OP_RECONNECT:
                raise ProviderUnavailableError(provider="discord")
            elif op == OP_INVALID_SESSION:
                if frame.get("d") is not True:
                    self.state = {"bot_id": bot_id, "identified_at": self.state.get("identified_at", 0)}
                    await self._save(ctx, trigger)
                raise RateLimitedError(provider="discord", retry_after=5)
            elif op == 0:
                data = frame.get("d")
                if not isinstance(data, dict) or type(frame.get("s")) is not int:
                    raise ProviderUnavailableError(provider="discord")
                if frame.get("t") == "READY":
                    if (
                        data.get("user", {}).get("id") != bot_id
                        or data.get("application", {}).get("id") != bot_id
                        or not isinstance(data.get("session_id"), str)
                        or not 1 <= len(data["session_id"]) <= MAX_SESSION_LENGTH
                    ):
                        raise ConnectionNotAuthorizedError(
                            provider="discord", hint="The Gateway bot identity did not match the connection."
                        )
                    gateway_url(data.get("resume_gateway_url"))
                    self.state.update(session_id=data["session_id"], resume_url=data["resume_gateway_url"])
                    self.connected = True
                elif frame.get("t") == "RESUMED":
                    self.connected = True
                elif frame.get("t") == "MESSAGE_CREATE":
                    if not self.connected and not resuming:
                        raise ProviderUnavailableError(provider="discord")
                    event = normalize(data, bot_id=bot_id, kind=trigger.kind, config=trigger.config)
                    if event is not None:
                        await ctx.emit(
                            trigger_id=trigger.id,
                            dedupe_key=f"discord:message:{event['message_id']}",
                            payload={"data": redact(event, token), "session_key": event["session_key"]},
                            expected_config=trigger.config,
                            expected_kind=trigger.kind,
                        )
                self.state["seq"] = frame["s"]
                await self._save(ctx, trigger)
