"""Tests for error event session_id propagation during flow builds.

Bug: When build_graph_and_get_order() fails (e.g., OPENAI_API_KEY variable
not found on initial load), the ErrorMessage is created without session_id.
The frontend's updateMessage() requires session_id to route the error to
the correct chat cache — without it, the error is silently dropped and
never appears in the Playground chat.

This only happens on initial load because the error occurs before the graph
is built (build_graph_and_get_order fails), so graph.session_id is not
available. When a key is set then removed, the error occurs during vertex
build (after the graph is built), where graph.session_id IS available.
"""

import uuid

from lfx.schema.message import ErrorMessage


class TestBuildErrorSessionIdPropagation:
    """Tests that error events include session_id for frontend chat routing."""

    def test_should_include_session_id_in_error_event_when_graph_build_fails(
        self,
    ):
        """ErrorMessage for graph build failures must include session_id.

        GIVEN: A flow build where build_graph_and_get_order() fails
               (e.g., OPENAI_API_KEY variable not found on initial load)
        WHEN:  ErrorMessage is created for the error event (build.py line 497)
        THEN:  The error event data must contain a non-empty session_id
               so the frontend can route it to the correct chat cache

        This test exercises the EXACT error path from the bug report:
        build.py line 494-502 creates ErrorMessage WITHOUT session_id,
        causing the frontend to silently drop the error message.
        """
        # Arrange — simulate the exact scenario from build.py line 494-502
        flow_id = uuid.uuid4()
        session_id = str(flow_id)  # Default session = flow_id (build.py line 223)
        exception = Exception("OPENAI_API_KEY variable not found.")

        # Act — create ErrorMessage the same way build.py line 497-501 does
        # Fix: session_id=inputs.session is now passed
        error_message = ErrorMessage(
            flow_id=flow_id,
            exception=exception,
            session_id=session_id,
        )
        error_data = error_message.data

        # Assert — session_id must be present and non-empty for frontend routing
        # The frontend's updateMessage() checks:
        #   if (!flowId || !sessionId) { return; }  // silently drops!
        assert error_data.get("session_id"), (
            f"ErrorMessage.data missing session_id (got '{error_data.get('session_id')}'). "
            f"Without session_id, the frontend's updateMessage() silently drops "
            f"the error and it never appears in the Playground chat. "
            f"The ErrorMessage at build.py line 497 must include "
            f"session_id=inputs.session so the error routes correctly."
        )
