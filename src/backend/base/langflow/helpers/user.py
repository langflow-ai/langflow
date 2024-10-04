from uuid import UUID

from fastapi import HTTPException
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_db_service


def get_user_by_flow_id_or_endpoint_name(flow_id_or_name: str) -> UserRead | None:
    with get_db_service().with_session() as session:
        try:
            flow_id = UUID(flow_id_or_name)
            flow = session.get(Flow, flow_id)
        except ValueError:
            stmt = select(Flow).where(Flow.endpoint_name == flow_id_or_name)
            flow = session.exec(stmt).first()

        if flow is None:
            raise HTTPException(status_code=404, detail=f"Flow identifier {flow_id_or_name} not found")

        user = session.get(User, flow.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User for flow {flow_id_or_name} not found")

        return UserRead.model_validate(user, from_attributes=True)
