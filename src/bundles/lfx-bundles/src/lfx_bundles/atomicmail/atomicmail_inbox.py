"""List or search the messages of an Atomic Mail inbox."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.atomicmail.atomicmail_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    AtomicMailAPIError,
    atomicmail_call,
    format_people,
)

MAX_MESSAGES_LIMIT = 50


class AtomicMailInboxComponent(Component):
    """Return the newest inbox messages, or the messages that match a search."""

    display_name = "Atomic Mail Inbox"
    description = "List the newest emails in your Atomic Mail inbox, or search all your mail."
    documentation = DOCUMENTATION_URL
    icon = "Mail"
    name = "AtomicMailInbox"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Atomic Mail API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Text to search for in all mail. Leave empty to list the newest inbox messages.",
            tool_mode=True,
        ),
        IntInput(
            name="max_messages",
            display_name="Max Messages",
            info=f"The number of messages to return, from 1 to {MAX_MESSAGES_LIMIT}.",
            value=10,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Atomic Mail to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Messages", name="messages", method="read_inbox"),
    ]

    async def _messages(self) -> list[Data]:
        """Return one ``Data`` per message, newest first; the preview is the ``text``."""
        query = str(self.query or "").strip()
        limit = min(max(int(self.max_messages or 1), 1), MAX_MESSAGES_LIMIT)
        try:
            if query:
                result = await atomicmail_call(
                    "search_messages",
                    {"query": query, "limit": limit},
                    api_key=self.api_key,
                    timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                )
            else:
                result = await atomicmail_call(
                    "read_inbox",
                    {"limit": limit},
                    api_key=self.api_key,
                    timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                )
            messages = result.get("messages")
            if not isinstance(messages, list):
                msg = "Atomic Mail returned an answer without a list of messages."
                raise AtomicMailAPIError(msg)
        except AtomicMailAPIError as exc:
            await logger.aerror(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        return [
            Data(
                text=str(message.get("preview") or message.get("subject") or ""),
                data={
                    "id": message.get("id"),
                    "from": format_people(message.get("from")),
                    "to": format_people(message.get("to")),
                    "subject": message.get("subject") or "",
                    "received_at": message.get("receivedAt"),
                    "preview": message.get("preview") or "",
                },
            )
            for message in messages
            if isinstance(message, dict)
        ]

    async def read_inbox(self) -> DataFrame:
        """Return the messages as a table with one row per message."""
        data = await self._messages()
        self.status = data
        return DataFrame(data)
