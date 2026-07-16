"""Request and permission guards for V2 workflow execution.

These run before a flow executes: they reject unsupported field combinations,
enforce owner-only overrides, apply the server-side component policy gate, and
validate caller-supplied output selection. They raise ``HTTPException`` so the
route handlers can surface a structured error without running the graph.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from lfx.utils.flow_validation import CustomComponentValidationError, validate_flow_for_current_settings
from lfx.workflow.converters import ParsedWorkflowRun

from langflow.services.authorization.fetch import deny_to_404
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead


def _flow_not_found_privacy_exception(exc: HTTPException, flow_id: str) -> HTTPException:
    return deny_to_404(exc, detail=f"Flow with id {flow_id} not found")


def _reject_unsupported_sync_fields(parsed: ParsedWorkflowRun) -> None:
    """Reject request fields the inline sync path does not execute."""
    if parsed.mode != "sync":
        return

    unsupported_fields: list[str] = []
    if parsed.data is not None:
        unsupported_fields.append("data")
    if parsed.files:
        unsupported_fields.append("files")
    if parsed.start_component_id is not None:
        unsupported_fields.append("start_component_id")
    if parsed.stop_component_id is not None:
        unsupported_fields.append("stop_component_id")

    if unsupported_fields:
        fields = ", ".join(unsupported_fields)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Unsupported sync request fields",
                "code": "SYNC_MODE_UNSUPPORTED_FIELDS",
                "message": f"mode='sync' does not support request fields: {fields}. Use mode='stream' or "
                "mode='background' for live-canvas overrides, files, or partial-run boundaries.",
                "fields": unsupported_fields,
            },
        )


def _reject_sync_only_fields(parsed: ParsedWorkflowRun) -> None:
    """Reject sync-only request fields in stream/background mode.

    ``output_ids`` only drives answer selection on the inline sync path; other
    modes would silently ignore it, which reads as success to the caller.
    """
    if parsed.mode == "sync" or not parsed.output_ids:
        return

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "Unsupported request fields for mode",
            "code": "MODE_UNSUPPORTED_FIELDS",
            "message": f"mode='{parsed.mode}' does not support request fields: output_ids. "
            "Output selection via output_ids only applies to mode='sync'.",
            "fields": ["output_ids"],
        },
    )


def _enforce_flow_data_override_owner(parsed: ParsedWorkflowRun, flow: FlowRead, current_user: UserRead) -> None:
    """Only the flow owner may execute caller-supplied graph data."""
    if parsed.data is None or flow.user_id == current_user.id:
        return

    raise _flow_not_found_privacy_exception(
        HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the flow owner can override flow data during execution",
        ),
        parsed.flow_id,
    )


def _validate_flow_data_for_execution(parsed: ParsedWorkflowRun, flow: FlowRead) -> None:
    """Apply the same server-side component policy gate used by v1/public runs."""
    try:
        if parsed.data is not None:
            validate_flow_for_current_settings(parsed.data)
        elif flow.data:
            validate_flow_for_current_settings(flow.data)
    except CustomComponentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def _validate_output_ids(output_ids: list[str] | None, terminal_node_ids: list[str]) -> None:
    """Reject ``output_ids`` that aren't outputs of this flow, BEFORE it runs.

    Checks against the terminal node ids known after graph build but before
    execution, so a typo or wrong id costs no compute. ``available`` lists the
    flow's real output ids so callers can self-correct. None/empty means "no
    selection" and never raises.
    """
    if not output_ids:
        return
    known = set(terminal_node_ids)
    unknown = [output_id for output_id in output_ids if output_id not in known]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Unknown output_ids",
                "code": "UNKNOWN_OUTPUT_IDS",
                "message": f"output_ids not produced by this flow: {unknown}.",
                "available": terminal_node_ids,
            },
        )
