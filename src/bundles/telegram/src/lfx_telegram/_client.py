"""Fixed-origin Telegram Bot API transport with credential-free failures."""

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

API_ORIGIN = "https://api.telegram.org"
TOKEN_PATTERN = re.compile(r"[1-9][0-9]{4,15}:[A-Za-z0-9_-]{30,128}")
MAX_RETRY_AFTER_SECONDS = 86400
METHODS = frozenset({"getMe", "getUpdates", "getWebhookInfo", "setWebhook", "deleteWebhook", "sendMessage"})


def redact(value: Any) -> Any:
    """Remove Telegram credentials even when a user posts one as message text."""
    if isinstance(value, str):
        return TOKEN_PATTERN.sub("[redacted bot token]", value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


class TelegramClient:
    """Keep token-bearing URLs below httpx's request-logging client layer."""

    def __init__(self, lease: CredentialLease, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._lease = lease
        self._transport = transport if transport is not None else httpx.AsyncHTTPTransport(retries=0)

    async def __aenter__(self):
        await self._transport.__aenter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._transport.__aexit__(*args)

    async def _request(self, method: str, payload: dict[str, Any]) -> Any:
        credential = await self._lease.get_credential()
        token = credential.access_token.get_secret_value()
        if credential.provider not in {"", "telegram"} or credential.identity not in {None, "bot"}:
            raise ConnectionNotAuthorizedError(provider="telegram")
        if not TOKEN_PATTERN.fullmatch(token):
            msg = "Use a Telegram bot token issued by BotFather."
            raise InvalidRequestError(msg, provider="telegram")
        bot_id = token.split(":", 1)[0]
        if credential.account is not None and credential.account.id != bot_id:
            raise ConnectionNotAuthorizedError(provider="telegram")
        request = httpx.Request(
            "POST",
            f"{API_ORIGIN}/bot{token}/{method}",
            json=payload,
            extensions={"timeout": {"connect": 10.0, "read": 35.0, "write": 10.0, "pool": 10.0}},
        )
        try:
            response = await self._transport.handle_async_request(request)
            try:
                await response.aread()
                body = response.json()
                status = response.status_code
            finally:
                await response.aclose()
        except (httpx.HTTPError, ValueError, TypeError):
            raise ProviderUnavailableError(provider="telegram") from None
        if not isinstance(body, dict):
            raise ProviderUnavailableError(provider="telegram")
        code = body.get("error_code", status)
        code = code if type(code) is int else status
        if status >= httpx.codes.INTERNAL_SERVER_ERROR:
            raise ProviderUnavailableError(provider="telegram", http_status=status)
        if code == httpx.codes.UNAUTHORIZED:
            raise AuthExpiredError(provider="telegram")
        if code == httpx.codes.TOO_MANY_REQUESTS:
            parameters = body.get("parameters")
            retry = parameters.get("retry_after") if isinstance(parameters, dict) else None
            retry = float(retry) if type(retry) is int and 0 <= retry <= MAX_RETRY_AFTER_SECONDS else None
            raise RateLimitedError(provider="telegram", retry_after=retry)
        if code == httpx.codes.FORBIDDEN:
            raise ConnectionNotAuthorizedError(provider="telegram", reason="provider")
        if code in {400, 404, 409}:
            message = "Telegram rejected the request. Check the target and bot receiver configuration."
            raise InvalidRequestError(message, provider="telegram", http_status=code)
        if body.get("ok") is not True or status != httpx.codes.OK:
            raise ProviderUnavailableError(provider="telegram")
        return body.get("result")

    async def call(self, method: str, **payload: Any) -> Any:
        """Call only declared methods, with one credential re-resolution on rejection."""
        if method not in METHODS:
            msg = "This Telegram method is unsupported."
            raise InvalidRequestError(msg, provider="telegram")
        try:
            return await self._request(method, payload)
        except AuthExpiredError as error:
            await self._lease.get_token_after_auth_error(error)
            return await self._request(method, payload)

    async def identity(self) -> dict[str, Any]:
        """Establish the bot identity from Telegram, never from caller metadata."""
        result = await self.call("getMe")
        credential = await self._lease.get_credential()
        token_id = credential.access_token.get_secret_value().split(":", 1)[0]
        if (
            not isinstance(result, dict)
            or result.get("is_bot") is not True
            or type(result.get("id")) is not int
            or str(result["id"]) != token_id
            or not isinstance(result.get("username"), str)
            or not re.fullmatch(r"[A-Za-z0-9_]{5,32}", result["username"])
        ):
            raise ConnectionNotAuthorizedError(
                provider="telegram", hint="Use a token whose Telegram bot identity can be verified."
            )
        return {"id": str(result["id"]), "username": result["username"]}
