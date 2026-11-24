from uuid import UUID

from fastapi import HTTPException
from lfx.services.deps import session_scope_readonly
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User, UserRead


async def get_user_by_flow_id_or_endpoint_name(flow_id_or_name: str, user_id: str | UUID | None = None) -> UserRead:
    async with session_scope_readonly() as session:
        # Pre-resolve user_id and catch malformed IDs to prevent 500s
        uuid_user_id: UUID | None = None
        if user_id is not None:
            try:
                uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            except (ValueError, AttributeError) as exc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Flow identifier {flow_id_or_name} not found",
                ) from exc

        try:
            flow_id = UUID(flow_id_or_name)
            flow = await session.get(Flow, flow_id)
        except ValueError:
            stmt = select(Flow).where(Flow.endpoint_name == flow_id_or_name)
            if uuid_user_id is not None:
                stmt = stmt.where(Flow.user_id == uuid_user_id)
            flow = (await session.exec(stmt)).first()

        # Enforce ownership check for both UUID and endpoint_name lookups
        if flow and uuid_user_id and flow.user_id != uuid_user_id:
            flow = None

        if flow is None:
            raise HTTPException(status_code=404, detail=f"Flow identifier {flow_id_or_name} not found")

        user = await session.get(User, flow.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User for flow {flow_id_or_name} not found")

        return UserRead.model_validate(user, from_attributes=True)
