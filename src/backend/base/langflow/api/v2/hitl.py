"""Human-in-the-loop persistence + decision validation for the v2 workflows API.

The pause is stored as a chat message so the interactive card survives reload;
on resume the same message is updated with the chosen action so a reloaded
session renders it as resolved instead of re-offering the decision.
"""

from __future__ import annotations

import uuid
from uuid import UUID

from lfx.log import logger
from sqlalchemy.orm.attributes import flag_modified

from langflow.services.deps import get_job_service


async def is_decision_allowed(job_id: UUID, decision: dict) -> bool:
    """Whether ``decision.action_id`` is one of the pause's allowed decisions.

    Returns True when there is no pending request constraining the choice (nothing
    to enforce); otherwise the chosen action must be in ``allowed_decisions``.
    """
    pending = await get_job_service().get_pending_human_request(job_id)
    allowed = (pending or {}).get("allowed_decisions") or []
    if not allowed:
        return True
    return decision.get("action_id") in allowed


async def persist_human_input_card(data: dict, flow_id: uuid.UUID, session_id: str, job_id) -> None:
    """Persist the pause as a chat message so the interactive card survives reload.

    The card carries request_id + job_id, so a reloaded session can resume the run.
    Records the card's message id in job metadata so resume can mark it answered.
    """
    from lfx.schema.content_block import ContentBlock
    from lfx.schema.content_types import HumanInputContent
    from lfx.schema.message import Message

    from langflow.memory import astore_message

    content = HumanInputContent(
        request_id=data.get("request_id", ""),
        job_id=str(job_id) if job_id else None,
        kind=data.get("kind", "node_input"),
        prompt=data.get("prompt"),
        options=data.get("options") or [],
        fields=data.get("schema") or [],
        allowed_decisions=data.get("allowed_decisions") or [],
    )
    block = ContentBlock(title="Human input required", contents=[content])
    message = Message(
        text="",
        sender="Machine",
        sender_name="AI",
        session_id=session_id,
        flow_id=flow_id,
        content_blocks=[block],
    )
    try:
        stored = await astore_message(message, flow_id=flow_id, run_id=str(job_id) if job_id else None)
        if stored and job_id is not None:
            await get_job_service().update_job_metadata(uuid.UUID(str(job_id)), {"card_message_id": str(stored[0].id)})
    except Exception:  # noqa: BLE001
        await logger.awarning("Failed to persist human-input card for flow %s", flow_id, exc_info=True)


def _set_submitted_action(content_blocks: list, action_id: str | None) -> bool:
    """Stamp ``submitted_action`` on the card's content in place, preserving the rest."""
    changed = False
    for block in content_blocks or []:
        contents = block.get("contents") if isinstance(block, dict) else getattr(block, "contents", None)
        for content in contents or []:
            ctype = content.get("type") if isinstance(content, dict) else getattr(content, "type", None)
            if ctype != "human_input":
                continue
            if isinstance(content, dict):
                content["submitted_action"] = action_id
            else:
                content.submitted_action = action_id
            changed = True
    return changed


async def mark_card_answered(job_id: UUID, request_id: str, decision: dict) -> None:  # noqa: ARG001
    """Record the chosen action on the persisted card message for ``job_id``.

    Patches the existing card in place so the prompt/options it was stored with are
    preserved — rebuilding from the suspend event would drop them.
    """
    from lfx.services.deps import session_scope

    from langflow.services.database.models.message.model import MessageTable

    job = await get_job_service().get_job_by_job_id(job_id)
    card_message_id = (job.job_metadata or {}).get("card_message_id") if job else None
    if not card_message_id:
        return
    try:
        async with session_scope() as session:
            message = await session.get(MessageTable, UUID(str(card_message_id)))
            if message is None:
                return
            if _set_submitted_action(message.content_blocks, decision.get("action_id")):
                flag_modified(message, "content_blocks")
                session.add(message)
    except Exception as _e:  # noqa: BLE001
        await logger.awarning("Failed to mark human-input card answered for job %s: %r", job_id, _e)
