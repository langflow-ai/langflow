"""Translate flow payload validation into actionable HTTP errors."""

from fastapi import HTTPException
from pydantic import ValidationError

from langflow.api.validation_errors import redact_validation_errors


def flow_validation_error(exc: ValidationError) -> HTTPException:
    """Keep field details without exposing the submitted graph or a model dump."""
    errors = redact_validation_errors(exc.errors())
    for error in errors:
        error["msg"] = error["msg"].removeprefix("Value error, ")
    return HTTPException(status_code=422, detail=errors)
