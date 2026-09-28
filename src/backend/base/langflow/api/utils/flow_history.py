"""HTTP responses for flow history outcomes."""

from __future__ import annotations

from fastapi import HTTPException, status
from lfx.log.logger import logger

from langflow.services.database.models.flow.model import FlowHistoryWrite
from langflow.services.flow_history.errors import (
    FlowGraphInvalidError,
    FlowHistoryCorruptionError,
    FlowHistoryError,
    FlowRevisionMismatchError,
    FlowRevisionNotFoundError,
    FlowRevisionNotRetainedError,
    FlowVersionConflictError,
)
from langflow.services.flow_history.recorder import GraphWriteResult

HISTORY_FAILURE_MESSAGE = "The flow's history could not be read or recorded. The change was not saved."


def history_http_error(exc: FlowHistoryError) -> HTTPException:
    """Translate a history error into the response a client can act on.

    A mismatch and an invalid graph each carry a stable code and the flag that
    resolves them. Damaged history is logged with where it was found, never
    with graph values, and reported without detail.
    """
    if isinstance(exc, FlowVersionConflictError):
        # Imported here: importing the v1 routes package from this module is circular.
        from langflow.api.v1.flow_conflict import build_conflict_detail

        # Multi-edit safety's own refusal, so its conflict dialog handles it unchanged.
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_conflict_detail(
                flow_id=exc.flow_id,
                expected=exc.expected,
                current=exc.current,
                author_id=exc.author_id,
                author_name=exc.author_name,
                modified_at=exc.modified_at,
            ),
        )
    if isinstance(exc, FlowRevisionMismatchError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.code,
                "message": (
                    "This flow was changed outside Langflow and no longer matches its history. "
                    "Save a copy if you need it, then resend with repair_revision_mismatch to reset it "
                    "to its latest recorded version."
                ),
                "current_revision": exc.current_revision,
                "latest_revision": exc.latest_revision,
            },
        )
    if isinstance(exc, FlowGraphInvalidError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": exc.code,
                "message": (
                    f"The {exc.graph} flow breaks the flow graph rules. Correct it, or resend with "
                    "repair_invalid_graph to repair it and keep the stored original as a version."
                ),
                "graph": exc.graph,
                "violations": [violation.to_dict() for violation in exc.violations],
            },
        )
    if isinstance(exc, FlowRevisionNotRetainedError):
        return HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": exc.code,
                "message": "This point in the flow's history is older than the history Langflow keeps.",
            },
        )
    if isinstance(exc, FlowRevisionNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, FlowHistoryCorruptionError):
        logger.error(
            "Flow history is damaged",
            flow_id=str(exc.flow_id),
            revision=exc.revision,
            damage=exc.kind,
        )
    else:
        logger.error("Flow history write failed", error_type=type(exc).__name__, cause=type(exc.__cause__).__name__)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": FlowHistoryError.code, "message": HISTORY_FAILURE_MESSAGE},
    )


def history_write_summary(result: GraphWriteResult | None) -> FlowHistoryWrite | None:
    """Describe what a graph write recorded, or None when it changed nothing.

    A save that repeats the stored graph records nothing and answers exactly
    as it would have before history existed, so identical saves keep getting
    identical responses.
    """
    if result is None or not (
        result.start_revision is not None or result.deduplicated or result.flow_repaired or result.graph_repairs
    ):
        return None
    return FlowHistoryWrite(
        request_id=result.request_id,
        start_revision=result.start_revision,
        end_revision=result.end_revision,
        latest_revision=result.latest_revision,
        current_revision=result.current_revision,
        deduplicated=result.deduplicated,
        flow_repaired=result.flow_repaired,
        graph_repairs=result.graph_repairs,
    )
