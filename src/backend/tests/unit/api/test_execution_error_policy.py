from __future__ import annotations

from langflow.api.utils.execution_errors import error_details_for_client


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
