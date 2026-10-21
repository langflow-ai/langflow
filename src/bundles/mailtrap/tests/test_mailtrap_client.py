"""Shared helpers: request targets, client construction, error mapping, address parsing, recipient limit."""

from __future__ import annotations

import asyncio
import re

import lfx_mailtrap
import mailtrap as mt
import mailtrap.config
import pytest
import requests
from lfx_mailtrap import _client
from lfx_mailtrap._guardrail import (
    RecipientNotAllowedError,
    assert_recipients_allowed,
    is_recipient_allowed,
    parse_allowed_recipients,
)
from pydantic import SecretStr

COMPONENT_CLASSES = [getattr(lfx_mailtrap, name) for name in lfx_mailtrap.__all__]
REQUEST_TARGET_WORDS = ("url", "host", "base", "proxy", "endpoint")


def test_sdk_hosts_are_the_mailtrap_hosts():
    # The components never pass ``api_host``, so these constants are the only request targets.
    assert mailtrap.config.SENDING_HOST == "send.api.mailtrap.io"
    assert mailtrap.config.BULK_HOST == "bulk.api.mailtrap.io"
    assert mailtrap.config.SANDBOX_HOST == "sandbox.api.mailtrap.io"
    assert mailtrap.config.GENERAL_HOST == "mailtrap.io"


@pytest.mark.parametrize("component_class", COMPONENT_CLASSES, ids=lambda c: c.__name__)
def test_no_component_declares_a_request_target_input(component_class):
    names = [component_input.name for component_input in component_class.inputs]
    assert not [name for name in names if any(word in name for word in REQUEST_TARGET_WORDS)]


@pytest.mark.parametrize("component_class", COMPONENT_CLASSES, ids=lambda c: c.__name__)
def test_no_component_uses_an_input_name_that_langflow_overwrites(component_class):
    # Langflow sets a top-level ``stream`` or ``streaming`` field on every node to the
    # run's own streaming flag, which would silently replace the Stream dropdown.
    names = {component_input.name for component_input in component_class.inputs}
    assert not names & {"stream", "streaming"}


@pytest.mark.parametrize(
    ("stream", "host"),
    [
        (_client.STREAM_TRANSACTIONAL, "send.api.mailtrap.io"),
        (_client.STREAM_BULK, "bulk.api.mailtrap.io"),
        (_client.STREAM_SANDBOX, "sandbox.api.mailtrap.io"),
    ],
)
def test_sending_client_uses_the_host_of_the_stream(stream, host):
    client = _client.sending_client("token", stream, "77")
    assert client.api_host is None
    assert client._sending_api_host == host
    assert client.inbox_id == ("77" if stream == _client.STREAM_SANDBOX else None)


def test_sending_client_needs_an_inbox_for_sandbox():
    with pytest.raises(ValueError, match="Sandbox Inbox ID is required"):
        _client.sending_client("token", _client.STREAM_SANDBOX, "")


def test_sending_client_rejects_an_unknown_stream():
    with pytest.raises(ValueError, match="Stream must be one of"):
        _client.sending_client("token", "Marketing", None)


def test_clients_identify_the_bundle():
    for client in (_client.sending_client("token", _client.STREAM_BULK, None), _client.sandbox_client("token", 1)):
        assert client.headers["User-Agent"].startswith("langflow-mailtrap-bundle ")
    assert "mailtrap-python/" in _client.USER_AGENT


def test_require_token_unwraps_secret_values():
    assert _client.require_token(SecretStr(" token ")) == "token"
    assert _client.require_token("token") == "token"
    with pytest.raises(ValueError, match="Mailtrap API token is required"):
        _client.require_token("")
    with pytest.raises(ValueError, match="Mailtrap API token is required"):
        _client.require_token(None)


def test_require_id_reads_numbers_only():
    assert _client.require_id(" 42 ", "Account ID") == 42
    with pytest.raises(ValueError, match="Account ID is required"):
        _client.require_id("", "Account ID")
    with pytest.raises(ValueError, match="Account ID must be a number"):
        _client.require_id("abc", "Account ID")


def test_parse_addresses_accepts_names_lists_commas_and_lines():
    addresses = _client.parse_addresses(
        ["Jane <jane@example.com>, bob@example.com", "amy@example.org\ntom@example.org"]
    )
    assert [(a.email, a.name) for a in addresses] == [
        ("jane@example.com", "Jane"),
        ("bob@example.com", None),
        ("amy@example.org", None),
        ("tom@example.org", None),
    ]
    assert _client.parse_addresses(None) == []
    assert _client.parse_addresses("") == []
    assert _client.parse_addresses([]) == []


def test_parse_addresses_rejects_an_invalid_address():
    with pytest.raises(ValueError, match="not a valid email address"):
        _client.parse_addresses("not-an-address")


def test_parse_address_needs_exactly_one():
    assert _client.parse_address("Acme <hello@acme.com>", "From").email == "hello@acme.com"
    with pytest.raises(ValueError, match="From is required"):
        _client.parse_address("", "From")
    with pytest.raises(ValueError, match="exactly one email address"):
        _client.parse_address("a@acme.com, b@acme.com", "From")


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            mt.AuthorizationError(errors=["Incorrect API token"]),
            "Mailtrap rejected the API token (401): Incorrect API token",
        ),
        (
            mt.APIError(422, errors=["from: domain is not verified"]),
            "Mailtrap API error 422: from: domain is not verified",
        ),
        (mt.ClientConfigurationError("`account_id` is required"), "Mailtrap client error: `account_id` is required"),
        (requests.ConnectionError("connection refused"), "Mailtrap request failed: connection refused"),
        (requests.Timeout(), "Mailtrap request failed: Timeout"),
    ],
)
def test_call_mailtrap_turns_sdk_errors_into_value_errors(error, message):
    def failing_call():
        raise error

    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        asyncio.run(_client.call_mailtrap(failing_call))


def test_truncate_cuts_long_bodies():
    assert _client.truncate(None) == ("", False)
    assert _client.truncate("short") == ("short", False)
    body, truncated = _client.truncate("x" * (_client.MAX_BODY_CHARS + 5))
    assert len(body) == _client.MAX_BODY_CHARS
    assert truncated is True


def test_update_stream_fields_shows_the_inbox_only_for_sandbox():
    build_config = {"sandbox_inbox_id": {"show": False, "required": False}}
    _client.update_stream_fields(build_config, _client.STREAM_SANDBOX, "sending_stream")
    assert build_config["sandbox_inbox_id"] == {"show": True, "required": True}
    _client.update_stream_fields(build_config, _client.STREAM_BULK, "sending_stream")
    assert build_config["sandbox_inbox_id"] == {"show": False, "required": False}
    _client.update_stream_fields(build_config, _client.STREAM_SANDBOX, "subject")
    assert build_config["sandbox_inbox_id"] == {"show": False, "required": False}


# Recipient limit (ported from mailtrap-langchain-example's guardrail.py)


def test_allowed_recipients_split_domains_and_addresses():
    domains, addresses = parse_allowed_recipients(" Example.com, @example.org; Me@Gmail.com\nexample.net ")
    assert domains == {"example.com", "example.org", "example.net"}
    assert addresses == {"me@gmail.com"}
    assert parse_allowed_recipients(None) == (set(), set())
    assert parse_allowed_recipients(["example.com"]) == ({"example.com"}, set())


@pytest.mark.parametrize(
    ("recipient", "allowed"),
    [
        ("jane@example.com", True),
        (" JANE@Example.COM ", True),
        ("me@gmail.com", True),
        ("someone@gmail.com", False),
        ("jane@sub.example.com", False),
        ("jane@example.com.evil.io", False),
        ("not-an-address", False),
    ],
)
def test_is_recipient_allowed(recipient, allowed):
    assert (
        is_recipient_allowed(recipient=recipient, allowed_domains={"example.com"}, allowed_addresses={"me@gmail.com"})
        is allowed
    )


def test_assert_recipients_allowed_without_a_limit_allows_everyone():
    assert_recipients_allowed(["anyone@anywhere.io"], "")
    assert_recipients_allowed(["anyone@anywhere.io"], None)


def test_assert_recipients_allowed_names_the_rejected_recipient():
    with pytest.raises(RecipientNotAllowedError, match=r"'eve@evil\.io' is not allowed.*@example\.com, me@gmail\.com"):
        assert_recipients_allowed(["jane@example.com", "eve@evil.io"], "example.com, me@gmail.com")
    assert issubclass(RecipientNotAllowedError, ValueError)
