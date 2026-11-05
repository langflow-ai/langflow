from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, TypeVar

from fastapi import HTTPException, status

from langflow.services.database.lock_retry import is_database_lock_error, run_with_lock_retry
from langflow.services.evaluations.errors import (
    EvalsConflictError,
    EvalsNotFoundError,
    EvalsValidationError,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T")
DATABASE_BUSY = "The database is busy. Please retry the request."


@asynccontextmanager
async def evals_http_errors() -> AsyncGenerator[None, None]:
    """Map Evals domain errors to HTTP statuses; anything else propagates unchanged."""
    try:
        yield
    except EvalsNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EvalsConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EvalsValidationError as exc:
        detail: object = str(exc)
        issues = getattr(exc, "issues", None)
        if issues:
            detail = {"message": str(exc), "issues": issues}
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    except Exception as exc:
        if not is_database_lock_error(exc):
            raise
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=DATABASE_BUSY, headers={"Retry-After": "1"}
        ) from exc


async def evals_write(session: AsyncSession, description: str, operation: Callable[[], Awaitable[T]]) -> T:
    """Run a read-then-write request again on SQLite lock contention (a running evaluation writes often)."""
    return await run_with_lock_retry(lambda _attempt: operation(), session=session, description=description)
