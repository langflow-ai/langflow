import uuid

from fastapi import APIRouter, HTTPException, status

# Try to import from lfx, fallback to async-compatible wrapper if unavailable
try:
    from lfx.log.logger import logger
except ImportError:
    import logging
    from typing import Any

    class _AsyncLogger:
        """Async-compatible wrapper over standard logging.Logger.

        Provides awaitable methods used in this module (e.g., aexception, ainfo)
        to avoid attribute errors when lfx logger is not installed.
        """

        def __init__(self, base: logging.Logger) -> None:
            self._base = base

        # Pass-through for unknown attributes (sync logging API)
        def __getattr__(self, name: str) -> Any:  # pragma: no cover - thin shim
            return getattr(self._base, name)

        async def aexception(self, msg: str, *args: Any, **kwargs: Any) -> None:
            self._base.exception(msg, *args, **kwargs)

        async def ainfo(self, msg: str, *args: Any, **kwargs: Any) -> None:
            self._base.info(msg, *args, **kwargs)

    logger = _AsyncLogger(logging.getLogger(__name__))
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils import DbSession
from langflow.services.cache.utils import is_rich_pickle_enabled, validate_rich_pickle_support
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_chat_service

health_check_router = APIRouter(tags=["Health Check"])


class HealthResponse(BaseModel):
    status: str = "nok"
    chat: str = "error check the server logs"
    db: str = "error check the server logs"
    rich_pickle: str = "not_checked"
    """
    Do not send exceptions and detailed error messages to the client because it might contain credentials and other
    sensitive server information.
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
@health_check_router.get("/health_check")
async def health_check(
    session: DbSession,
) -> HealthResponse:
    response = HealthResponse()
    # use a fixed valid UUId that UUID collision is very unlikely
    user_id = "da93c2bd-c857-4b10-8c8c-60988103320f"
    try:
        # Check database to query a bogus flow
        stmt = select(Flow).where(Flow.id == uuid.uuid4())
        (await session.exec(stmt)).first()
        response.db = "ok"
    except Exception:  # noqa: BLE001
        await logger.aexception("Error checking database")

    try:
        chat = get_chat_service()
        await chat.set_cache("health_check", str(user_id))
        await chat.get_cache("health_check")
        response.chat = "ok"
    except Exception:  # noqa: BLE001
        await logger.aexception("Error checking chat service")

    # Check Rich pickle support status
    try:
        if is_rich_pickle_enabled():
            if validate_rich_pickle_support():
                response.rich_pickle = "ok"
            else:
                response.rich_pickle = "enabled_but_validation_failed"
        else:
            response.rich_pickle = "not_enabled"
    except Exception:  # noqa: BLE001
        await logger.aexception("Error checking Rich pickle support")
        response.rich_pickle = "error check the server logs"

    if response.has_error():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response.model_dump())
    response.status = "ok"
    return response
