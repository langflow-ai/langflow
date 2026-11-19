"""Token-bearing API paths never reach the httpx request logger or errors."""

import logging

import httpx
import pytest
from conftest import BOT, TOKEN, BotTransport, Resolver, lease
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
)
from lfx_telegram._client import TelegramClient, redact


async def test_api_calls_bypass_url_logging(caplog):
    caplog.set_level(logging.DEBUG)
    transport = BotTransport([BOT])
    async with TelegramClient(lease(), transport=httpx.MockTransport(transport.handler)) as client:
        assert await client.identity() == {"id": "123456789", "username": "example_bot"}
    assert TOKEN not in caplog.text
    assert "api.telegram.org/bot" not in caplog.text


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, InvalidRequestError),
        (403, ConnectionNotAuthorizedError),
        (409, InvalidRequestError),
        (429, RateLimitedError),
        (500, ProviderUnavailableError),
    ],
)
async def test_provider_errors_are_typed_and_sanitized(status, error):
    transport = BotTransport(
        [
            (
                status,
                {"ok": False, "error_code": status, "description": f"secret {TOKEN}", "parameters": {"retry_after": 3}},
            )
        ]
    )
    async with TelegramClient(lease(), transport=httpx.MockTransport(transport.handler)) as client:
        with pytest.raises(error) as caught:
            await client.call("sendMessage", chat_id=1, text="hello")
    assert TOKEN not in str(caught.value)
    assert caught.value.__cause__ is None
    if status == 429:
        assert caught.value.retry_after == 3


async def test_auth_refresh_is_bounded():
    transport = BotTransport([(401, {"ok": False, "error_code": 401})] * 2)
    resolver = Resolver()
    async with TelegramClient(lease(resolver), transport=httpx.MockTransport(transport.handler)) as client:
        with pytest.raises(AuthExpiredError):
            await client.call("getMe")
    assert len(transport.calls) == 2
    assert len(resolver.calls) == 2


async def test_transport_exception_cannot_leak_credential_url():
    transport = BotTransport([httpx.ConnectError(f"failed https://api.telegram.org/bot{TOKEN}/getMe")])
    async with TelegramClient(lease(), transport=httpx.MockTransport(transport.handler)) as client:
        with pytest.raises(ProviderUnavailableError) as caught:
            await client.call("getMe")
    assert TOKEN not in str(caught.value)
    assert caught.value.__suppress_context__ is True


@pytest.mark.parametrize(
    "resolver", [Resolver(identity="user_delegated"), Resolver(account_id="987654321"), Resolver(tokens=["invalid"])]
)
async def test_bad_identity_fails_before_network(resolver):
    transport = BotTransport([])
    async with TelegramClient(lease(resolver), transport=httpx.MockTransport(transport.handler)) as client:
        with pytest.raises((ConnectionNotAuthorizedError, InvalidRequestError)):
            await client.call("getMe")
    assert transport.calls == []


@pytest.mark.parametrize("method", ["https://evil.invalid", "../getMe", "getFile", "getMe?token=other"])
async def test_api_method_is_an_allowlist(method):
    transport = BotTransport([])
    async with TelegramClient(lease(), transport=httpx.MockTransport(transport.handler)) as client:
        with pytest.raises(InvalidRequestError):
            await client.call(method)
    assert transport.calls == []


def test_posted_tokens_are_redacted_from_visible_payloads():
    assert redact({"text": f"token {TOKEN}"}) == {"text": "token [redacted bot token]"}
