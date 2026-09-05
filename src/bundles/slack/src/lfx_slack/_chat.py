"""Shared ``chat.postMessage`` payload helpers.

``Slack: Send Message (as user)`` and ``Slack: Post Message (as app)`` call the
same Web API method with the same body; only the executing identity and the
matrix-declared input set differ.  The request assembly lives here so the two
components cannot drift.
"""

from __future__ import annotations

from typing import Any

from lfx.schema.data import Data

API_METHOD = "chat_postMessage"

# chat.postMessage truncates at 40,000 characters. Rejecting locally keeps the
# provider error from being the first signal that a prompt overflowed.
MAX_TEXT_CHARACTERS = 40_000


def as_json_list(value: Any) -> list[dict[str, Any]] | None:
    """Normalize a Data / list[Data] / list[dict] input into Slack JSON.

    An unset optional ``DataInput`` arrives as an empty string or an empty
    list, so falsy values and falsy list items are dropped rather than
    rejected.
    """
    if not value:
        return None
    items = value if isinstance(value, list) else [value]
    blocks: list[dict[str, Any]] = []
    for item in items:
        if not item:
            continue
        if isinstance(item, Data):
            blocks.append(dict(item.data))
        elif isinstance(item, dict):
            blocks.append(dict(item))
        else:
            msg = f"Slack blocks and attachments must be Data or dict objects; got {type(item).__name__}."
            raise TypeError(msg)
    return blocks or None


def post_message_payload(
    *,
    channel: str,
    text: str,
    thread_ts: str | None = None,
    reply_broadcast: bool | None = None,
    blocks: Any = None,
    attachments: Any = None,
    unfurl_links: bool | None = None,
) -> dict[str, Any]:
    """Validate the shared inputs and build the Web API request body."""
    channel = (channel or "").strip()
    if not channel:
        msg = "Channel is required."
        raise ValueError(msg)
    if not text:
        msg = "Message text is required."
        raise ValueError(msg)
    if len(text) > MAX_TEXT_CHARACTERS:
        msg = f"Message text is {len(text)} characters; Slack truncates above {MAX_TEXT_CHARACTERS}."
        raise ValueError(msg)

    payload: dict[str, Any] = {"channel": channel, "text": text}
    thread = (thread_ts or "").strip()
    if thread:
        payload["thread_ts"] = thread
    if reply_broadcast:
        payload["reply_broadcast"] = True
    block_list = as_json_list(blocks)
    if block_list:
        payload["blocks"] = block_list
    attachment_list = as_json_list(attachments)
    if attachment_list:
        payload["attachments"] = attachment_list
    if unfurl_links is not None:
        payload["unfurl_links"] = bool(unfurl_links)
    return payload


def message_result(body: dict[str, Any]) -> Data:
    """Shape a ``chat.postMessage`` response into the component's Data output."""
    return Data(
        data={
            "channel": body.get("channel"),
            "ts": body.get("ts"),
            "message": body.get("message", {}),
        }
    )
