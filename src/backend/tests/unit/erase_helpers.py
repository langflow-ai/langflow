import asyncio
from uuid import UUID

from langflow.services.database.models.data_subject_request import DataSubjectRequest, DataSubjectRequestStatus
from langflow.services.deps import session_scope

POLL_SECONDS = 0.1


async def wait_for_erase(request_id: str | UUID, *, timeout: float = 30.0) -> DataSubjectRequest:
    """Wait for the background worker to finish a deletion started with ``DELETE /users/{id}`` (202)."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        async with session_scope() as session:
            request = await session.get(DataSubjectRequest, UUID(str(request_id)))
            if request is not None and request.status == DataSubjectRequestStatus.DONE.value:
                return request
            if request is not None and (request.error or {}).get("attempts"):
                msg = f"Erase failed: {request.error}"
                raise AssertionError(msg)
        if asyncio.get_running_loop().time() > deadline:
            msg = f"Erase {request_id} did not finish in {timeout}s"
            raise AssertionError(msg)
        await asyncio.sleep(POLL_SECONDS)
