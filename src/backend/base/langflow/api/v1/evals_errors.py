from __future__ import annotations

import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, TypeVar

from fastapi import HTTPException, status

from langflow.services.database.lock_retry import is_database_lock_error, run_with_lock_retry
from langflow.services.evaluations.errors import (
    EvalsConflictError,
    EvalsDatabaseBusyError,
    EvalsNotFoundError,
    EvalsValidationError,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T")
DATABASE_BUSY = "The database is busy. Please retry the request."
# A snapshot conflict fails at once; an attempt that waited longer was held by another writer for the whole
# busy timeout, so trying again would only wait it out again.
LOCK_WAIT_GIVE_UP_SECONDS = 1.0


def _database_busy() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=DATABASE_BUSY, headers={"Retry-After": "1"}
    )


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
    except EvalsDatabaseBusyError as exc:
        raise _database_busy() from exc
    except Exception as exc:
        if not is_database_lock_error(exc):
            raise
        raise _database_busy() from exc


async def evals_write(session: AsyncSession, description: str, operation: Callable[[], Awaitable[T]]) -> T:
    """Run a read-then-write request again on SQLite lock contention (a running evaluation writes often)."""
    # A retry rolls the session back, which expires everything loaded in it, including the caller that
    # authentication loaded here; reading it again from async code then fails. Detached, it keeps its values.
    session.expunge_all()

    async def attempt(_attempt: int) -> T:
        started = time.monotonic()
        try:
            return await operation()
        except Exception as exc:
            if is_database_lock_error(exc) and time.monotonic() - started > LOCK_WAIT_GIVE_UP_SECONDS:
                # Unchained, so the retry loop does not read it as a lock error to try again.
                raise EvalsDatabaseBusyError(DATABASE_BUSY) from None
            raise

    return await run_with_lock_retry(attempt, session=session, description=description)
