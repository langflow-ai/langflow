"""Fixed-origin Discord bot requests with bounded, sanitized failures."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
)

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease

MAX_RETRY_SECONDS = 86400

API_ORIGIN = "https://discord.com"
API_BASE = API_ORIGIN + "/api/v10"
_PATH = re.compile(r"^(?:/users/@me|/applications/@me|/gateway/bot|/channels/[1-9][0-9]{0,19}(?:/messages)?)$")


def snowflake(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value) or int(value) >= 2**64:
        msg = "Use a numeric Discord ID copied from developer mode."
        raise InvalidRequestError(msg, provider="discord")
    return value


def redact(value: Any, token: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: redact(item, token)
            for key, item in value.items()
            if not re.search(r"token|secret|authorization", key, re.IGNORECASE)
        }
    if isinstance(value, list):
        return [redact(item, token) for item in value]
    if isinstance(value, str) and token:
        return value.replace(token, "[redacted]")
    return value


def _http_transport() -> httpx.AsyncBaseTransport:
    return httpx.AsyncHTTPTransport(retries=0)


class DiscordClient:
    def __init__(self, lease: CredentialLease):
        self.lease = lease
        self.http = httpx.AsyncClient(transport=_http_transport(), timeout=15, follow_redirects=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        await self.http.aclose()

    async def request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        if (
            not _PATH.fullmatch(path)
            or method not in {"GET", "POST"}
            or (method == "POST" and not path.endswith("/messages"))
        ):
            msg = "Unsupported Discord API request."
            raise InvalidRequestError(msg, provider="discord")
        credential = await self.lease.get_credential()
        token = credential.access_token.get_secret_value()
        if (
            credential.provider != "discord"
            or credential.identity != "bot"
            or not token
            or any(c.isspace() for c in token)
        ):
            raise ConnectionNotAuthorizedError(provider="discord", hint="Use a Discord application bot token.")
        try:
            response = await self.http.request(
                method, API_BASE + path, headers={"Authorization": "Bot " + token}, json=payload
            )
        except httpx.HTTPError:
            raise ProviderUnavailableError(provider="discord") from None
        if response.status_code == httpx.codes.UNAUTHORIZED:
            raise AuthExpiredError(provider="discord")
        if response.status_code in {403, 404}:
            raise ConnectionNotAuthorizedError(
                provider="discord", hint="Check the bot installation and channel permissions."
            )
        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            try:
                delay = float(response.json().get("retry_after", response.headers.get("Retry-After", 1)))
                if not 0 <= delay <= MAX_RETRY_SECONDS:
                    raise ValueError
            except (TypeError, ValueError, AttributeError):
                delay = 1
            raise RateLimitedError(provider="discord", retry_after=delay)
        if response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR or response.is_redirect:
            raise ProviderUnavailableError(provider="discord")
        if response.is_error:
            msg = "Discord rejected the message configuration."
            raise InvalidRequestError(msg, provider="discord", http_status=response.status_code)
        try:
            body = response.json()
        except ValueError:
            raise ProviderUnavailableError(provider="discord") from None
        if not isinstance(body, dict):
            raise ProviderUnavailableError(provider="discord")
        return redact(body, token)

    async def identity(self) -> dict:
        bot = await self.request("GET", "/users/@me")
        app = await self.request("GET", "/applications/@me")
        bot_id = snowflake(bot.get("id"))
        if bot.get("bot") is not True or snowflake(app.get("id")) != bot_id:
            raise ConnectionNotAuthorizedError(
                provider="discord", hint="Use the token for this Discord application bot."
            )
        credential = await self.lease.get_credential()
        if credential.account is not None and credential.account.id != bot_id:
            raise ConnectionNotAuthorizedError(provider="discord", hint="Reconnect the original Discord bot.")
        flags = app.get("flags", 0)
        if type(flags) is not int:
            raise ProviderUnavailableError(provider="discord")
        return {
            "id": bot_id,
            "name": str(bot.get("username", "Discord bot"))[:100],
            "content_enabled": bool(flags & ((1 << 18) | (1 << 19))),
        }

    async def channel(self, guild_id: str, channel_id: str) -> dict:
        channel = await self.request("GET", f"/channels/{snowflake(channel_id)}")
        if (
            channel.get("id") != channel_id
            or channel.get("guild_id") != snowflake(guild_id)
            or channel.get("type") not in {0, 5, 10, 11, 12}
        ):
            raise ConnectionNotAuthorizedError(
                provider="discord", hint="Choose an accessible text channel or thread in the configured guild."
            )
        return channel
