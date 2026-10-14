"""Helpers shared by the admin and self-service data subject routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from lfx.services.settings.feature_flags import FEATURE_FLAGS

from langflow.api.utils.core import build_content_disposition
from langflow.services.data_subjects.schemas import DataSubjectRequestRead
from langflow.services.database.models.data_subject_request import CLOSED_STATUSES

if TYPE_CHECKING:
    from collections.abc import Iterator
    from tempfile import SpooledTemporaryFile

    from langflow.services.data_subjects.errors import DataSubjectError
    from langflow.services.database.models.data_subject_request import DataSubjectRequest

ERROR_CODE_HEADER = "X-Langflow-Error-Code"
STREAM_CHUNK_BYTES = 64 * 1024


def require_data_subject_feature() -> None:
    """Answer 404 while the feature flag is off, so the routes look unmounted."""
    if not FEATURE_FLAGS.data_subject_requests:
        raise HTTPException(status_code=404, detail="Not Found")


def to_http_error(exc: DataSubjectError) -> HTTPException:
    return HTTPException(
        status_code=int(exc.status_code),
        detail={"code": exc.code, "message": exc.message, **exc.details},
        headers={ERROR_CODE_HEADER: exc.code},
    )


def request_read(request: DataSubjectRequest) -> DataSubjectRequestRead:
    due_at = request.due_at if request.due_at.tzinfo else request.due_at.replace(tzinfo=timezone.utc)
    overdue = request.status not in {s.value for s in CLOSED_STATUSES} and due_at < datetime.now(timezone.utc)
    return DataSubjectRequestRead.model_validate({**request.model_dump(), "overdue": overdue})


def _chunks(archive: SpooledTemporaryFile) -> Iterator[bytes]:
    try:
        while chunk := archive.read(STREAM_CHUNK_BYTES):
            yield chunk
    finally:
        archive.close()


def zip_response(archive: SpooledTemporaryFile, filename: str) -> StreamingResponse:
    return StreamingResponse(
        _chunks(archive),
        media_type="application/zip",
        headers={"Content-Disposition": build_content_disposition(filename)},
    )
