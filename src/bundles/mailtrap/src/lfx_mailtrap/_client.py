"""Mailtrap client, shared inputs and helpers for the ``lfx-mailtrap`` components.

Request targets
---------------
Every request goes through the official SDK's :class:`mailtrap.MailtrapClient`.
The components never pass ``api_host``, and no component has a URL, host or
proxy input, so the SDK always talks to its fixed Mailtrap hosts
(``send.api.mailtrap.io``, ``bulk.api.mailtrap.io``, ``sandbox.api.mailtrap.io``
and ``mailtrap.io``) and the API token is only ever sent to Mailtrap.
``tests/test_mailtrap_client.py`` pins both facts.

The SDK is synchronous (``requests``), so :func:`call_mailtrap` runs each call
in a worker thread and turns the SDK's errors into a :class:`ValueError` with
Mailtrap's own message.  In tool mode Langflow hands that message to the Agent.

This module and ``_guardrail.py`` live at the package root, as Slack's
``_client.py`` does, so that ``components/mailtrap`` holds only components.
"""

from __future__ import annotations

import asyncio
from email.utils import getaddresses
from typing import TYPE_CHECKING, Any, TypeVar

import mailtrap as mt
import requests
from lfx.inputs.inputs import DropdownInput, SecretStrInput, StrInput
from lfx.utils.secrets import secret_value_to_str

from lfx_mailtrap._guardrail import EMAIL_PATTERN

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

DOCUMENTATION_URL = "https://docs.langflow.org/bundles-mailtrap"
DEFAULT_CATEGORY = "langflow"
# Message bodies are cut to this many characters to keep an Agent's context small.
MAX_BODY_CHARS = 20_000
# Identify the integration to Mailtrap; keeps traffic attributable.
USER_AGENT = f"langflow-mailtrap-bundle {mt.MailtrapClient.DEFAULT_USER_AGENT}"

STREAM_TRANSACTIONAL = "Transactional"
STREAM_BULK = "Bulk"
STREAM_SANDBOX = "Sandbox"
STREAMS = [STREAM_TRANSACTIONAL, STREAM_BULK, STREAM_SANDBOX]


def api_token_input() -> SecretStrInput:
    return SecretStrInput(
        name="api_token",
        display_name="Mailtrap API Token",
        required=True,
        info="A Mailtrap API token. Create one at https://mailtrap.io/api-tokens.",
    )


def stream_input() -> DropdownInput:
    # Not named ``stream``: Langflow overwrites a top-level ``stream`` field on
    # every node with the run's own streaming flag (see api/warm_graph.py).
    return DropdownInput(
        name="sending_stream",
        display_name="Stream",
        options=STREAMS,
        value=STREAM_TRANSACTIONAL,
        real_time_refresh=True,
        info=(
            "Transactional and Bulk send real email from a verified sending domain. "
            "Sandbox delivers into an Email Sandbox inbox and reaches no one."
        ),
    )


def sandbox_inbox_input(*, for_sending: bool = True) -> StrInput:
    if for_sending:
        return StrInput(
            name="sandbox_inbox_id",
            display_name="Sandbox Inbox ID",
            show=False,
            info="The ID of the Email Sandbox inbox to send to. Required when Stream is Sandbox.",
        )
    return StrInput(
        name="sandbox_inbox_id",
        display_name="Sandbox Inbox ID",
        required=True,
        info="The ID of the Email Sandbox inbox, as in the inbox URL: mailtrap.io/inboxes/<ID>/messages.",
    )


def account_id_input() -> StrInput:
    return StrInput(
        name="account_id",
        display_name="Account ID",
        required=True,
        info="Your Mailtrap account ID. The Email Sandbox API needs it.",
    )


def category_input() -> StrInput:
    return StrInput(
        name="category",
        display_name="Category",
        value=DEFAULT_CATEGORY,
        advanced=True,
        info="Mailtrap category for the email, used to group it in stats and logs.",
    )


def allowed_recipients_input() -> StrInput:
    return StrInput(
        name="allowed_recipient_domains",
        display_name="Allowed Recipient Domains",
        advanced=True,
        info=(
            "Comma-separated domains, for example 'example.com, example.org'. A full address, for example "
            "'me@gmail.com', allows that one address. When set, any other recipient is rejected before sending."
        ),
    )


def update_stream_fields(build_config: dict, field_value: Any, field_name: str | None) -> dict:
    """Show the Sandbox Inbox ID input only when Stream is Sandbox."""
    if field_name == "sending_stream" and "sandbox_inbox_id" in build_config:
        build_config["sandbox_inbox_id"]["show"] = field_value == STREAM_SANDBOX
        build_config["sandbox_inbox_id"]["required"] = field_value == STREAM_SANDBOX
    return build_config


def require_token(value: Any) -> str:
    token = secret_value_to_str(value, strip=True)
    if not token:
        msg = "Mailtrap API token is required. Set the Mailtrap API Token input."
        raise ValueError(msg)
    return token


def optional_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def require_text(value: Any, label: str) -> str:
    text = optional_text(value)
    if not text:
        msg = f"{label} is required."
        raise ValueError(msg)
    return text


def require_id(value: Any, label: str) -> int:
    """Read a numeric Mailtrap ID (account, inbox or Sandbox message)."""
    text = require_text(value, label)
    if not text.isdigit():
        msg = f"{label} must be a number, got '{text}'."
        raise ValueError(msg)
    return int(text)


def parse_addresses(raw: Any) -> list[mt.Address]:
    """Turn a list, or a comma- or newline-separated string, into Mailtrap addresses.

    Accepts ``a@example.com`` and ``Name <a@example.com>``.
    """
    if raw is None or raw == "":
        return []
    values = raw if isinstance(raw, list) else [raw]
    lines = [line for value in values if value is not None for line in str(value).splitlines()]
    addresses: list[mt.Address] = []
    for name, raw_email in getaddresses(lines):
        email = raw_email.strip()
        if not email:
            continue
        if not EMAIL_PATTERN.match(email):
            msg = f"'{email}' is not a valid email address."
            raise ValueError(msg)
        addresses.append(mt.Address(email=email, name=name.strip() or None))
    return addresses


def parse_address(raw: Any, label: str) -> mt.Address:
    addresses = parse_addresses(require_text(raw, label))
    if len(addresses) != 1:
        msg = f"{label} must be exactly one email address."
        raise ValueError(msg)
    return addresses[0]


def sending_client(token: str, stream: str, sandbox_inbox_id: Any) -> mt.MailtrapClient:
    """Client for ``/api/send`` on the host that matches the stream."""
    if stream == STREAM_SANDBOX:
        inbox_id = require_id(sandbox_inbox_id, "Sandbox Inbox ID")
        return mt.MailtrapClient(token=token, sandbox=True, inbox_id=str(inbox_id), user_agent=USER_AGENT)
    if stream not in STREAMS:
        msg = f"Stream must be one of {', '.join(STREAMS)}, got '{stream}'."
        raise ValueError(msg)
    return mt.MailtrapClient(token=token, bulk=stream == STREAM_BULK, user_agent=USER_AGENT)


def sandbox_client(token: str, account_id: int) -> mt.MailtrapClient:
    """Client for the Email Sandbox (testing) API, which is scoped to an account."""
    return mt.MailtrapClient(token=token, account_id=str(account_id), user_agent=USER_AGENT)


async def call_mailtrap(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a blocking SDK call in a worker thread and turn its errors into ValueError."""
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except mt.AuthorizationError as e:
        msg = f"Mailtrap rejected the API token (401): {e}"
        raise ValueError(msg) from e
    except mt.APIError as e:
        msg = f"Mailtrap API error {e.status}: {e}"
        raise ValueError(msg) from e
    except mt.MailtrapError as e:
        msg = f"Mailtrap client error: {e}"
        raise ValueError(msg) from e
    except requests.RequestException as e:
        msg = f"Mailtrap request failed: {str(e) or type(e).__name__}"
        raise ValueError(msg) from e


def truncate(text: str | None) -> tuple[str, bool]:
    """Cut a message body to :data:`MAX_BODY_CHARS` and report whether it was cut."""
    if not text:
        return "", False
    if len(text) <= MAX_BODY_CHARS:
        return text, False
    return text[:MAX_BODY_CHARS], True


def sandbox_message_fields(message: Any) -> dict[str, Any]:
    """Summary fields of an Email Sandbox message (``mailtrap.models.messages.EmailMessage``)."""
    return {
        "id": message.id,
        "subject": message.subject,
        "from_email": message.from_email,
        "from_name": message.from_name,
        "to_email": message.to_email,
        "to_name": message.to_name,
        "sent_at": message.sent_at.isoformat(),
        "is_read": message.is_read,
        "size": message.human_size,
    }
