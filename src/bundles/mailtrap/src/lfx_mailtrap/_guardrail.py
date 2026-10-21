"""Recipient limit for the Mailtrap components that send email.

Ported from ``guardrail.py`` in https://github.com/mailtrap/mailtrap-langchain-example.
That example allows one domain plus the user's own address.  Here the
**Allowed Recipient Domains** input takes a list: ``example.com`` (or
``@example.com``) allows every address at that domain, and a full address such
as ``me@gmail.com`` allows that one address.  An empty input sets no limit.

The check runs before any request is made, so an Agent that picks a recipient
outside the list gets an error and no email leaves Langflow.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+$")


class RecipientNotAllowedError(ValueError):
    """A recipient is outside the allowed domains and addresses."""


def parse_allowed_recipients(raw: object) -> tuple[set[str], set[str]]:
    """Split the Allowed Recipient Domains input into (domains, exact addresses)."""
    if raw is None:
        return set(), set()
    values = raw if isinstance(raw, list) else re.split(r"[,;\s]+", str(raw))
    domains: set[str] = set()
    addresses: set[str] = set()
    for value in values:
        entry = str(value).strip().lower().removeprefix("@")
        if not entry:
            continue
        if "@" in entry:
            addresses.add(entry)
        else:
            domains.add(entry)
    return domains, addresses


def is_recipient_allowed(*, recipient: str, allowed_domains: set[str], allowed_addresses: set[str]) -> bool:
    recipient = recipient.strip().lower()
    if not EMAIL_PATTERN.match(recipient):
        return False

    if recipient in allowed_addresses:
        return True

    domain = recipient.rsplit("@", 1)[1]
    return domain in allowed_domains


def assert_recipients_allowed(recipients: Iterable[str], allowed: object) -> None:
    """Raise :class:`RecipientNotAllowedError` for the first recipient outside the limit."""
    allowed_domains, allowed_addresses = parse_allowed_recipients(allowed)
    if not allowed_domains and not allowed_addresses:
        return

    for recipient in recipients:
        if not is_recipient_allowed(
            recipient=recipient, allowed_domains=allowed_domains, allowed_addresses=allowed_addresses
        ):
            allowed_text = ", ".join([*sorted(f"@{domain}" for domain in allowed_domains), *sorted(allowed_addresses)])
            msg = (
                f"Recipient '{recipient}' is not allowed. "
                f"Allowed Recipient Domains limits this component to: {allowed_text}."
            )
            raise RecipientNotAllowedError(msg)
