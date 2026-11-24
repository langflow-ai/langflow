from __future__ import annotations

import inspect

from fastapi import HTTPException
from langflow.api.utils.execution_errors import (
    SAFE_WORKFLOW_ERROR_MESSAGE,
    error_details_for_client,
    error_for_client,
)


def test_delegated_error_details_hide_message_and_traceback() -> None:
    sensitive_detail = "owner-provider-sensitive-value"

    details = error_details_for_client(
        RuntimeError(sensitive_detail),
        expose_details=False,
        stack_trace=f"Traceback: provider value={sensitive_detail}",
    )

    assert details.message == "Workflow execution failed."
    assert details.stack_trace == ""
    assert sensitive_detail not in repr(details)


def test_owner_error_details_preserve_debugging_context() -> None:
    message = "owner-visible component failure"
    stack_trace = "Traceback: owner debugging context"

    details = error_details_for_client(
        RuntimeError(message),
        expose_details=True,
        stack_trace=stack_trace,
    )

    assert details.message == message
    assert details.stack_trace == stack_trace


def test_execution_helpers_fail_closed_by_default() -> None:
    from langflow.api import build
    from langflow.api.v1 import endpoints
    from langflow.api.v2 import workflow_execution

    helpers = (
        build.start_flow_build,
        build.generate_flow_events,
        endpoints.simple_run_flow,
        endpoints.run_flow_generator,
        workflow_execution._stream_event_frames,
    )

    for helper in helpers:
        assert inspect.signature(helper).parameters["expose_error_details"].default is False


def test_delegated_http_error_preserves_status_while_redacting_detail() -> None:
    error = HTTPException(status_code=422, detail="sensitive validation detail")

    sanitized = error_for_client(error, expose_details=False)

    assert isinstance(sanitized, HTTPException)
    assert sanitized.status_code == 422
    assert sanitized.detail == SAFE_WORKFLOW_ERROR_MESSAGE
