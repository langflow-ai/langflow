"""Human-in-the-loop persistence helpers for the v2 workflows API.

The pause is stored as a chat message so the interactive card survives reload;
on resume the same message is updated with the chosen action so a reloaded
session renders it as resolved instead of re-offering the decision.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm.attributes import flag_modified

from langflow.services.deps import get_job_service
from lfx.log import logger


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
    from langflow.services.database.models.message.model import MessageTable
    from lfx.services.deps import session_scope

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
