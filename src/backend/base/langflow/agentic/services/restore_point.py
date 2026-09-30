"""Assistant restore points built on the existing flow-versioning system.

Before an assistant turn that can mutate the canvas, the current flow state
is snapshotted as a regular ``FlowVersion`` row so the user can restore it
from the existing versions UI (or a future "revert" affordance fed by the
``restore_version_id`` field on the SSE ``complete`` event).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from lfx.log.logger import logger

RESTORE_POINT_DESCRIPTION_PREFIX = "assistant-pre-edit"


def _restore_point_description() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"{RESTORE_POINT_DESCRIPTION_PREFIX} {timestamp}"


async def create_restore_point(flow_id: str | None, user_id: str | None) -> str | None:
    """Snapshot the flow's current state; best-effort, never raises.

    Returns the version id as a string, the latest existing version's id when
    it already matches the canvas (no duplicate spam), or ``None`` when there
    is nothing to snapshot (missing/invalid ids, unowned flow, empty canvas)
    or versioning failed — a restore point must never break the turn.
    """
    if not flow_id or not user_id:
        return None
    try:
        flow_uuid = UUID(flow_id)
        user_uuid = UUID(user_id)
    except ValueError:
        logger.debug("assistant.restore_point.skipped: flow_id/user_id is not a valid UUID")
        return None

    try:
        # Lazy imports mirror _get_current_flow_summary — the agentic layer
        # must not hard-depend on the DB models at import time.
        from lfx.services.deps import session_scope
        from sqlmodel import col, select

        from langflow.services.database.models.flow import Flow
        from langflow.services.database.models.flow_version.crud import create_flow_version_entry
        from langflow.services.database.models.flow_version.model import FlowVersion

        async with session_scope() as session:
            flow = await session.get(Flow, flow_uuid)
            if flow is None or not flow.data:
                return None
            if flow.user_id is not None and flow.user_id != user_uuid:
                logger.warning(
                    "assistant.restore_point.ownership_denied",
                    extra={"flow_id": flow_id, "user_id": user_id},
                )
                return None
            data = flow.data
            if not data.get("nodes") and not data.get("edges"):
                return None

            latest = (
                await session.exec(
                    select(FlowVersion)
                    .where(FlowVersion.flow_id == flow_uuid)
                    .order_by(col(FlowVersion.version_number).desc())
                    .limit(1)
                )
            ).first()
            if latest is not None and latest.data == data:
                return str(latest.id)

            entry = await create_flow_version_entry(
                session,
                flow_uuid,
                user_uuid,
                data=data,
                description=_restore_point_description(),
            )
            return str(entry.id)
    except Exception as exc:  # noqa: BLE001 — a restore point must never break the turn
        logger.warning("assistant.restore_point.failed flow_id=%s: %s", flow_id, exc)
        return None
