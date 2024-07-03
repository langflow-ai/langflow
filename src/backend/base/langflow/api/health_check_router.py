import uuid

from fastapi import Depends, APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session, select

from langflow.services.deps import (
    get_chat_service,
    get_session,
    get_variable_service,
)
from langflow.services.database.models.flow import Flow
from langflow.services.variable.service import VariableService, GENERIC_TYPE
from langflow.services.database.models.folder.utils import create_default_folder_if_it_doesnt_exist


health_check_router = APIRouter(tags=["Health Check"])


class HealthResponse(BaseModel):
    status: str = "nok"
    chat: str = "error"
    db: str = "error"
    folder: str = "error"
    variables: str = "error"

    def has_error(self) -> bool:
        return any(v == "error" for v in self.model_dump().values())


# /health is also supported by uvicorn
# it means uvicorn's /health serves first before the langflow instance is up
# therefore it's not a reliable health check for a langflow instance
# we keep this for backward compatibility
@health_check_router.get("/health")
async def health():
    return {"status": "ok"}


# /health_check evaluates key services
# It's a reliable health check for a langflow instance
@health_check_router.get("/health_check", response_model=HealthResponse)
async def health_check(
    session: Session = Depends(get_session),
    variable_service: VariableService = Depends(get_variable_service),
):
    response = HealthResponse()
    test_id = uuid.uuid4()
    try:
        # Check database to query a bogus flow
        stmt = select(Flow).where(Flow.id == test_id)
        session.exec(stmt).first()
        response.db = "ok"
    except Exception as e:
        logger.exception(e)

    try:
        chat = get_chat_service()
        await chat.set_cache("health_check", str(test_id))
        if v := await chat.get_cache("health_check"):
            if v.get("result") == str(test_id):
                response.chat = "ok"
            else:
                logger.error("chat service get incorrect value")
    except Exception as e:
        logger.exception(e)

    # use the same uuid for user_id for testing purpose
    user_id = "da93c2bd-c857-4b10-8c8c-60988103320f"
    try:
        variable_service.initialize_user_variables(user_id, session)
        variable_service.create_variable(
            user_id=user_id,
            name="health_check_test",
            value="ok",
            default_fields=[],
            _type=GENERIC_TYPE,
            session=session,
        )
        variable_service.delete_variable(user_id=user_id, name="health_check_test", session=session)
        response.variables = "ok"
    except Exception as e:
        logger.exception(e)

    try:
        create_default_folder_if_it_doesnt_exist(session, uuid.UUID(user_id))
        response.folder = "ok"
    except Exception as e:
        logger.exception(e)

    if response.has_error():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response.model_dump())
    else:
        response.status = "ok"
        return response
