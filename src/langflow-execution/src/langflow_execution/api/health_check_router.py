from fastapi import APIRouter
from pydantic import BaseModel

health_check_router = APIRouter(tags=["Health Check"])


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


# /health is also supported by uvicorn
# it means uvicorn's /health serves first before the langflow instance is up
# therefore it's not a reliable health check for a langflow instance
# we keep this for backward compatibility
@health_check_router.get("/health")
async def health():
    return {"status": "ok"}
