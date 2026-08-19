"""Request and permission guards for V2 workflow execution.

These run before a flow executes: they reject unsupported field combinations,
enforce owner-only overrides, apply the server-side component policy gate, and
validate caller-supplied output selection. They raise ``HTTPException`` so the
route handlers can surface a structured error without running the graph.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi import HTTPException, status
from lfx.log.logger import logger
from lfx.utils.flow_validation import (
    CatalogPolicyIdentityUnavailableError,
    CustomComponentValidationError,
    prepare_flow_build_for_user_from_cache,
)
from lfx.workflow.converters import ParsedWorkflowRun

from langflow.api.utils.execution_errors import caller_owns_flow, error_for_client
from langflow.services.authorization.fetch import deny_to_404
from langflow.services.authorization.flow_data_override import flow_data_override_allowed
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "error": "Unsupported request fields for mode",
            "code": "MODE_UNSUPPORTED_FIELDS",
            "message": f"mode='{parsed.mode}' does not support request fields: output_ids. "
            "Output selection via output_ids only applies to mode='sync'.",
            "fields": ["output_ids"],
        },
    )


def _apply_flow_data_override_policy(
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    current_user: UserRead,
) -> ParsedWorkflowRun:
    """Strip caller-supplied graph data the caller may not override.

    This used to deny, reframed to 404 for privacy. That made the Playground
    unusable for every non-owner: the canvas always posts ``data`` (its own
    nodes and edges), so a user holding ``flow:execute`` — which the built-in
    Viewer and Editor both do — could run the flow through the API but got
    "Flow does not exist" from the UI on the same flow (LE-1905).

    Execute-only callers get what ``flow:execute`` means: the stored definition
    runs. Dropping their override is also strictly safer than honoring it, and
    their canvas is read-only, so the graph they posted is the stored one.
    """
    if (parsed.data is None and not parsed.tweaks) or flow_data_override_allowed():
        return parsed
    if caller_owns_flow(flow, current_user):
        return parsed

    logger.info(
        "Ignoring caller-supplied flow data for flow %s: caller may execute but not edit it; running the stored graph.",
        flow.id,
    )
    return replace(parsed, data=None, tweaks={})


def _validate_flow_data_for_execution(
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    current_user: UserRead,
    *,
    expose_error_details: bool,
) -> ParsedWorkflowRun:
    """Apply component policies and return sanitized caller-supplied graph data."""
    try:
        if parsed.data is not None:
            sanitized_data = prepare_flow_build_for_user_from_cache(
                parsed.data,
                is_superuser=current_user.is_superuser,
            )
            if sanitized_data is not None:
                return replace(parsed, data=sanitized_data)
        elif flow.data:
            # A stored graph is caller-controlled: a regular user can persist component
            # source through the flow-write API and then execute it by omitting ``data``.
            # ``validate_flow_for_current_settings`` never sees the caller and therefore
            # cannot apply ``custom_component_admin_only``. Run the caller-aware policy and
            # carry the server-sanitized copy on ``parsed.data`` so every execution mode
            # builds from it. Caller-supplied ``data`` was already rejected for sync mode by
            # ``_reject_unsupported_sync_fields``, so a value here is always server-trusted.
            sanitized_data = prepare_flow_build_for_user_from_cache(
                flow.data,
                is_superuser=current_user.is_superuser,
            )
            if sanitized_data is not None:
                # The streaming driver rebuilds a ``FlowDataRequest`` from this dict, which
                # requires both graph keys, so normalize a stored row that omits one.
                return replace(parsed, data={"nodes": [], "edges": [], **sanitized_data})
    except CustomComponentValidationError as exc:
        client_error = error_for_client(exc, expose_details=expose_error_details)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(client_error)) from exc
    except CatalogPolicyIdentityUnavailableError as exc:
        client_error = error_for_client(exc, expose_details=expose_error_details)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(client_error)) from exc
    except RuntimeError as exc:
        client_error = error_for_client(exc, expose_details=expose_error_details)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(client_error)) from exc
    return parsed


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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": "Unknown output_ids",
                "code": "UNKNOWN_OUTPUT_IDS",
                "message": f"output_ids not produced by this flow: {unknown}.",
                "available": terminal_node_ids,
            },
        )
