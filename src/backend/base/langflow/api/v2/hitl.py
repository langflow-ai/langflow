"""Human-in-the-loop persistence + decision validation for the v2 workflows API.

The pause is stored as a chat message so the interactive card survives reload;
on resume the same message is updated with the chosen action so a reloaded
session renders it as resolved instead of re-offering the decision.
"""

from __future__ import annotations

import uuid
from uuid import UUID

from lfx.log import logger
from lfx.run.hitl import reroute_decision_on_timeout
from sqlalchemy.orm.attributes import flag_modified

from langflow.services.deps import get_job_service

__all__ = [
    "ensure_resume_execute_permission",
    "is_decision_allowed",
    "list_pending_human_requests",
    "mark_card_answered",
    "persist_human_input_card",
    "reroute_decision_on_timeout",
]


async def ensure_resume_execute_permission(current_user, flow_id: UUID) -> None:
    """Re-enforce flow:execute before applying a resume decision.

    Resume executes the remainder of the flow; job ownership alone is not enough —
    shared access revoked while the run was suspended must not let the decision through.
    """
    from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
    from langflow.services.authorization import FlowAction, ensure_flow_permission

    flow = await get_flow_by_id_or_endpoint_name(str(flow_id), current_user.id, widen_for_shares=True)
    await ensure_flow_permission(
        current_user,
        FlowAction.EXECUTE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=getattr(flow, "workspace_id", None),
        folder_id=getattr(flow, "folder_id", None),
    )


async def list_pending_human_requests(
    flow_id: UUID,
    user_id: UUID,
    *,
    request_end_user_id: str | None = None,
    include_all_end_users: bool = False,
) -> list[dict]:
    """Suspended HITL jobs for a flow + their pending request, for the Traces overlay.

    Traces and jobs are separate stores; the paused state lives on the SUSPENDED job, so
    the frontend correlates these to trace rows by ``session_id``.

    Serving-plane isolation (B1): this enumerates by flow_id and each row exposes the merged
    ``session_id`` + the HITL prompt, so rows are filtered to the requesting end user by the SAME
    rule the single-job guard uses (``_end_user_matches``). ``include_all_end_users`` bypasses the
    filter for a superuser. Default (feature off / anonymous) keeps only end-user-less jobs, which
    on an editor plane is every job — unchanged behavior.
    """
    from sqlmodel import select

    from langflow.api.v2.workflow import _end_user_matches
    from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        result = await session.exec(
            select(Job).where(
                Job.flow_id == flow_id,
                Job.user_id == user_id,
                Job.status == JobStatus.SUSPENDED,
                Job.type == JobType.WORKFLOW,
            )
        )
        jobs = list(result.all())

    pending: list[dict] = []
    for job in jobs:
        if not include_all_end_users and not _end_user_matches(request_end_user_id, job.job_metadata):
            continue
        request = await get_job_service().get_pending_human_request(job.job_id)
        if not request:
            continue
        session_id = ((job.job_metadata or {}).get("request") or {}).get("session_id")
        pending.append(
            {
                "job_id": str(job.job_id),
                "flow_id": str(job.flow_id),
                "session_id": session_id,
                "created_at": job.created_timestamp.isoformat() if job.created_timestamp else None,
                "request_id": request.get("request_id"),
                "kind": request.get("kind"),
                "prompt": request.get("prompt"),
                "options": request.get("options") or [],
                "allowed_decisions": request.get("allowed_decisions") or [],
            }
        )
    return pending


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
    from lfx.memory.flow_context import derive_message_owner_uuid
    from lfx.schema.content_block import ContentBlock
    from lfx.schema.content_types import HumanInputContent
    from lfx.schema.message import Message
    from lfx.workflow.end_user_identity import end_user_id_from_scoped_session

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
    # Stamp the serving-plane owner so this card is retrievable through the per-user monitor pull
    # (GET /monitor/messages?end_user_id=...). The card is built by hand and bypasses
    # Component._store_message, so without this it persists user_id=NULL and the owner's own pull
    # misses it (the pull's predicate is an exact owner match, so NULL never returns). The scoped
    # session carries the end user (<end_user>::<base>); resolve it through the same helpers the
    # component write path and the monitor read path use so write == read. None off / editor /
    # anonymous -> NULL, unchanged. See BUG-02.
    owner_end_user = end_user_id_from_scoped_session(session_id)
    owner_user_id = derive_message_owner_uuid(owner_end_user) if owner_end_user else None
    try:
        stored = await astore_message(
            message, flow_id=flow_id, run_id=str(job_id) if job_id else None, user_id=owner_user_id
        )
        if stored and job_id is not None:
            await get_job_service().update_job_metadata(uuid.UUID(str(job_id)), {"card_message_id": str(stored[0].id)})
    except Exception:  # noqa: BLE001
        await logger.awarning("Failed to persist human-input card for flow %s", flow_id, exc_info=True)


def _set_submitted_action(content_blocks: list, action_id: str | None, request_id: str | None = None) -> bool:
    """Stamp ``submitted_action`` on the card's content in place, preserving the rest.

    With ``request_id`` set, only a content whose ``request_id`` matches is stamped, so
    a decision can never resolve a different pause's card.
    """
    changed = False
    for block in content_blocks or []:
        contents = block.get("contents") if isinstance(block, dict) else getattr(block, "contents", None)
        for content in contents or []:
            is_dict = isinstance(content, dict)
            ctype = content.get("type") if is_dict else getattr(content, "type", None)
            if ctype != "human_input":
                continue
            card_request_id = content.get("request_id") if is_dict else getattr(content, "request_id", None)
            if request_id is not None and card_request_id != request_id:
                continue
            if is_dict:
                content["submitted_action"] = action_id
            else:
                content.submitted_action = action_id
            changed = True
    return changed


def _mark_superseded(content_blocks: list) -> bool:
    """Flag every still-open human_input content as superseded, in place."""
    changed = False
    for block in content_blocks or []:
        contents = block.get("contents") if isinstance(block, dict) else getattr(block, "contents", None)
        for content in contents or []:
            is_dict = isinstance(content, dict)
            ctype = content.get("type") if is_dict else getattr(content, "type", None)
            if ctype != "human_input":
                continue
            answered = content.get("submitted_action") if is_dict else getattr(content, "submitted_action", None)
            if answered is not None:
                continue
            if is_dict:
                content["superseded"] = True
            else:
                content.superseded = True
            changed = True
    return changed


async def mark_card_superseded(job_id: UUID) -> None:
    """Close the persisted card of a run cancelled by supersede/stop.

    Without this the reloaded card (no ``submitted_action``) turns interactive
    again and every click 409s against the cancelled job. Patched in place like
    ``mark_card_answered`` so prompt/options are preserved for the history.
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
            if _mark_superseded(message.content_blocks):
                flag_modified(message, "content_blocks")
                session.add(message)
    except Exception as _e:  # noqa: BLE001
        await logger.awarning("Failed to mark human-input card superseded for job %s: %r", job_id, _e)


async def mark_card_answered(job_id: UUID, request_id: str, decision: dict, *, card_message_id=None) -> None:
    """Record the chosen action on the persisted card message for ``job_id``.

    Patches the existing card in place so the prompt/options it was stored with are
    preserved — rebuilding from the suspend event would drop them. Callers should pass
    the ``card_message_id`` they read BEFORE enqueuing the continuation: the resumed run
    may reach another pause and overwrite job metadata, and the stamp must land on the
    answered card, not the new one (``request_id`` is enforced against the card content
    as a second guard).
    """
    from lfx.services.deps import session_scope

    from langflow.services.database.models.message.model import MessageTable

    if card_message_id is None:
        job = await get_job_service().get_job_by_job_id(job_id)
        card_message_id = (job.job_metadata or {}).get("card_message_id") if job else None
    if not card_message_id:
        return
    try:
        async with session_scope() as session:
            message = await session.get(MessageTable, UUID(str(card_message_id)))
            if message is None:
                return
            if _set_submitted_action(message.content_blocks, decision.get("action_id"), request_id):
                flag_modified(message, "content_blocks")
                session.add(message)
    except Exception as _e:  # noqa: BLE001
        await logger.awarning("Failed to mark human-input card answered for job %s: %r", job_id, _e)
