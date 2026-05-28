from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel import col, select

from langflow.services.database.models.flow_operation.model import FlowOperation, FlowOperationActorDelegate

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def create_flow_operation(
    session: AsyncSession,
    *,
    flow_id: UUID,
    protocol_version: int,
    revision: int,
    client_id: str,
    actor_user_id: UUID,
    actor_delegate: FlowOperationActorDelegate,
    forward_ops: list[dict[str, Any]],
    backward_ops: list[dict[str, Any]],
) -> FlowOperation:
    """Persist an accepted operation batch row.

    ``actor_user_id`` must be the authenticated user that initiated the operation,
    including agent operations started by a user. ``actor_delegate`` distinguishes
    direct edits (``self``) from agent-mediated edits (``agent``). ``actor_user_id``
    is nullable on the model only so existing operation rows survive user deletion
    via ``ON DELETE SET NULL``.

    This helper does not authenticate, authorize, or verify that ``actor_user_id``
    may write to ``flow_id``. Callers must derive it from authentication, then
    load the flow and run the appropriate authorization guard before creating an
    operation row.
    """
    entry = FlowOperation(
        flow_id=flow_id,
        protocol_version=protocol_version,
        revision=revision,
        client_id=client_id,
        actor_user_id=actor_user_id,
        actor_delegate=actor_delegate,
        forward_ops=forward_ops,
        backward_ops=backward_ops,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def get_flow_operation_by_revision(
    session: AsyncSession,
    flow_id: UUID,
    revision: int,
) -> FlowOperation | None:
    """Return an operation row by flow/revision.

    Callers are responsible for flow visibility checks before exposing the row.
    """
    result = await session.exec(
        select(FlowOperation).where(FlowOperation.flow_id == flow_id, FlowOperation.revision == revision)
    )
    return result.first()


async def list_flow_operations_after_revision(
    session: AsyncSession,
    flow_id: UUID,
    after_revision: int,
    *,
    page_size: int,
) -> list[FlowOperation]:
    """Return one page of accepted operations with revision strictly greater than ``after_revision``.

    ``page_size`` is supplied by the API layer (default/max validation belong there, not in CRUD).
    Callers are responsible for flow visibility checks before exposing rows.
    """
    stmt = (
        select(FlowOperation)
        .where(FlowOperation.flow_id == flow_id, FlowOperation.revision > after_revision)
        .order_by(col(FlowOperation.revision).asc())
        .limit(page_size)
    )
    return list((await session.exec(stmt)).all())
