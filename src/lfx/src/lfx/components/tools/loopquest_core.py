"""Pure helpers for the LoopQuest Langflow component — no Langflow imports, so
they can be unit-tested in isolation.
"""

from __future__ import annotations


def build_task_body(
    *,
    content: str,
    module: str = "swiper",
    mode: str = "gate",
    title: str | None = None,
    claim: str | None = None,
    source: str | None = None,
    timeout_seconds: int | None = None,
    on_timeout: str | None = "escalate",
    review_source: str = "langflow",
) -> dict:
    """Build the POST /api/v1/tasks body from the tool call + component config."""
    payload: dict = {"content": content, "body": content}
    if claim:
        payload["claim"] = claim
    if source:
        payload["source"] = source

    body: dict = {
        "module": module or "swiper",
        "mode": mode or "gate",
        "payload": payload,
        "card": {"title": title or "Review", "body": content},
        "source": review_source,
    }
    if timeout_seconds:
        body["timeout_seconds"] = timeout_seconds
    if on_timeout:
        body["on_timeout"] = on_timeout
    return body


def verdict_to_string(task: dict) -> str | None:
    """Turn a polled task into a human-readable verdict, or None while pending."""
    status = task.get("status")
    if status == "reviewed":
        verdict = task.get("verdict")
        decision = "APPROVED" if verdict is True else "FLAGGED" if verdict is False else "RESOLVED"
        parts = [f"Human review {decision}"]
        if task.get("verdict_choice"):
            parts.append(f"choice: {task['verdict_choice']}")
        if task.get("verdict_reason"):
            parts.append(f"reason: {task['verdict_reason']}")
        if task.get("timed_out"):
            parts.append("(auto-resolved on timeout)")
        return " · ".join(parts)
    if status == "escalated":
        return "Human review ESCALATED — no automatic verdict; a person will follow up."
    return None
