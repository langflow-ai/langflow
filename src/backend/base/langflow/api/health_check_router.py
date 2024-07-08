import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session, select

from langflow.services.database.models.flow import Flow
from langflow.services.deps import get_chat_service, get_session

health_check_router = APIRouter(tags=["Health Check"])


class HealthResponse(BaseModel):
    status: str = "nok"
    chat: str = "error check the server logs"
    db: str = "error check the server logs"
    """
    Do not send exceptions and detailed error messages to the client because it might contain credentials and other sensitive server information.
    """

    def has_error(self) -> bool:
        return any(v.startswith("error") for v in self.model_dump().values())


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
):
    response = HealthResponse()
    # use a fixed valid UUId that UUID collision is very unlikely
    user_id = "da93c2bd-c857-4b10-8c8c-60988103320f"
    try:
        # Check database to query a bogus flow
        stmt = select(Flow).where(Flow.id == uuid.uuid4())
        session.exec(stmt).first()
        response.db = "ok"
    except Exception as e:
        logger.exception(e)

    try:
        chat = get_chat_service()
        await chat.set_cache("health_check", str(user_id))
        await chat.get_cache("health_check")
        response.chat = "ok"
    except Exception as e:
        logger.exception(e)

    if response.has_error():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response.model_dump())
    else:
        response.status = "ok"
        return response
