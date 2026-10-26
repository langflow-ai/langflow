from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import HTTPException, status

from langflow.services.evaluations.errors import (
    EvalsConflictError,
    EvalsNotFoundError,
    EvalsValidationError,
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
