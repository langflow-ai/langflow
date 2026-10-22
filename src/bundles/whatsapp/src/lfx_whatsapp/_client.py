"""Fixed-origin Graph transport and operator-owned WhatsApp account binding."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

import httpx
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
)

if TYPE_CHECKING:
    from lfx.integrations.models import ResolvedCredential

ORIGIN = "https://graph.facebook.com"
SCOPES = ("whatsapp_business_management", "whatsapp_business_messaging")
_ID = re.compile(r"[1-9][0-9]{0,30}\Z")
_TOKEN = re.compile(r"EAA[A-Za-z0-9_-]{20,}")


MAX_TOKEN = 8192
TOKEN_EXPIRED_CODE = 190
MAX_TIMESTAMP = 253402300799
MAX_CURSOR = 2048


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        msg = "Use a numeric WhatsApp asset ID."
        raise ValueError(msg)
    return value


@dataclass(frozen=True)
class Settings:
    app_id: str
    waba_id: str
    phone_id: str
    version: str
    app_secret: str = field(repr=False)

    @property
    def tenant(self) -> str:
        return f"{self.app_id}:{self.waba_id}"


def settings() -> Settings:
    """Read server configuration, never an asset URL from the canvas."""
    try:
        app = identifier(os.environ.get("LANGFLOW_WHATSAPP_APP_ID"))
        waba = identifier(os.environ.get("LANGFLOW_WHATSAPP_WABA_ID"))
        phone = identifier(os.environ.get("LANGFLOW_WHATSAPP_PHONE_ID"))
        version = os.environ.get("LANGFLOW_WHATSAPP_GRAPH_VERSION", "")
        secret = os.environ.get("LANGFLOW_WHATSAPP_APP_SECRET", "")
        if not re.fullmatch(r"v[1-9][0-9]{0,2}\.0", version) or not re.fullmatch(r"[A-Fa-f0-9]{32}", secret):
            raise ValueError
    except ValueError:
        msg = "Configure the WhatsApp app, app secret, WABA, phone ID and Graph API version on this server."
        raise InvalidRequestError(msg, provider="whatsapp") from None
    return Settings(app, waba, phone, version, secret)


def redact(value: Any, *secrets: str) -> Any:
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[redacted]")
        return _TOKEN.sub("[redacted]", value)
    if isinstance(value, dict):
        return {key: redact(item, *secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, *secrets) for item in value]
    return value


class _CredentialReader(Protocol):
    async def get_credential(self) -> ResolvedCredential: ...


class WhatsAppClient:
    """Keep token-debug URLs below HTTP request logging and never retry sends."""

    def __init__(self, lease: _CredentialReader, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.lease = lease
        self.config = settings()
        self.transport = transport if transport is not None else httpx.AsyncHTTPTransport(retries=0)

    async def __aenter__(self):
        await self.transport.__aenter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.transport.__aexit__(*args)

    async def request(self, method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict:
        allowed = {
            "debug_token",
            f"{self.config.waba_id}/phone_numbers",
            f"{self.config.waba_id}/subscribed_apps",
            f"{self.config.phone_id}/messages",
        }
        if path not in allowed or method not in {"GET", "POST"}:
            msg = "Unsupported WhatsApp operation."
            raise InvalidRequestError(msg, provider="whatsapp")
        credential = await self.lease.get_credential()
        if credential.provider != "whatsapp" or credential.identity != "service":
            raise ConnectionNotAuthorizedError(provider="whatsapp")
        token = credential.access_token.get_secret_value()
        if not token or len(token) > MAX_TOKEN or any(character.isspace() for character in token):
            raise ConnectionNotAuthorizedError(provider="whatsapp")
        if credential.account is not None and (
            credential.account.id != self.config.phone_id or credential.account.tenant_id != self.config.tenant
        ):
            raise ConnectionNotAuthorizedError(provider="whatsapp")
        headers = {"Authorization": f"Bearer {token}"}
        if path == "debug_token":
            headers = {"Authorization": f"Bearer {self.config.app_id}|{self.config.app_secret}"}
            params = {"input_token": token}
        request = httpx.Request(
            method,
            f"{ORIGIN}/{self.config.version}/{path}",
            params=params,
            json=body,
            headers=headers,
            extensions={"timeout": dict.fromkeys(("connect", "read", "write", "pool"), 20.0)},
        )
        try:
            response = await self.transport.handle_async_request(request)
            try:
                await response.aread()
                result = response.json()
                status = response.status_code
            finally:
                await response.aclose()
        except (httpx.HTTPError, ValueError, TypeError):
            raise ProviderUnavailableError(provider="whatsapp") from None
        if not isinstance(result, dict):
            raise ProviderUnavailableError(provider="whatsapp")
        error = result.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        code = code if type(code) is int else None
        if status == httpx.codes.UNAUTHORIZED or code == TOKEN_EXPIRED_CODE:
            raise AuthExpiredError(provider="whatsapp")
        if status == httpx.codes.TOO_MANY_REQUESTS or code in {4, 17, 32, 613, 130429, 131056}:
            raise RateLimitedError(provider="whatsapp")
        if status >= httpx.codes.INTERNAL_SERVER_ERROR:
            raise ProviderUnavailableError(provider="whatsapp", http_status=status)
        if status == httpx.codes.FORBIDDEN or code in {10, 200}:
            raise ConnectionNotAuthorizedError(provider="whatsapp", reason="provider")
        if status >= httpx.codes.MULTIPLE_CHOICES or error is not None:
            msg = "WhatsApp rejected the request. Check account access, recipients and message eligibility."
            raise InvalidRequestError(
                msg,
                provider="whatsapp",
                http_status=status,
            )
        return result

    async def verify_account(self) -> tuple[frozenset[str], datetime | None]:
        """Prove the app, permission grant, expiry and WABA phone membership."""
        debug = (await self.request("GET", "debug_token")).get("data")
        if (
            not isinstance(debug, dict)
            or debug.get("is_valid") is not True
            or debug.get("type") != "SYSTEM_USER"
            or debug.get("app_id") != self.config.app_id
            or "expires_at" not in debug
            or not isinstance(debug.get("scopes"), list)
            or any(not isinstance(scope, str) for scope in debug["scopes"])
            or not set(SCOPES) <= set(debug["scopes"])
        ):
            raise ConnectionNotAuthorizedError(
                provider="whatsapp", hint="Use this app's system-user token with both WhatsApp permissions."
            )
        expirations = []
        for field_name in ("expires_at", "data_access_expires_at"):
            value = debug.get(field_name, 0)
            if type(value) is not int or value < 0 or value > MAX_TIMESTAMP:
                raise ConnectionNotAuthorizedError(provider="whatsapp")
            if value:
                if value <= time.time() + 60:
                    raise AuthExpiredError(provider="whatsapp")
                expirations.append(datetime.fromtimestamp(value, timezone.utc))
        after = None
        seen = set()
        found = False
        for _ in range(100):
            params = {"fields": "id", "limit": 100}
            if after is not None:
                params["after"] = after
            page = await self.request("GET", f"{self.config.waba_id}/phone_numbers", params=params)
            rows = page.get("data")
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ProviderUnavailableError(provider="whatsapp")
            found = found or any(row.get("id") == self.config.phone_id for row in rows)
            paging = page.get("paging", {})
            if not isinstance(paging, dict):
                raise ProviderUnavailableError(provider="whatsapp")
            if not paging.get("next"):
                break
            cursors = paging.get("cursors")
            after = cursors.get("after") if isinstance(cursors, dict) else None
            if not isinstance(after, str) or not after or len(after) > MAX_CURSOR or after in seen:
                raise ProviderUnavailableError(provider="whatsapp")
            seen.add(after)
        else:
            raise ProviderUnavailableError(provider="whatsapp")
        if not found:
            raise ConnectionNotAuthorizedError(
                provider="whatsapp", hint="The configured phone must belong to the configured WABA."
            )
        return frozenset(SCOPES), min(expirations) if expirations else None

    async def send(self, payload: dict) -> dict:
        await self.verify_account()
        result = await self.request("POST", f"{self.config.phone_id}/messages", body=payload)
        messages = result.get("messages")
        if (
            not isinstance(messages, list)
            or len(messages) != 1
            or not isinstance(messages[0], dict)
            or not isinstance(messages[0].get("id"), str)
        ):
            raise ProviderUnavailableError(provider="whatsapp")
        return redact(
            {
                "provider": "whatsapp",
                "phone_id": self.config.phone_id,
                "waba_id": self.config.waba_id,
                "message_id": messages[0]["id"],
                "recipient": payload["to"],
                "accepted": True,
            },
            (await self.lease.get_credential()).access_token.get_secret_value(),
            self.config.app_secret,
        )
