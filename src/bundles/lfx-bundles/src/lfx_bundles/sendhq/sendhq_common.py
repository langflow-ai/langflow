"""Shared HTTP and response shaping for the SendHQ components.

Every SendHQ component talks to the same REST API with the same bearer key and
error envelope, and returns emails in the same trimmed shape, so those concerns
live here rather than being re-derived in each component.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

BASE_URL = "https://sendhq.cc/api/v1"
TIMEOUT_SECONDS = 30.0
# Bodies are cut so a flow or an agent's context is not flooded by one message;
# the full message stays available through the API.
MAX_BODY_CHARS = 20_000
SNIPPET_CHARS = 200


def path_id(value: str) -> str:
    """Encode an ID as one URL path segment so it cannot change the request path."""
    if value in {".", ".."}:
        return value.replace(".", "%2E")
    return quote(value, safe="")


def split_addresses(value: str | None) -> list[str]:
    """Split a comma- or newline-separated list of addresses."""
    return [part.strip() for part in (value or "").replace("\n", ",").split(",") if part.strip()]


def _error(response: httpx.Response) -> dict[str, Any]:
    """Flatten SendHQ's `{"error": {"message", "status"}}` envelope.

    Some errors also carry `code`, `explanation` and `remedy`, which are kept so a
    flow (or an agent) can act on the reason.
    """
    try:
        body = response.json()
    except ValueError:
        body = {"error": response.text[:500]}
    error = body.get("error") if isinstance(body, dict) else None
    details = error if isinstance(error, dict) else {}
    message = details.get("message") if details else error
    result: dict[str, Any] = {"error": message or f"HTTP {response.status_code}", "status": response.status_code}
    for key in ("code", "explanation", "remedy"):
        if details.get(key):
            result[key] = details[key]
    return result


async def request(
    api_key: str,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Call the SendHQ API and return (ok, data).

    Success is reported separately from the payload because every email object
    carries its own `error` field (null unless delivery failed), so the presence
    of `error` in a payload says nothing about whether the request worked.
    """
    if not api_key:
        return False, {"error": "No SendHQ API key provided."}
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "langflow-sendhq"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.request(method, f"{BASE_URL}{path}", headers=headers, json=json, params=params)
    except httpx.HTTPError as e:
        return False, {"error": f"Request to SendHQ failed: {e}"}
    if response.is_error:
        return False, _error(response)
    try:
        data = response.json()
    except ValueError:
        return False, {"error": "SendHQ returned a response that is not JSON.", "status": response.status_code}
    return True, data if isinstance(data, dict) else {"data": data}


def summary(email: dict[str, Any]) -> dict[str, Any]:
    """An email without its body or raw MIME, for lists."""
    text = (email.get("text") or "").strip()
    result: dict[str, Any] = {
        "id": email.get("id"),
        "thread_id": email.get("threadId"),
        "direction": email.get("direction"),
        "status": email.get("status"),
        "from": email.get("from"),
        "to": email.get("to"),
        "subject": email.get("subject"),
        "snippet": text[:SNIPPET_CHARS],
        "unread": email.get("unread"),
        "category": email.get("category"),
        "attachment_count": email.get("attachmentCount"),
        "created_at": email.get("createdAt"),
    }
    if email.get("error"):
        # Why SendHQ could not deliver this message, e.g. a rejected recipient.
        result["delivery_error"] = email["error"]
    return result


def detail(email: dict[str, Any]) -> dict[str, Any]:
    """An email with its body (text, else HTML) and attachment names."""
    result = summary(email)
    result.pop("snippet")
    body = email.get("text") or email.get("html") or ""
    result["cc"] = email.get("cc")
    result["reply_to"] = email.get("replyTo")
    result["body"] = body[:MAX_BODY_CHARS]
    if len(body) > MAX_BODY_CHARS:
        result["body_truncated"] = True
    result["attachments"] = [
        {"id": item.get("id"), "filename": item.get("filename"), "size_bytes": item.get("sizeBytes")}
        for item in email.get("attachments") or []
    ]
    return result


def reply_route(parent: dict[str, Any], from_email: str | None) -> tuple[str | None, list[str], str]:
    """Sender, recipients and subject for a reply to `parent`.

    A reply to received mail goes back to its sender (or Reply-To); a follow-up to
    sent mail goes to the same recipients. It is sent from `from_email` when set,
    or else from the address that received (or sent) the original.
    """
    if parent.get("direction") == "in":
        recipients = [parent.get("replyTo") or parent.get("from")]
        sender = from_email or next(iter(parent.get("to") or []), None)
    else:
        recipients = list(parent.get("to") or [])
        sender = from_email or parent.get("from")
    subject = parent.get("subject") or ""
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}".strip()
    return sender, [recipient for recipient in recipients if recipient], subject
