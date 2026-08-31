import asyncio
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, HTTPException, status
from lfx.log.logger import logger
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils import DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_chat_service, get_settings_service

health_check_router = APIRouter(tags=["Health Check"])

# Enterprise readiness check registry.  Enterprise plugins append async
# callables here at plugin-registration time (before any request is served).
# Each callable returns a (name, status) tuple where status is "ok" or a
# string starting with "error:".  The /healthz handler loops over all
# registered checks and returns HTTP 503 if any check reports an error.
# An empty registry (the OSS default) leaves /healthz behaviour unchanged.
_enterprise_readiness_checks: list[Callable[[], Awaitable[tuple[str, str]]]] = []

# use a fixed valid UUId that UUID collision is very unlikely
_HEALTH_CHECK_PROBE_KEY = "da93c2bd-c857-4b10-8c8c-60988103320f"


class HealthResponse(BaseModel):
    status: str = "nok"
    chat: str = "error check the server logs"
    db: str = "error check the server logs"
    """
    Do not send exceptions and detailed error messages to the client because it might contain credentials and other
    sensitive server information.
    """

    def has_error(self) -> bool:
        return any(v.startswith("error") for v in self.model_dump().values())


async def _probe_services(session: DbSession) -> HealthResponse:
    """Run DB and chat-service liveness probes and return a populated HealthResponse."""
    response = HealthResponse()
    try:
        # Check database to query a bogus flow
        stmt = select(Flow).where(Flow.id == uuid.uuid4())
        (await session.exec(stmt)).first()
        response.db = "ok"
    except Exception:  # noqa: BLE001
        await logger.aexception("Error checking database")

    try:
        chat = get_chat_service()
        await chat.set_cache("health_check", _HEALTH_CHECK_PROBE_KEY)
        await chat.get_cache("health_check")
        response.chat = "ok"
    except Exception:  # noqa: BLE001
        await logger.aexception("Error checking chat service")

    return response


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
    response = await _probe_services(session)
    if response.has_error():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response.model_dump())
    response.status = "ok"
    return response


# /healthz is the Kubernetes-style readiness probe endpoint.
# In addition to the OSS service checks it runs all enterprise readiness
# checks registered in _enterprise_readiness_checks.  A single "error:"
# result from any registered check causes a 503 response so the pod is
# marked Unready without requiring a restart.
@health_check_router.get("/healthz")
async def healthz(
    session: DbSession,
) -> HealthResponse:
    response = await _probe_services(session)

    check_timeout: float = get_settings_service().settings.worker_timeout
    for check in _enterprise_readiness_checks:
        check_name = getattr(check, "__qualname__", type(check).__name__)
        try:
            _name, result = await asyncio.wait_for(check(), timeout=check_timeout)
            if result.startswith("error:"):
                await logger.awarning("Enterprise readiness check %s returned error result", check_name)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service unavailable",
                )
        except HTTPException:
            raise
        # asyncio.TimeoutError is a subclass of TimeoutError since 3.11;
        # both listed for Python 3.10 compatibility.
        except (TimeoutError, asyncio.TimeoutError) as exc:
            await logger.awarning("Enterprise readiness check %s timed out after %ss", check_name, check_timeout)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            await logger.awarning("Enterprise readiness check %s raised unexpectedly: %s", check_name, exc)

    if response.has_error():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response.model_dump())
    response.status = "ok"
    return response
